import peak.events.trellis as trellis
import peak.events.activity as activity
import peak.util.addons as addons
from datetime import datetime
import chandler.time_services as time_services
import time

__all__ = ('Item', 'Extension', 'ConstraintError')

class Item(trellis.Component):

    title = trellis.attr(initially=u'')

    _extension_types = trellis.make(trellis.Set)
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


class ConstraintError(Exception):
    """Exception when a cell is set to an inappropriate value."""
    msg = "Can't set %(cell_description)s to: %(cell_value)s"
    cell_description = "cell"

    def __init__(self, cell_value):
        self.cell_value = cell_value

    def __str__(self):
        return self.msg % {'cell_description' : self.cell_description,
                           'cell_value'       : self.cell_value}
