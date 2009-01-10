#   Copyright (c) 2003-2008 Open Source Applications Foundation
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

import datetime
import logging

from dateutil.rrule import rrulestr
import dateutil
from vobject.icalendar import (DateOrDateTimeBehavior, MultiDateBehavior)
from vobject.base import textLineToContentLine
from chandler.time_services import TimeZone


logger = logging.getLogger(__name__)

def getDateUtilRRuleSet(field, value, dtstart):
    """
    Turn EIM recurrence fields into a dateutil rruleset.

    dtstart is required to deal with count successfully.
    """
    ical_string = ""
    if value.startswith(';'):
        # remove parameters, dateutil fails when it sees them
        value = value.partition(':')[2]
    # EIM uses a colon to concatenate RRULEs, which isn't iCalendar
    for element in value.split(':'):
        ical_string += field
        ical_string += ':'
        ical_string += element
        ical_string += "\r\n"
    # dateutil chokes on unicode, pass in a string
    return rrulestr(str(ical_string), forceset=True, dtstart=dtstart)

du_utc = dateutil.tz.tzutc()

def fromICalendarDateTime(text, multivalued=False):
    prefix = 'dtstart' # arbitrary
    if not text.startswith(';') and not text.startswith(':'):
        # no parameters
        prefix += ':'
    line = textLineToContentLine(prefix + text)
    if multivalued:
        line.behavior = MultiDateBehavior
    else:
        line.behavior = DateOrDateTimeBehavior
    line.transformToNative()
    anyTime = getattr(line, 'x_osaf_anytime_param', "").upper() == 'TRUE'
    allDay = False
    start = line.value
    if not multivalued:
        start = [start]
    if type(start[0]) == datetime.date:
        allDay = not anyTime
        start = [TimeZone.forceToDateTime(dt) for dt in start]
    else:
        tzid = line.params.get('X-VOBJ-ORIGINAL-TZID')
        if tzid is None:
            # RDATEs and EXDATEs won't have an X-VOBJ-ORIGINAL-TZID
            tzid = getattr(line, 'tzid_param', None)
        if start[0].tzinfo == du_utc:
            tzinfo = TimeZone.utc
        elif tzid is None:
            tzinfo = TimeZone.floating
        else:
            # this parameter was broken, fixed in vobject 0.6.6, handle either
            # a string or take the first element of a list
            if not isinstance(tzid, basestring):
                tzid = tzid[0]
            tzinfo = TimeZone[tzid]
        start = [dt.replace(tzinfo=tzinfo) for dt in start]
    if not multivalued:
        start = start[0]
    return (start, allDay, anyTime)

def getMasterAlias(alias):
    """Return the portion of the alias before the colon."""
    master, sep, dt = alias.partition(':')
    return master

def splitUUID(recurrence_aware_uuid):
    """
    Split an EIM recurrence UUID.

    Return the tuple (UUID, recurrenceID or None).  UUID will be a string,
    recurrenceID will be a datetime or None.
    """
    pseudo_uuid = str(recurrence_aware_uuid)
    # tolerate old-style, double-colon pseudo-uuids
    position = pseudo_uuid.find('::')
    if position != -1:
        return (pseudo_uuid[:position],
                fromICalendarDateTime(pseudo_uuid[position + 2:])[0])
    position = pseudo_uuid.find(':')
    if position != -1:
        return (pseudo_uuid[:position],
                fromICalendarDateTime(pseudo_uuid[position:])[0])
    return (pseudo_uuid, None)

# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

