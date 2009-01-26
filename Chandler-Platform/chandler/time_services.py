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
from datetime import datetime, date, time
import PyICU
from PyICU import ICUtzinfo
import dateutil

__all__ = ('getNow', 'timestamp', 'setNow', 'resetNow', 'nowTimestamp',
           'TimeZone', 'Scheduled', 'is_past_timestamp', 'is_past',
           'fromtimestamp',
           'force_datetime', 'olsonize', )

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
    return float(timegm(dt.utctimetuple()))

def fromtimestamp(dt):
    return datetime.fromtimestamp(dt, TimeZone.default)

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

def is_past(dt):
    return is_past_timestamp(timestamp(dt))

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



tzid_mapping = {}
# PyICU's tzids match whatever's in zoneinfo, which is essentially the Olson
# timezone database
olson_tzids = tuple(PyICU.TimeZone.createEnumeration())

def getICUInstance(name):
    """Return an ICUInstance, or None for false positive GMT results."""
    result = None
    if name is not None:
        result = ICUtzinfo.getInstance(name)
        if result is not None and \
            result.tzid == 'GMT' and \
            name != 'GMT':
            result = None

    return result


def olsonize(oldTzinfo, dt=None):
    """Turn oldTzinfo into an ICUtzinfo whose tzid matches something in the Olson db.
    """
    if (oldTzinfo == TimeZone.floating or
        (isinstance(oldTzinfo, ICUtzinfo) and oldTzinfo.tzid in olson_tzids)):
        # if tzid isn't in olson_tzids, ICU is using a bogus timezone, bug 11784
        return oldTzinfo
    elif oldTzinfo is None:
        icuTzinfo = None # Will patch to floating at the end
    else:
        year_start = 2007 if dt is None else dt.year
        year_end = year_start + 1

        # First, for dateutil.tz._tzicalvtz, we check
        # _tzid, since that's the displayable timezone
        # we want to use. This is kind of cheesy, but
        # works for now. This means that we're preferring
        # a tz like 'America/Chicago' over 'CST' or 'CDT'.
        tzical_tzid = getattr(oldTzinfo, '_tzid', None)
        icuTzinfo = getICUInstance(tzical_tzid)

        if tzical_tzid is not None:
            if tzical_tzid in tzid_mapping:
                # we've already calculated a tzinfo for this tzid
                icuTzinfo = tzid_mapping[tzical_tzid]

        if icuTzinfo is None:
            # special case UTC, because dateutil.tz.tzutc() doesn't have a TZID
            # and a VTIMEZONE isn't used for UTC
            if vobject.icalendar.tzinfo_eq(TimeZone.utc, oldTzinfo):
                icuTzinfo = TimeZone.utc

        # iterate over all PyICU timezones, return the first one whose
        # offsets and DST transitions match oldTzinfo.  This is painfully
        # inefficient, but we should do it only once per unrecognized timezone,
        # so optimization seems premature.
        backup = None
        if icuTzinfo is None:
            well_known = [] # XXX replace view-based well-known timezones with something else
            # canonicalTimeZone doesn't help us here, because our matching
            # criteria aren't as strict as PyICU's, so iterate over well known
            # timezones first
            for tzid in itertools.chain(well_known, olson_tzids):
                test_tzinfo = getICUInstance(tzid)
                # only test for the DST transitions for the year of the event
                # being converted.  This could be very wrong, but sadly it's
                # legal (and common practice) to serialize VTIMEZONEs with only
                # one year's DST transitions in it.  Some clients (notably iCal)
                # won't even bother to get that year's offset transitions right,
                # but in that case, we really can't pin down a timezone
                # definitively anyway (fortunately iCal uses standard zoneinfo
                # tzid strings, so getICUInstance above should just work)
                #
                # Also, don't choose timezones in Antarctica, when we're guessing
                # we might as well choose a location with human population > 100.
                if (not tzid.startswith('Antarctica') and
                    vobject.icalendar.tzinfo_eq(test_tzinfo, oldTzinfo,
                                               year_start, year_end)):
                    icuTzinfo = test_tzinfo
                    if tzical_tzid is not None:
                        tzid_mapping[tzical_tzid] = icuTzinfo
                    break
                # sadly, with the advent of the new US timezones, Exchange has
                # chosen to serialize US timezone DST transitions as if they
                # began in 1601, so we can't rely on dt.year.  So also try
                # 2007-2008, but treat any matches as a backup, they're
                # less reliable, since the VTIMEZONE may not define DST
                # transitions for 2007-2008.  Keep the first match, since we
                # process well known timezones first, and there's no way to
                # distinguish between, say, America/Detroit and America/New_York
                # in the 21st century.
                if backup is None:
                    if vobject.icalendar.tzinfo_eq(test_tzinfo, oldTzinfo,
                                                   2007, 2008):
                        backup = test_tzinfo
        if icuTzinfo is None and backup is not None:
            icuTzinfo = backup
            if tzical_tzid is not None:
                tzid_mapping[tzical_tzid] = icuTzinfo
    # if we have an unknown timezone, we'll return floating
    return TimeZone.floating if icuTzinfo is None else icuTzinfo

def force_datetime(dt, tzinfo=None):
    """
    If dt is a datetime, return dt, if a date, add time(0) and return.

    @param dt: The input.
    @type dt: C{datetime} or C{date}

    @return: A C{datetime}
    """
    if tzinfo is None:
        tzinfo = TimeZone.floating
    if type(dt) == datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tzinfo)
        else:
            return dt
    elif type(dt) == date:
        return datetime.combine(dt, time(0, tzinfo=tzinfo))
