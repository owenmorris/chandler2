import peak.events.trellis as trellis
import peak.events.collections as collections
import peak.events.activity as activity
from simplegeneric import generic
from peak.util import addons, plugins
from datetime import datetime
import chandler.time_services as time_services
import time
import sys

__all__ = ('Item', 'Extension', 'DashboardEntry', 'Collection', 'Entity',
           'One', 'Many', 'FilteredSubset', 'AggregatedSet',
           'ItemAddOn', 'inherited_attrs', 'reset_cell_default',
           'InteractionComponent', 'Feature', 'Scope',
           'Command', 'Text', 'Table', 'TableColumn', 'Choice', 'ChoiceItem',
           'ConstraintError', 'Viewer',)


class Role(trellis.CellAttribute):
    """
    Superclass for One, Many descriptors, which are used to set up
    'bi-directional references'.
    """

    # These classes work by observing a trellis.Set of 2-element tuples
    # that contains all values for the relationship (like a "linking table" in
    # SQL). This interface could be made more abstract: for example, if the
    # objects in question come from a database, we might want to have primary
    # keys in the "table", or not populate the entire table at all

    _tuples = None

    inverted = False

    # If an instance is initialised with an inverse (i.e. via keyword in
    # __init__), then we have to access _tuples "backward". The inverted
    # attribute says whether or not to do that.

    def __init__(self, *args, **kw):
        inverse = kw.pop('inverse', None)
        if inverse is None:
            self._tuples = trellis.Set()
        else:
            self._tuples = inverse._tuples
            self.inverted = True
        super(Role, self).__init__(*args, **kw)

    def _iter_values(self, obj):
        """Used to find all values in the _tuples "table" for a given object"""
        for t in self._tuples:
            if self.inverted:
                if t[1] is obj: yield t[0]
            else:
                if t[0] is obj: yield t[1]


class Many(Role):

    def initial_value(self, obj):
        # override of trellis.CellAttribute
        return TupleBackedSet(_tuples=self._tuples, owner=obj,
                               inverted=self.inverted)

    def __set__(self, obj, iterable):
        old_values = set(self._iter_values(obj))
        new_values = set(iterable)
        remove = old_values.difference(new_values)
        new_values.difference_update(old_values)

        for value in remove:
            t = (value, obj) if self.inverted else (obj, value)
            self._tuples.remove(t)

        for value in iterable:
            t = (value, obj) if self.inverted else (obj, value)
            self._tuples.add(t)

    def __delete__(self, obj):
        self.__set__(obj, ())


class One(Role):

    def __init__(self, inverse=None):

        def rule(obj):
            for val in self._iter_values(obj):
                return val
            return None

        return super(One, self).__init__(inverse=inverse, rule=rule, value=None)

    def __set__(self, obj, value):
        """Called when you assign to a ``One`` attribute"""

        # Remove the old value, so that we really are a to-one relationship
        self.__delete__(obj)
        if obj is not None:
            if self.inverted:
                t = (value, obj)
            else:
                t = (obj, value)
            self._tuples.add(t)

    def __delete__(self, obj):
        remove = set((value, obj) if self.inverted else (obj, value)
                     for value in self._iter_values(obj))
        self._tuples.difference_update(remove)


class TupleBackedSet(trellis.Set):
    """trellis.Set subclass that is used as the value of a Many() attribute."""

    # In other words, one of these gets instantiated as the value
    # gets instantiated whenever you create an object whose class has a
    # Many().
    #
    # The idea is that we make changes always by changing our _tuples
    # instance; by observing that and calling our superclass's methods
    # to update the Set's contents, we avoid circularity problems and
    # keep in sync.
    #
    # XXX: Currently, only add() and remove() methods work; other standard
    # set methods (xxx_update, for example, will cause bad things to happen.

    _tuples = trellis.attr(None) # This will be shared amongst instances
    owner = trellis.attr(None)
    inverted = False

    def add(self, obj):
        t = (obj, self.owner) if self.inverted else (self.owner, obj)
        self._tuples.add(t)

    def remove(self, obj):
        t = (obj, self.owner) if self.inverted else (self.owner, obj)
        self._tuples.remove(t)

    def iter_matches(self, iterable):
        for t in iterable:
            if self.inverted:
                t = tuple(reversed(t))
            if t[0] is self.owner:
                yield t[1]

    @trellis.maintain
    def maintain_set(self):
        for obj in self.iter_matches(self._tuples.removed):
            trellis.Set.remove(self, obj)
        for obj in self.iter_matches(self._tuples.added):
            trellis.Set.add(self, obj)


class AggregatedSet(trellis.sets.ImmutableSet, trellis.Component):
    """
    Takes a Set of input objects, and a get_values() function, and
    produces a Set of all values associated with the input objects.
    """

    # Implementation notes
    #
    #    - Like set, trellis.Set, maintains a _data dict. However,
    #      in our case, the keys of _data are input objects, and
    #      the values are (for now) Cells.
    #
    #    - The elements of _added and _removed are no longer quite so
    #      simple, because they have to handle two different cases:
    #
    #        1. single elements being added/removed from items, in which
    #           case all their associated values need to be added/removed.
    #
    #        2. values being added/removed due to start date/time changes,
    #           or due to changes in things our get_values depends on.
    #
    #      So, we make _added and _removed dicts rather than sets. In the
    #      face of a general change, we can figure out whether a particular
    #      value should be considered to be added or removed (i.e. whether
    #      it was present or not present before the start of the change).

    def __init__(self, iterable=None, **kw):
        if iterable is not None:
            kw.update(input=trellis.Set(iterable))
        trellis.Component.__init__(self, **kw)

    @trellis.maintain
    def input(self):
        return trellis.Set()

    _added = trellis.todo(dict)
    _removed = trellis.todo(dict)

    to_add = _added.future
    to_remove = _removed.future

    def get_values(self, item):
        """
        Override this to iterate over the computed values corresponding
        to ``item``.
        """
        return (item,)

    def __iter__(self):
        seen = set()
        for cell in self._data.itervalues():
            for value in cell.get_value():
                if not value in seen:
                    seen.add(value)
                    yield value

    def __contains__(self, obj):
        if self._data is None:
            return False
        else:
            return any(obj in cell.get_value()
                       for cell in self._data.itervalues())

    def __repr__(self):
        return "%s([%s])" % (type(self).__name__,
                             ", ".join(repr(x) for x in self))

    def __len__(self):
        return sum(1 for value in self.__iter__())

    def __nonzero__(self):
        return any(cell.get_value()
                   for cell in self._data.itervalues())

    @trellis.compute
    def added(self):
        return self._added_and_removed[0]

    @trellis.compute
    def removed(self):
        return self._added_and_removed[1]

    @trellis.maintain
    def _added_and_removed(self):
        # Return a 2-element tuple of the newly added and newly
        # removed objects.
        added = set()
        removed = set()

        for item, values in self._added.iteritems():
            added.update(v for v in values
                         if not any(v in self._data[other].value and not v in self._added.get(other, ())
                                     for other in self.input
                                     if other is not item))
        for item, values in self._removed.iteritems():
            removed.update(v for v in values
                           if all(v not in self._data[other].value or v in self._added.get(other, ())
                                  for other in self.input
                                  if other is not item))

        return (added - removed, removed - added)

    @trellis.maintain(make=dict)
    def _data(self):
        """The dictionary containing the set cells."""
        if self._new_input:
            data = self._data
            added = iter(x for x in self._new_input if not x in self._data)
            removed = set(x for x in self._data if not x in self._new_input)
        else:
            data = self._data
            added = self.input.added
            removed = self.input.removed

        for item in added:
            cell = data.get(item, None)
            if cell is None:
                rule = self._create_cell_rule(item, data)
                cell = trellis.Cell(rule=rule, value=rule())
                trellis.on_undo(data.pop, item, None)
                data[item] = cell
                trellis.mark_dirty()
        for item in removed:
            cell = data.get(item, None)
            if cell is not None:
                self.to_remove[item] = cell.value
                trellis.on_undo(setattr, cell, 'rule', cell.rule)
                cell.rule = lambda:()
                trellis.on_undo(data.__setitem__, item, data[item])
                del data[item]
                trellis.mark_dirty()
        return data

    @trellis.compute(resetting_to=None)
    def _new_input(self):
        return self.input

    def _create_cell_rule(self, item, data):
        def maintain_rule():
            """This maintains the cell corresponding to item in _data"""

            # Figure out the new value; this also causes the
            # trellis to calculate the cell's dependencies, and
            # thereby trigger later changes if necessary.
            new_value = self.get_values(item)

            # If we were a real @maintain rule it would be
            # easy to figure out the old value here. Instead,
            # we have to track down the cell from self._data
            # (the same way that a @maintain rule eventually gets
            # it from component.__cells__).

            if data is None:
                return new_value

            old_cell = data.get(item, None)
            old_value = getattr(old_cell, 'value', ())

            if old_value != new_value:
                self.to_add[item] = tuple(e for e in new_value
                                          if not e in old_value)
                self.to_remove[item] = tuple(e for e in old_value
                                             if not e in new_value)

            return new_value

        return maintain_rule


class FilteredSubset(AggregatedSet):

    predicate = trellis.attr(lambda obj: True)

    def get_values(self, item):
        return (item,) if self.predicate(item) else ()

class Entity(trellis.Component):
    _extension_types = trellis.make(trellis.Set)

    @trellis.maintain
    def extensions(self):
        return frozenset(t(self) for t in self._extension_types)

class Item(Entity, plugins.Extensible):
    extend_with = plugins.Hook('chandler.domain.item_addon')

    trellis.attrs(
        title=u'',
        body=u'',     # XXX add body to Item doctests..
    )

    created = trellis.make(lambda x: time_services.nowTimestamp(),
                           optional=False, writable=True)

    _extension_types = trellis.make(trellis.Set)

    trellis.make.attrs(
        _default_dashboard_entry=lambda self: DashboardEntry(self),
        dashboard_entries=lambda self: trellis.Set([self._default_dashboard_entry]),
    )

    collections = Many()

    def __init__(self, **kwargs):
        trellis.Component.__init__(self, **kwargs)
        self.load_extensions() # plugins.Extensible method

    def inherited_value(self, add_on_instance, name):
        """Inheritance rule for cells defined by inherited_attrs."""
        return getattr(add_on_instance, name)


class ItemAddOn(trellis.Component, addons.AddOn):
    _item = trellis.attr(None)
    item = trellis.make(lambda self: self._item, optional=False)

    def __init__(self, item, **kwds):
        self._item = item
        super(ItemAddOn, self).__init__(**kwds)

def reset_cell_default(component, attr):
    cell_attribute = getattr(type(component), attr)
    setattr(component, attr, cell_attribute.initial_value(component))

def inherited_attrs(**attrs):
    """Like trellis.attrs, but creates maintain rules that handle inheritance."""
    frame = sys._getframe(1)
    for k, v in attrs.items():
        if k in frame.f_locals:
            raise TypeError("%s is already defined in this class" % (k,))
        rule = get_inherit_rule(k)
        frame.f_locals[k] = trellis.CellAttribute.mkattr(v, __name__=k, rule=rule)

def get_inherit_rule(name):
    def func(add_on):
        item = getattr(add_on, '_item', None)
        if item is None:
            item = add_on
        return item.inherited_value(add_on, name)
    func.__name__ = name
    return func

class Extension(ItemAddOn):
    @trellis.modifier
    def add(self, **kw):
        t = type(self)

        if t in self.item._extension_types:
            raise ValueError("Extension %s has already been added" % (t,))

        self.item._extension_types.add(t)
        trellis.init_attrs(self, **kw)
        return self

    @trellis.modifier
    def remove(self):
        t = type(self)

        try:
            self.item._extension_types.remove(t)
        except KeyError:
            raise ValueError("Extension %s is not present" % (t,))

    @classmethod
    def installed_on(cls, obj):
        try:
            obj = obj._item
        except AttributeError:
            pass
        return isinstance(obj, Entity) and cls in obj._extension_types

class DashboardEntry(trellis.Component, plugins.Extensible):
    extend_with = plugins.Hook('chandler.domain.dashboard_entry_addon')

    trellis.attrs(
        subject_item=None,
        when=None,
        what=None,
    )

    def __init__(self, subject_item, **kw):
        if not isinstance(subject_item, Item):
            raise TypeError, "DashboardEntry's subject_item must be an Item"
        cells = trellis.Cells(subject_item)
        # touch created in case it's a rule and doesn't yet exist
        subject_item.created
        kw.setdefault("when", cells["created"])
        kw.setdefault("what", cells["title"])
        super(DashboardEntry, self).__init__(**kw)
        self.subject_item = subject_item
        self.load_extensions() # plugins.Extensible methods


class Collection(Entity):
    title = trellis.attr(initially=u'')

    items = Many(inverse=Item.collections)

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self.title)

    def add(self, item):
        self.items.add(item)

    def remove(self, item):
        self.items.remove(item)


class ConstraintError(Exception):
    """Exception when a cell is set to an inappropriate value."""
    msg = "Can't set %(cell_description)s to: %(cell_value)s"
    cell_description = "cell"

    def __init__(self, cell_value):
        self.cell_value = cell_value

    def __str__(self):
        return self.msg % {'cell_description' : self.cell_description,
                           'cell_value'       : self.cell_value}

#### Interaction Components #####

class InteractionComponent(trellis.Component):
    scope = One()

    trellis.attrs(
        label=u'',
        enabled=True,
        visible=True,
        help=None,
    )

    hints = trellis.make(dict)

    def __iter__(self):
        yield self


class Feature(InteractionComponent):
    value = trellis.attr(None)


class _RuleCell(trellis.Cell):
     def get_value(self):
         return self.rule().get_value()
     def set_value(self, value):
         return self.rule().set_value(value)
     value = property(get_value, set_value)


class Scope(InteractionComponent):
    model = trellis.attr(None)
    subcomponents = Many(inverse=InteractionComponent.scope)

    def make_model_cell(self, attr):
        def get_cell():
            return trellis.Cells(self.model)[attr]
        return _RuleCell(get_cell)

    @staticmethod
    def feature_cells(**kw):
        def rule(scope):
            def iter_features():
                for key, fn in kw.iteritems():
                    feature = fn()
                    feature.scope = scope
                    feature.value = scope.make_model_cell(key)
                    yield feature
            return tuple(iter_features())
        return trellis.CellAttribute(rule=rule)

    def __iter__(self):
        yield self

        for child in self.subcomponents:
            for value in child:
                yield value


class Text(Feature):
    pass


class Command(Feature):
    def act(self):
        """Override this to implement a particular command."""
        pass

class ChoiceItem(InteractionComponent):
    trellis.attrs(
        label=u'',
        help=u'',
        enabled=True,
        value=None,
    )
    def __repr__(self):
        return "<%s at 0x%0x value=%r>" % (type(self).__name__, id(self), self.value)

class Choice(Feature):
    choices = trellis.make(trellis.List, writable=True)

    # code to translate between our value and our chosen_item
    @trellis.compute(resetting_to=None)
    def new_value(self):
        return self.value

    @trellis.compute
    def chosen_item(self):
        """The currently selected ChoiceItem from our list"""
        # First, cover a change to the new_choice receiver cell
        if self.new_choice is not None:
            if self.new_choice in self.choices:
                return self.new_choice

            raise ConstraintError("Choice %r isn't in choices of %r" %
                                   (self.new_choice, self))

        # Cover the case of someone explicitly tweaking value (or
        # indirectly triggering a recompute)
        value = self.new_value or self.value
        for choice_item in self.choices:
            if choice_item.value == value:
                return choice_item

        if value is not None:
            raise ConstraintError("No value for %r in choices of %r" %
                                   (value, self))

        # If all else fails, return the first ChoiceItem
        if self.choices:
            return self.choices[0]

    @trellis.maintain(initially=None)
    def value(self):
        if self.chosen_item is not None:
            return self.chosen_item.value

    new_choice = trellis.attr(resetting_to=None)


@trellis.modifier
def _change_set(s, contents):
    s.clear()
    s.update(contents)

    single_item_selection = trellis.attr(True)
class Table(Scope):
    """A Table is responsible for managing the display of a C{trellis.Set}"""
    columns = trellis.make(trellis.List)
    sort_column = trellis.attr(None)
    select_column = trellis.attr(resetting_to=None)

    @trellis.maintain
    def items(self):
        return collections.SortedSet(data=self.model)

    @trellis.make(writable=True)
    def model(self):
        return trellis.Set()

    @staticmethod
    def default_sort_key(item):
        return item

    @trellis.maintain
    def _maintain_sort_params(self):
        if self.select_column is not None and self.select_column.can_sort:
            if self.select_column is self.sort_column:
                self.select_column.sort_ascending = not self.select_column.sort_ascending
                self.items.reverse = not self.select_column.sort_ascending
            else:
                self.sort_column = self.select_column
        elif self.sort_column is None:
            self.items.sort_key = self.default_sort_key
        else:
            # should probably be in a modifier because it could
            # trigger 2 unnecessary sorts
            self.items.sort_key = self.sort_column.sort_key
            self.items.reverse = not self.sort_column.sort_ascending

    new_selection = trellis.attr(resetting_to=None)
    single_item_selection = trellis.attr(True)

    def _make_selection(self):
        contents = self.new_selection
        if self.single_item_selection:
            if contents is not None:
                contents  = (contents,)
            elif self.selected_item is not None:
                contents = (self.selected_item,)

        if contents is None:
            contents = ()
        return collections.SubSet(contents, base=self.model)

    @trellis.maintain(initially=None, optional=True)
    def selection(self):
        new_sel = self.new_selection
        if self.single_item_selection:
            if new_sel is None:
                new_sel = self.selected_item
            if new_sel is not None:
                items = (new_sel,)
            else:
                items = ()
            selection = trellis.Set(items)
        else:
            selection = self.selection
            if selection is None:
                if new_sel is None:
                    new_sel = ()
                return collections.SubSet(new_sel, base=self.model)
            if new_sel is not None:
                _change_set(selection, new_sel)

        return selection

    @trellis.maintain(initially=None, optional=True)
    def selected_item(self):
        if self.new_selection is not None:
            return self.new_selection
        elif self.selected_item is None:
            try:
                return iter(self.items).next()
            except StopIteration, TypeError:
                pass # i.e. return None
        return self.selected_item

    def get_cell_value(self, (row, col)):
        """Get value at (row, col) in the table"""
        self.items.changes # introduce dependency?!?!
        try:
            item = self.items[row]
            column = self.columns[col]
        except IndexError:
            return None
        else:
            return column.get_value(item)

    visible_range_increments = trellis.attr(resetting_to=(0, 0, 0, 0))

    @trellis.maintain(initially=(0, 0, 0, 0))
    def visible_ranges(self):
        visible_ranges = tuple(old + delta
                               for old, delta in zip(self.visible_ranges,
                                                     self.visible_range_increments))
        if self.visible_ranges != visible_ranges:
            self.set_visible_ranges(visible_ranges)
        return visible_ranges

    @trellis.make
    def observer(self):
        return collections.Observing(lookup_func=self.get_cell_value)

    @trellis.modifier
    def set_visible_ranges(self, (start_row, end_row, start_col, end_col)):
        keys = self.observer.keys
        old = self.visible_ranges

        def in_new(row, col):
            return start_row <= row < end_row and start_col <= col < end_col

        def in_old(row, col):
            return old[0] <= row < old[1] and old[2] <= col < old[3]

        for row in xrange(min(old[0], start_row), max(old[1], end_row)):
            for col in xrange(min(old[2], start_col), max(old[2], end_col)):
                cell_in_new = in_new(row, col)
                cell_in_old = in_old(row, col)

                if cell_in_new and not cell_in_old:
                    keys.add((row, col))
                elif cell_in_old and not cell_in_new:
                    keys.remove((row, col))



class TableColumn(InteractionComponent):
    trellis.attrs(
        can_sort=True,
        sort_ascending=False,
    )

    # @@@ [grant] Need to document these ...
    action = None
    set_text_value = None

    def __repr__(self):
        return '<%s "%s">' % (type(self).__name__, self.label)

    def get_value(self, item):
        return unicode(item)

    def sort_key(self, item):
        return self.get_value(item)

class Frame(Scope):
    """A top-level window/dialog in the UI"""
    pass


#### Utility #####

class Viewer(trellis.Component):
    """
    A utility class, usually used to observe changes to a cell during
    doctests. This should probably eventually move to a Chandler-Debug
    plugin.
    """
    component = trellis.attr(None)
    cell_name = trellis.attr(None)

    @trellis.compute
    def formatted_name(self):
        return self.cell_name

    @trellis.perform
    def view_it(self):
        value = getattr(self.component, self.cell_name, None)
        if None not in (self.component, self.cell_name, value):
            print "%s changed to: %s" % (self.formatted_name, value)

#
# Initial presentation support (such as it is)
#

@generic
def present(obj, parent=None):
    """
    Turn an interaction/presentation object into
    something usable by a GUI library.
    """
    #print "Generic rendering of %s" % (obj,)
    return obj

@present.when_type(Scope)
def present_scope(scope, parent=None):
    #print "Rendering scope %s" % (scope,)
    for subcomponent in scope.subcomponents:
        present(subcomponent, parent)

