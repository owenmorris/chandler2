#   Copyright (c) 2003-2007 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import peak.events.trellis as trellis
import peak.events.activity as activity
import peak.context as context

from calendar import timegm
from datetime import datetime
from PyICU import ICUtzinfo

__all__ = ('getNow', 'timestamp', 'setNow', 'resetNow', 'nowTimestamp',
           'TimeZone', 'Scheduled', 'is_past_timestamp')

def getNow(tz=None):
    """
    Return the current datetime, or the peak.events.activity.Time's
    simulated time.

    The timezone is set to ICUtzinfo.default if tz is None, otherwise
    timezone is set to tz.
    """
    if tz is None:
        tz = TimeZone.default
    return datetime.fromtimestamp(activity.Time._now, tz)

def timestamp(dt):
    # timegm returns an int number of seconds, which is probably good
    # enough for our purposes, but make tests expect a float, in
    # case we decide to replace it with something with a little more
    # resolution
    return float(timegm(dt.astimezone(TimeZone.utc).timetuple()))

def setNow(dt):
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=ICUtzinfo.default)

    # this ignores calendar.timegm (or time.mktime) range limits and
    # MAXYEAR/MINYEAR, since a now timestamp really shouldn't be outside those
    # ranges
    new_timestamp = timestamp(dt)

    activity.Time.auto_update = False
    activity.Time.advance(new_timestamp - activity.Time._now)

def resetNow():
    activity.Time.auto_update = True
    activity.Time.tick()

def nowTimestamp():
    """The number of seconds betwen the UTC epoch and now."""
    return activity.Time._now

def is_past_timestamp(stamp):
    return bool(activity.Time[stamp - nowTimestamp()])

class TimeZone(trellis.Component, context.Service):

    default = trellis.attr(ICUtzinfo.default)

    @trellis.perform
    def save_default(self):
        ICUtzinfo.setDefault(self.default)

    class _FloatingTZInfo(ICUtzinfo):
        def __init__(self): pass

        def utcoffset(self, dt):
            return TimeZone.default.utcoffset(dt)

        def dst(self, dt):
            return TimeZone.default.dst(dt)

        def __repr__(self):
            return "FloatingTZ(%r)" % (TimeZone.default,)

    floating = _FloatingTZInfo()

    def __getitem__(self, key):
        result = ICUtzinfo.getInstance(key)
        if result.tzid == 'GMT' and key != 'GMT':
            return None
        else:
            return result


    ### Helper constants
    pacific  = ICUtzinfo.getInstance("US/Pacific")
    eastern  = ICUtzinfo.getInstance("US/Eastern")
    utc      = ICUtzinfo.getInstance("UTC")


class Scheduled(trellis.Component):

    fire_date = trellis.attr(datetime.min.replace(tzinfo=TimeZone.floating))
    callback = trellis.attr(lambda reminder: None)

    @trellis.compute
    def _when_to_fire(self):
        # We want to convert fire_date into an activity.Time object.
        # To do that, subtract from datetime.now
        delta_seconds = timestamp(self.fire_date) - nowTimestamp()

        if delta_seconds >= 0:
            return activity.Time[delta_seconds]
        else:
            return False

    @trellis.perform # @@@ can't be a perform because we don't know if
                     # callback modifies the trellis or not
    def fire(self):
        if self._when_to_fire:
            self.callback(self)


