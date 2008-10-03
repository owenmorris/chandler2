from datetime import datetime, timedelta, time
import peak.events.trellis as trellis

from chandler.core import *
from chandler.timemachine import floating


one_hour = timedelta(hours=1)
zero_delta = timedelta(0)
midnight = time(0, tzinfo=floating)

class Event(Extension):
    trellis.attrs(
        base_start = None,          # None, or a datetime with a PyICU tzinfo
        base_duration = one_hour,   # a timedelta
        all_day = False,
        any_time = False
    )

    @trellis.compute
    def start(self):
        if not self.is_day:
            return self.base_start
        else:
            return datetime.combine(self.base_start.date(), midnight)

    @trellis.compute
    def duration(self):
        if not self.is_day:
            return self.base_duration
        else:
            return timedelta(self.base_duration.days + 1)

    @trellis.compute
    def end(self):
        return (self.start + self.duration if self.start is not None
                                          else None)

    @trellis.compute
    def is_day(self):
        return self.all_day or self.any_time

    @trellis.maintain
    def constraints(self):
        if self.base_start is not None and self.base_start.tzinfo is None:
            # this won't happen consistently; if base_start is already set,
            # trellis itself will raise a TypeError
            raise NaiveTimezoneError(repr(self.base_start))
        if not isinstance(self.base_duration, timedelta) or self.base_duration < zero_delta:
            raise BadDurationError(self.base_duration)

class NaiveTimezoneError(ConstraintError):
    cell_description = "base_start"

class BadDurationError(ConstraintError):
    cell_description = "base_duration"


# location
# transparency

# constraints on base_start and base_duration

# is_between
