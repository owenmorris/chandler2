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

from datetime import datetime
from time import mktime
from PyICU import ICUtzinfo

now = None

def getNow(tz=None):
    """
    Return the current datetime, or the timemachine's pretend time.

    The timezone is set to ICUtzinfo.default if tz is None, otherwise
    timezone is set to tz.

    """
    if tz is None:
        tz = ICUtzinfo.default
    if now is None:
        return datetime.now(tz=tz)
    else:
        return now.astimezone(tz)

def setNow(dt):
    global now
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=ICUtzinfo.default)
    now = dt

def resetNow():
    setNow(None)

### Helper constants

pacific = ICUtzinfo.getInstance("US/Pacific")
eastern = ICUtzinfo.getInstance("US/Eastern")
utc = ICUtzinfo.getInstance("UTC")

# timestamp function

def nowTimestamp():
    """The number of seconds betwen the UTC epoch and now."""
    # ignoring time.mktime range limits and MAXYEAR/MINYEAR, since a
    # now timestamp really shouldn't be outside those ranges
    if now is None:
        return mktime(datetime.utcnow().timetuple())
    else:
        return mktime(now.astimezone(utc).timetuple())
