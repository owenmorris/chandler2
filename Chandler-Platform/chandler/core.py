import peak.events.trellis as trellis
import peak.events.activity as activity
from peak.util import addons, plugins
from datetime import datetime
import chandler.time_services as time_services
import time
import sys

__all__ = ('Item', 'Extension', 'DashboardEntry', 'Collection',
           'One', 'Many',
           'Feature', 'Command', 'Text', 'Table', 'Scope',
           'InheritedAddOn', 'inherited_attrs',
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


class Item(trellis.Component, plugins.Extensible):
    extend_with = plugins.Hook('chandler.domain.item_addon')

    title = trellis.attr(initially=u'')
    created = trellis.make(lambda x: time_services.nowTimestamp(),
                           optional=False)

    _extension_types = trellis.make(trellis.Set)

    trellis.make.attrs(
        _default_dashboard_entry=lambda self: DashboardEntry(self),
        dashboard_entries=lambda self: trellis.Set([self._default_dashboard_entry]),
    )

    collections = Many()

    def __init__(self, **kwargs):
        trellis.Component.__init__(self, **kwargs)
        self.load_extensions() # plugins.Extensible method

    @trellis.maintain
    def extensions(self):
        return frozenset(t(self) for t in self._extension_types)

class InheritedAddOn(addons.AddOn):
    __inherited__ = () # overridden to set() by calling inherited_attrs()

    @classmethod
    def __class_call__(cls, ob, *data):
        parent = None
        # look for a parent to inherit from
        for parent, child_key in plugins.Hook('chandler.domain.inherit_from').query(ob):
            if parent is not None:
                # use parent's dict to store inherited AddOns
                a = parent.__dict__
                addon_key = cls.addon_key(child_key, *data)
                break
        else:
            # normal AddOn behavior
            a = addons.addons_for(ob)
            addon_key = cls.addon_key(*data)
        try:
            return a[addon_key]
        except KeyError:
            ob = a.setdefault(addon_key, super(addons.AddOn, cls).__class_call__(ob, *data))
            if parent is not None:
                ob._init_inheritance(parent)
            return ob

    def _init_inheritance(self, parent):
        for attr in self.__inherited__:
            self.__cells__[attr] = self.__class__(parent).__cells__[attr]


def inherited_attrs(**attrs):
    """Like trellis.attrs but add attributes to __inherited__, too."""
    frame = sys._getframe(1)
    trellis._make_multi(frame, attrs, arg='initially')
    frame.f_locals.setdefault('__inherited__', set()).update(attrs)


class Extension(trellis.Component, InheritedAddOn):
    __item = trellis.attr(None)

    item = trellis.make(lambda self: self.__item, optional=False)

    def __init__(self, item, **kwds):
        self.__item = item
        super(Extension, self).__init__(**kwds)

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
            obj = obj.__item
        except AttributeError:
            pass
        return isinstance(obj, Item) and cls in obj._extension_types

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
        kw.setdefault("when", cells["created"])
        kw.setdefault("what", cells["title"])
        super(DashboardEntry, self).__init__(**kw)
        self.subject_item = subject_item
        self.load_extensions() # plugins.Extensible methods


class Collection(trellis.Component):
    title = trellis.attr(initially=u'')

    items = Many(inverse=Item.collections)

    def __repr__(self):
        return "<Collection: %s>" % self.title

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

class Feature(trellis.Component):
    trellis.attrs(
        label=u'',
        enabled=True,
        visible=True,
        help=None,
    )
    cell = None
    scope = One()

class Text(Feature):
    pass

class Command(Feature):
    def act(self): pass

class Table(Feature):
    items = trellis.make(trellis.List)

    @trellis.maintain(initially=None)
    def selected_item(self):
        if self.selected_item is None or not self.selected_item in self.items:
            return self.items[0] or None
        return self.selected_item

    def display_name(self, item):
        """Hook for customizing item display"""
        return unicode(item)

class _RuleCell(trellis.Cell):
     def get_value(self):
         return self.rule().get_value()
     def set_value(self, value):
         return self.rule().set_value(value)
     value = property(get_value, set_value)

class Scope(trellis.Component):
    model = trellis.attr(None)
    features = Many(inverse=Feature.scope)

    def make_model_cell(self, attr):
        return _RuleCell(lambda: trellis.Cells(self.model)[attr])


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
