from datetime import datetime, timedelta
import peak.events.trellis as trellis
from peak.util import plugins
from dateutil.rrule import rrule, rruleset
import dateutil.rrule

from chandler.core import *
from chandler.event import Event
from chandler.time_services import timestamp
from chandler.triage import DONE

def to_dateutil_frequency(freq):
    """Return the dateutil constant associated with the given frequency."""
    return getattr(dateutil.rrule, freq.upper())


class Recurrence(Extension):
    trellis.attrs(
        freqeuncy=None,
        triaged_done_before=None,
        start_extension=Event,
        start_extension_cellname='start'
    )
    triaged_recurrence_ids=trellis.make(trellis.Dict)
    rdates=trellis.make(trellis.Set)
    exdates=trellis.make(trellis.Set)

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

    def occurrences_between(self, range_start, range_end):
        for dt in self.rruleset.between(range_start, range_end, True):
            yield Occurrence(self.item, dt)


class Occurrence(Item):
    def __init__(self, master, recurrence_id):
        self.master = master
        self.recurrence_id = recurrence_id
        # share all master cells
        self.__cells__ = master.__cells__
        # set up add-ons for the occurrence
        self.load_extensions() # plugins.Extensible method

    def __repr__(self):
        return "<Occurrence: %s>" % self.recurrence_id


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

