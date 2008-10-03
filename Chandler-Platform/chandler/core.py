import peak.events.trellis as trellis
import peak.events.activity as activity
import peak.util.addons as addons
from datetime import datetime
import osaf.timemachine as timemachine
import time

__all__ = ('Item', 'Extension', 'Scheduled', 'ConstraintError')

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

class Scheduled(trellis.Component):

    fire_date = trellis.attr(datetime.min)
    callback = trellis.attr(lambda reminder: None)

    @trellis.compute
    def _when_to_fire(self):
        # We want to convert fire_date into an activity.Time object.
        # To do that, subtract from datetime.now
        delta = self.fire_date - timemachine.getNow(self.fire_date.tzinfo)
        delta_seconds = (delta.days * 86400.0) + delta.seconds + (delta.microseconds/1.0e6)

        if delta_seconds >= 0:
            return activity.Time[delta_seconds]
        else:
            return False

    @trellis.perform # @@@ can't be a perform because we don't know if
                     # callback modifies the trellis or not
    def fire(self):
        if self._when_to_fire:
            self.callback(self)

class ConstraintError(Exception):
    """Exception when a cell is set to an inappropriate value."""
    msg = "Can't set %(cell_description)s to: %(cell_value)s"
    cell_description = "cell"

    def __init__(self, cell_value):
        self.cell_value = cell_value

    def __str__(self):
        return self.msg % {'cell_description' : self.cell_description,
                           'cell_value'       : self.cell_value}
