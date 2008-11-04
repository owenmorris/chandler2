from datetime import datetime, timedelta
import peak.events.trellis as trellis
from dateutil.rrule import rrule, rruleset
import dateutil.rrule

from chandler.core import *
from chandler.event import Event

def to_dateutil_frequency(freq):
    """Return the dateutil constant associated with the given frequency."""
    return getattr(dateutil.rrule, freq.upper())


class Recurrence(Extension):
    trellis.attrs(
        freqeuncy=None,
        start_extension=Event,
        start_extension_cellname='start'
    )

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
