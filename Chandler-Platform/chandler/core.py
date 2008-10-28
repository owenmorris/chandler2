import peak.events.trellis as trellis
import peak.events.activity as activity
from peak.util import addons, plugins
from datetime import datetime
import chandler.time_services as time_services
import time

__all__ = ('Item', 'Extension', 'ConstraintError', 'Collection')

class Item(trellis.Component, plugins.Extensible):
    extend_with = plugins.Hook('chandler.domain.item_addon')

    title = trellis.attr(initially=u'')
    created = trellis.make(lambda x: time_services.nowTimestamp(),
                           optional=False)

    _extension_types = trellis.make(trellis.Set)

    trellis.make.attrs(
        dashboard_entries=lambda self: trellis.Set([DashboardEntry(self)]),
        collections=trellis.Set
    )

    def __init__(self, **kwargs):
        trellis.Component.__init__(self, **kwargs)
        self.load_extensions() # plugins.Extensible method

    @trellis.maintain
    def extensions(self):
        return frozenset(t(self) for t in self._extension_types)


class Extension(trellis.Component, addons.AddOn):
    __item = trellis.attr(None)

    item = trellis.make(lambda self: self.__item, writable=False)

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

class DashboardEntry(trellis.Component):
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


class Collection(trellis.Component):
    title = trellis.attr(initially=u'')

    items = trellis.make(trellis.Set)

    def __repr__(self):
        return "<Collection: %s>" % self.title

    def add(self, item):
        self.items.add(item)
        item.collections.add(self)

    def remove(self, item):
        self.items.remove(item)
        item.collections.remove(self)


class ConstraintError(Exception):
    """Exception when a cell is set to an inappropriate value."""
    msg = "Can't set %(cell_description)s to: %(cell_value)s"
    cell_description = "cell"

    def __init__(self, cell_value):
        self.cell_value = cell_value

    def __str__(self):
        return self.msg % {'cell_description' : self.cell_description,
                           'cell_value'       : self.cell_value}


#### Utility #####

class Viewer(trellis.Component):
    """
    A utility class, usually used to observe changes to a cell during
    doctests. This should probably eventually move to a Chandler-Debug
    plugin.
    """
    component = trellis.attr(None)
    cell_name = trellis.attr(None)

    @trellis.perform
    def view_it(self):
        value = getattr(self.component, self.cell_name, None)
        if None not in (self.component, self.cell_name, value):
            print "%s changed to: %s" % (self.cell_name, value)
