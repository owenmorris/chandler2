from datetime import datetime, timedelta
import peak.events.trellis as trellis
from peak.util import plugins
from dateutil.rrule import rrule, rruleset
import dateutil.rrule

from chandler.core import *
from chandler.event import Event
from chandler.time_services import timestamp, getNow
from chandler.triage import DONE, LATER, NOW, Triage

def to_dateutil_frequency(freq):
    """Return the dateutil constant associated with the given frequency."""
    return getattr(dateutil.rrule, freq.upper())


class Recurrence(Extension):
    trellis.attrs(
        frequency=None,
        triaged_done_before=None,
        start_extension=Event,
        start_extension_cellname='start',
    )
    trellis.make.attrs(
        triaged_recurrence_ids=trellis.Dict,
        modification_recipes=trellis.Dict,
        _recurrence_dashboard_entries=trellis.Dict,
        rdates=trellis.Set,
        exdates=trellis.Set,
        _occurrence_cache=dict,
        _pre_modification_cells=dict
    )

    @trellis.compute
    def start(self):
        if not self.start_extension.installed_on(self.item):
            return None
        else:
            extension = self.start_extension(self.item)
            return getattr(extension, self.start_extension_cellname)

    def build_rrule(self, count=None, until=None):
        """Return a dateutil rrule based on self.

        The time-limit for the series can be overridden by setting
        either count or until.

        """
        kwds = dict(dtstart=self.start,
                    freq=to_dateutil_frequency(self.frequency),
                    cache=True)

        if count is not None:
            kwds['count'] = count
        elif until is not None:
            kwds['until'] = until
        elif self.count is not None:
            kwds['count'] = self.count
        else:
            kwds['until'] = self.until

        return rrule(**kwds)

    @trellis.maintain(initially=None)
    def until(self):
        """The last possible date for the series."""
        if self.count is None:
            return self.until
        else:
            rule = self.build_rrule(count=self.count)
            return rule[-1]

    @trellis.maintain(initially=None)
    def count(self):
        if self.count is None:
            self.until # make sure the rule depends on until
            return None
        elif self.until is None:
            return None
        else:
            rule = self.build_rrule(until=self.until)
            return rule.count()

    @trellis.compute
    def rruleset(self):
        if self.start is None:
            return None
        rrs = rruleset(cache=True)
        if self.frequency is not None:
            rrs.rrule(self.build_rrule())
        elif not self.rdates:
            # no rules or rdates, nothing to do
            return None
        for dt in self.rdates:
            rrs.rdate(dt)
        for dt in self.exdates:
            rrs.exdate(dt)
        return rrs

    def get_occurrence(self, recurrence_id):
        """Return Occurrence for recurrence_id, cache it for later."""
        occ = self._occurrence_cache.get(recurrence_id)
        if not occ:
            occ = Occurrence(self.item, recurrence_id)
            self._occurrence_cache[recurrence_id] = occ
        return occ

    @trellis.maintain
    def dashboard_recurrence_ids(self):
        """The set of recurrence_ids which should have DashboardEntries.

        Updates self._recurrence_dashboard_entries when re-calculated.

        """
        old_set = self.dashboard_recurrence_ids
        if old_set is None:
            old_set = frozenset()

        if not self in self.item.extensions or not self.start or not self.rruleset:
            new_set = frozenset()
        else:
            now_dt = getNow()
            past_done = None
            future_later = None
            new_set = set()
            for recurrence_id in self.rruleset:
                # XXX inefficient, creating an Occurrence for every past recurrence-id,
                # probably should be optimized by walking backwards from triaged_done_before
                triage = Triage(self.get_occurrence(recurrence_id)).calculated
                if triage not in (LATER, DONE):
                    new_set.add(recurrence_id)
                else:
                    if triage == DONE and recurrence_id < now_dt:
                        past_done = recurrence_id
                    elif triage == LATER and recurrence_id > now_dt:
                        future_later = recurrence_id
                        break

            for recurrence_id in past_done, future_later:
                if recurrence_id is not None:
                    new_set.add(recurrence_id)

            new_set.update(self.triaged_recurrence_ids)
            # XXX add modifications

        for recurrence_id in old_set - new_set:
            del self._recurrence_dashboard_entries[recurrence_id]
        for recurrence_id in new_set - old_set:
            entry = DashboardEntry(Occurrence(self.item, recurrence_id))
            self._recurrence_dashboard_entries[recurrence_id] = entry

        return new_set

    @trellis.maintain
    def _update_dashboard_entries(self):
        """Keep Item.dashboard_entries in sync with self._recurrence_dashboard_entries."""
        recurrence_entries = self._recurrence_dashboard_entries
        entries = self.item.dashboard_entries
        # keep the master in entries iff there's no recurrence
        if len(recurrence_entries) > 0:
            entries.discard(self.item._default_dashboard_entry)
        else:
            entries.add(self.item._default_dashboard_entry)

        for recurrence_id, entry in recurrence_entries.deleted.iteritems():
            entries.discard(entry)
        for recurrence_id, entry in recurrence_entries.added.iteritems():
            entries.add(entry)
        if recurrence_entries.changed:
            msg = "a value in recurrence_dashboard_entries changed: %s"
            raise Exception, msg % recurrence_entries.changed


    def occurrences_between(self, range_start, range_end):
        for dt in self.rruleset.between(range_start, range_end, True):
            yield self.get_occurrence(dt)

    def pick_dashboard_entry(self, recurrence_id):
        """Return the DashboardEntry associated with recurrence_id, or None."""
        return self._recurrence_dashboard_entries.get(recurrence_id)

class Occurrence(Item):
    def __init__(self, master, recurrence_id):
        self.master = master
        self.recurrence_id = recurrence_id
        # share all master cells
        self.__cells__ = master.__cells__
        # set up add-ons for the occurrence
        self.load_extensions()
        if self.modification_recipe:
            # initialize modified cells
            self._change_cells(self.modification_recipe.changes)

    def __repr__(self):
        return "<Occurrence: %s>" % self.recurrence_id

    @trellis.modifier
    def modify(self, add_on=None, name=None, value=None):
        """Adjust ModificationRecipe such that add_on(self).name == value.

        If no ModificationRecipe exists, create it.  With no
        arguments, just create a ModificationRecipe for this
        recurrence-id if one doesn't already exist.

        """
        recipes = Recurrence(self.master).modification_recipes
        recipe = recipes.get(self.recurrence_id)
        if not recipe:
            recipe = recipes.added.get(self.recurrence_id)
        if not recipe:
            recipe = ModificationRecipe()
            recipes[self.recurrence_id] = recipe

        if name:
            recipe.make_change(add_on, name, value)

    @trellis.compute
    def modification_recipe(self):
        return Recurrence(self.master).modification_recipes.get(self.recurrence_id)

    @trellis.modifier
    def unmodify(self):
        if self.modification_recipe:
            del Recurrence(self.master).modification_recipes[self.recurrence_id]

    @trellis.maintain
    def update_modified_cells(self):
        deletions = {}
        if self.modification_recipe:
            # new modifications
            if self.modification_recipe.changes.added:
                self._change_cells(self.modification_recipe.changes.added)
            # deleted changes
            deletions = self.modification_recipe.changes.deleted

        master_recipes = Recurrence(self.master).modification_recipes
        if self.recurrence_id in master_recipes.deleted:
            # unmodified
            deleted_recipe = master_recipes.deleted[self.recurrence_id]
            deletions = deleted_recipe.changes

        if deletions:
            old_cells = Recurrence(self.master)._pre_modification_cells[self.recurrence_id]
            for cls, name in deletions:
                add_on = cls(self) if cls is not None else self
                setattr(add_on, name, old_cells[(cls, name)])

    @trellis.modifier
    def _change_cells(self, change_dict):
        pre_modification_dict = Recurrence(self.master)._pre_modification_cells
        old_cells = pre_modification_dict.setdefault(self.recurrence_id, {})
        for key, value in change_dict.iteritems():
            cls, name = key
            add_on = cls(self) if cls is not None else self
            # before overriding a cell, store it so it can be restored
            if key not in old_cells:
                old_cells[key] = trellis.Cells(add_on)[name]
            setattr(add_on, name, value)


class ModificationRecipe(trellis.Component):
    # a dictionary of (AddOn, attr_name) keys, with Cells as values
    changes = trellis.make(trellis.Dict)

    @trellis.modifier
    def make_change(self, add_on, name, value):
        key = (add_on, name)
        cell = self.changes.get(key)
        if not cell:
            if self.changes.added.get(key):
                # multiple changes to the same attribute, bad
                raise Exception, "Can't change the same attribute twice: %s" % key
            self.changes[key] = trellis.Cell(value=value)
        else:
            cell.value = value

def occurrence_triage(item):
    """Hook for triage of an occurrence."""
    if not isinstance(item, Occurrence):
        return ()
    else:
        master = Recurrence(item.master)
        done_before = master.triaged_done_before
        if item.recurrence_id in master.triaged_recurrence_ids:
            return (master.triaged_recurrence_ids[item.recurrence_id],)
        elif not done_before or done_before < item.recurrence_id:
            return ()
        else:
            return ((timestamp(Event(item).start), DONE),)

plugins.Hook('chandler.domain.triage').register(occurrence_triage)

def inherit_via_recurrence(item):
    if isinstance(item, Occurrence):
        return (item.master, item.recurrence_id)
    else:
        return (None, None)

plugins.Hook('chandler.domain.inherit_from').register(inherit_via_recurrence)

