#   Copyright (c) 2006-2008 Open Source Applications Foundation
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

from chandler.sharing import (
    eim, eimml, legacy_model as model
)

from chandler.sharing.utility import (
    splitUUID, fromICalendarDateTime, getMasterAlias
)

from chandler.core import Item, Collection, reset_cell_default
from chandler.event import Event
from chandler.recurrence import Recurrence
from chandler.triage import Triage
from chandler.reminder import ReminderList

from itertools import chain
import os
from datetime import datetime, date, timedelta
from decimal import Decimal

from vobject.icalendar import (RecurringComponent, VEvent, timedeltaToString,
                               stringToDurations)
from chandler.time_services import getNow, TimeZone, timestamp, olsonize

__all__ = [
    'SharingTranslator',
    'DumpTranslator',
    'fromICalendarDuration',
    'toICalendarDateTime',
]

oneDay = timedelta(1)

noChangeOrInherit = (eim.NoChange, eim.Inherit)
emptyValues = (eim.NoChange, eim.Inherit, None)

def with_nochange(value, converter):
    """Convert value, as long as value isn't a special eim value."""
    if value in (eim.NoChange, eim.Inherit):
        return value
    return converter(value)

def datetimes_really_equal(dt1, dt2):
    return dt1.tzinfo == dt2.tzinfo and dt1 == dt2

def datetimeToDecimal(dt):
    return Decimal(int(timestamp(dt)))

def decimalToDatetime(decimal):
    return datetime.fromtimestamp(decimal, TimeZone.default)

def normalize_triage_code(code):
    """Cosmo expects triage status to be 100, 200, or 300."""
    code = max(100, min(300, int(code)))
    return (code // 100) * 100

### Event field conversion functions
# incomplete

def from_transparency(val):
    out = val.lower()
    if out == 'cancelled':
        out = 'fyi'
    elif out not in ('confirmed', 'tentative'):
        out = 'confirmed'
    return out

def fromICalendarDuration(text):
    return stringToDurations(text)[0]

def getTimeValues(record):
    """
    Extract start time and allDay/anyTime from a record.
    """
    dtstart  = record.dtstart
    # tolerate empty dtstart, treat it as Inherit, bug 9849
    if dtstart is None:
        dtstart = eim.Inherit
    start = None
    if dtstart not in noChangeOrInherit:
        start, allDay, anyTime = fromICalendarDateTime(dtstart)
    else:
        allDay = anyTime = start = dtstart
    # anyTime should be set to True if allDay is true, bug 9041
    anyTime = anyTime or allDay
    return (start, allDay, anyTime)

dateFormat = "%04d%02d%02d"
datetimeFormat = "%04d%02d%02dT%02d%02d%02d"
tzidFormat = ";TZID=%s"
allDayParameter = ";VALUE=DATE"
timedParameter  = ";VALUE=DATE-TIME"
anyTimeParameter = ";X-OSAF-ANYTIME=TRUE"

def formatDateTime(dt, allDay, anyTime):
    """Take a date or datetime, format it appropriately for EIM"""
    if allDay or anyTime:
        return dateFormat % dt.timetuple()[:3]
    else:
        base = datetimeFormat % dt.timetuple()[:6]
        if dt.tzinfo == TimeZone.utc:
            return base + 'Z'
        else:
            return base

def toICalendarDateTime(dt_or_dtlist, allDay, anyTime=False):
    if isinstance(dt_or_dtlist, datetime):
        dtlist = [dt_or_dtlist]
    else:
        dtlist = dt_or_dtlist

    output = ''
    if allDay or anyTime:
        output += allDayParameter
        if anyTime and not allDay:
            output += anyTimeParameter
    else:
        isUTC = dtlist[0].tzinfo == TimeZone.utc
        output += timedParameter
        tzinfo = olsonize(dtlist[0].tzinfo)
        if not isUTC and tzinfo != TimeZone.floating:
            output += tzidFormat % tzinfo.tzid

    output += ':'
    output += ','.join(formatDateTime(dt, allDay, anyTime)
                       for dt in dtlist)
    return output


def getRecurrenceFields(event):
    """
    Take an event, return EIM strings for rrule, exrule, rdate, exdate, any
    or all of which may be None.

    """
    if event.occurrenceFor is not None:
        return (eim.Inherit, eim.Inherit, eim.Inherit, eim.Inherit)
    elif event.rruleset is None:
        return (None, None, None, None)

    vobject_event = RecurringComponent()
    vobject_event.behavior = VEvent
    start = event.startTime
    if event.allDay or event.anyTime:
        start = start.date()
    elif start.tzinfo is TimeZone.floating:
        start = start.replace(tzinfo=None)
    vobject_event.add('dtstart').value = start
    vobject_event.rruleset = event.createDateUtilFromRule(False, True, False)

    if hasattr(vobject_event, 'rrule'):
        rrules = vobject_event.rrule_list
        rrule = ':'.join(obj.serialize(lineLength=1000)[6:].strip() for obj in rrules)
    else:
        rrule = None

    if hasattr(vobject_event, 'exrule'):
        exrules = vobject_event.exrule_list
        exrule = ':'.join(obj.serialize(lineLength=1000)[7:].strip() for obj in exrules)
    else:
        exrule = None

    rdates = getattr(event.rruleset, 'rdates', [])
    if len(rdates) > 0:
        rdate = toICalendarDateTime(rdates, event.allDay, event.anyTime)
    else:
        rdate = None

    exdates = getattr(event.rruleset, 'exdates', [])
    if len(exdates) > 0:
        exdate = toICalendarDateTime(exdates, event.allDay, event.anyTime)
    else:
        exdate = None

    return rrule, exrule, rdate, exdate

def empty_as_inherit(item, attr):
    value = getattr(item, attr)
    if not value:
        return eim.Inherit
    return value

def lower(s):
    return s.lower()

def no_op(x):
    return x

rrule_attr_dispatch = { # RFC2445 name  # eim->model
    'frequency' :       ('FREQ',        lower),
    'byday':            ('BYDAY',       no_op),
}

def getAliasForItem(item_or_addon):
    item = getattr(item_or_addon, '_item', item_or_addon)
    if getattr(item, 'recurrence_id', None):
        master = item.master
        tzinfo = item.recurrence_id.tzinfo
        # If recurrence_id isn't floating but the master is allDay or anyTime,
        # we have an off-rule modification, its recurrence-id shouldn't be
        # treated as date valued.
        date_value = Event(master).is_day and tzinfo == TimeZone.floating
        if tzinfo != TimeZone.floating:
            recurrence_id = recurrence_id.astimezone(TimeZone.utc)
        recurrence_id = formatDateTime(recurrence_id, dateValue, dateValue)
        return str(eim.EIM(master).uuid) + ":" + recurrence_id
    else:
        return str(eim.EIM(item).uuid)

def lipsum(length):
    # Return some text that has properties real text would have.
    corpus = "Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
    if length <= len(corpus):
        return corpus[:length]
    # Need to generate some additional stuff...
    ret = corpus
    words = corpus.split()
    import random
    shuffler = random.Random(1) # fixed seed on purpose
    while True:
        shuffler.shuffle(words)
        ret += os.linesep + ' '.join(words)
        if len(ret) >= length:
            return ret[:length]



eim.add_converter(model.aliasableUUID, Item, getAliasForItem)
# eim.add_converter(model.aliasableUUID, pim.Stamp, getAliasForItem)


# Hopefully someday we will be able to remove the following converters:

# Cosmo will generate a value of None even if Chandler hasn't provided a
# value for event status, so treat None as NoChange
eim.add_converter(model.EventRecord.status, type(None), lambda x: eim.NoChange)

# Cosmo will generate a value of empty string even if Chandler hasn't provided
# a value for triage, so treat empty string as NoChange
def emptyToNoChange(s):
    return s if s else eim.NoChange
eim.add_converter(model.ItemRecord.triage, str, emptyToNoChange)
eim.add_converter(model.ItemRecord.triage, unicode, emptyToNoChange)

# Cosmo will generate a value of None for a zero-length duration, but Chandler
# uses "PT0S"
eim.add_converter(model.EventRecord.duration, type(None), lambda x: "PT0S")



class SharingTranslator(eim.Translator):

    URI = "cid:app-translator@osaf.us"
    version = 1
    description = u"Translator for Chandler2 items"

    obfuscation = False

    def obfuscate(self, text):
        if text in (eim.Inherit, eim.NoChange):
            return text

        if text and getattr(self, "obfuscation", False):
            return lipsum(len(text))
        else:
            return text

    def getUUIDForAlias(self, alias):
        if ':' not in alias:
            return alias

        uuid, recurrenceID = splitUUID(alias)

        # find the occurrence and return itsUUID
        master = eim.get_item_for_uuid(uuid)
        if master is not None and pim.has_stamp(master, pim.EventStamp):
            masterEvent = pim.EventStamp(master)
            occurrence = masterEvent.getExistingOccurrence(recurrenceID)
            if occurrence is not None:
                if self.getAliasForItem(occurrence) != alias:
                    # don't get fooled by getExistingOccurrence( ) which
                    # thinks that a floating tz matches a non-floater
                    # (related to bug 9207)
                    return None
                return occurrence.itsItem.itsUUID.str16()

        return None


    def getAliasForItem(self, item):
        return getAliasForItem(item)



    # ItemRecord -------------

    @model.ItemRecord.importer
    def import_item(self, record):
        title = record.title if record.title is not None else eim.Inherit
        created = record.createdOn
        created = float(created) if created not in emptyValues else eim.NoChange
        self.withItemForUUID(record.uuid, Item,
            title=title,
            created=created,
        )

        manual = None
        if record.triage == eim.Inherit:
            manual = manual_timestamp = eim.Inherit
        elif record.triage != "" and record.triage not in emptyValues:
            code, timestamp, auto = record.triage.split(" ")
            manual = float(code)
            manual_timestamp = -1.0*float(timestamp)

        if manual is not None:
            self.withItemForUUID(record.uuid, Triage,
                manual=manual,
                manual_timestamp=manual_timestamp
            )


    @eim.exporter(Item)
    def export_item(self, item):
        triage = Triage(item)
        if triage.manual and triage.manual_timestamp:
            code = normalize_triage_code(triage.manual)
            manual_timestamp = -1 * triage.manual_timestamp
            encoded_triage = "%s %.2f 0" % (code, manual_timestamp)
        else:
            encoded_triage = eim.Inherit

        yield model.ItemRecord(
            item,                            # uuid
            self.obfuscate(item.title),      # title
            encoded_triage,                  # triage
            Decimal(int(item.created)),      # createdOn
            eim.NoChange,                    # hasBeenSent
            eim.NoChange,                    # needsReply
            eim.NoChange,                    # read
        )

        eim_wrapped = eim.EIM(item)

        yield model.NoteRecord(
            item,                                        # uuid
            self.obfuscate(item.body),                   # body
            empty_as_inherit(eim_wrapped, 'ical_uid'),   # icalUid
            eim.Inherit,                                 # icalendarProperties
            eim.Inherit,                                 # icalendarParameters
            empty_as_inherit(eim_wrapped, 'ical_extra')  # icalendarExtra
        )


        if not ReminderList(item).reminders:
            description = None
            trigger = None
            duration = None
            repeat = None

        elif reminder.reminderItem is item: # this is our reminder
            trigger = None
            if reminder.hasLocalAttributeValue('delta'):
                trigger = timedeltaToString(reminder.delta)
            elif reminder.hasLocalAttributeValue('absoluteTime'):
                # iCalendar Triggers are supposed to be expressed in UTC;
                # EIM may not require that but might as well be consistent
                reminderTime = reminder.absoluteTime.astimezone(TimeZone.utc)
                trigger = toICalendarDateTime(reminderTime, False)

            if reminder.duration:
                duration = timedeltaToString(reminder.duration)
            else:
                duration = None

            if reminder.repeat:
                repeat = reminder.repeat
            else:
                repeat = None

            description = getattr(reminder, 'description', None)
            if description is None:
                description = "Event Reminder"

        else: # we've inherited this reminder
            description = eim.Inherit
            trigger = eim.Inherit
            duration = eim.Inherit
            repeat = eim.Inherit

        yield model.DisplayAlarmRecord(
            item,
            description,
            trigger,
            duration,
            repeat,
        )


    # NoteRecord -------------

    @model.NoteRecord.importer
    def import_note(self, record):
        body = record.body if record.body is not None else eim.Inherit
        if record.uuid != getMasterAlias(record.uuid):
            # An occurrence
            ical_uid = eim.Inherit
        else:
            ical_uid = record.icalUid
            if ical_uid is None:
                ical_uid = eim.NoChange

        ical_extra = record.icalExtra
        ical_extra = ical_extra if ical_extra is not None else eim.NoChange

        self.withItemForUUID(record.uuid, Item,
            body=body
        )
        self.withItemForUUID(record.uuid, eim.EIM,
            ical_uid = ical_uid,
            ical_extra = ical_extra
        )

    # EventRecord -------------

    @model.EventRecord.importer
    def import_event(self, record):
        start, all_day, any_time = getTimeValues(record)
        uuid, recurrence_id = splitUUID(record.uuid)

        @self.withItemForUUID(record.uuid, Event,
            base_start=start,
            tzinfo=start.tzinfo,
            all_day=all_day,
            base_any_time=any_time,
            base_duration=with_nochange(record.duration, fromICalendarDuration),
            location=record.location,
            base_transparency=with_nochange(record.status, from_transparency),
        )
        def do(event):
            add_recurrence = not (record.rdate in emptyValues and record.rrule in emptyValues)
            recurrence_installed = Recurrence.installed_on(event._item)
            if not recurrence_installed and not add_recurrence:
                pass # no recurrence, nothing to do
            elif recurrence_id:
                pass # modification, no rules to set
            else:
                recur = Recurrence(event._item)
                if add_recurrence and not recurrence_installed:
                    recur.add()
                for datetype in 'rdate', 'exdate':
                    record_field = getattr(record, datetype)
                    if record_field is not eim.NoChange:
                        if record_field is None:
                            dates = ()
                        else:
                            dates = fromICalendarDateTime(record_field, multivalued=True)[0]
                        date_set = getattr(recur, datetype + 's')
                        if date_set.symmetric_difference(dates):
                            date_set.clear()
                            date_set.update(dates)

                if record.rrule is not eim.NoChange:
                    if record.rrule in emptyValues:
                        recur.frequency = None
                    else:
                        # EIM serializes multiple RRULEs colon separated,
                        # ignoring all but the first for now.
                        rule_dict = {}
                        first_rule, sep, later_rules = record.rrule.upper().partition(':')
                        for key_value_string in first_rule.split(';'):
                            key, sep, value = key_value_string.partition('=')
                            rule_dict[key] = value

                        # count and until are mutually exclusive, special case
                        if 'COUNT' in rule_dict:
                            recur.count = int(rule_dict['COUNT'])
                        elif 'UNTIL' in rule_dict:
                            recur.until = fromICalendarDateTime(rule_dict['UNTIL'])[0]
                        else:
                            recur.until = None

                        for attr, tup in rrule_attr_dispatch.items():
                            rule_key, convert = tup
                            if rule_key in rule_dict:
                                setattr(recur, attr, convert(rule_dict[rule_key]))
                            else:
                                reset_cell_default(recur, attr)

                if not recur.frequency and not recur.rdates:
                    if recurrence_installed:
                        recur.remove()


    @eim.exporter(Event)
    def export_event(self, event):

        transparency = str(event.transparency).upper()
        if transparency == "FYI":
            transparency = "CANCELLED"

        start = toICalendarDateTime(event.start, event.all_day, event.any_time)
        duration = timedeltaToString(event.duration)

#         lastPast = eim.NoChange
#         if event.occurrenceFor is None and event.rruleset is not None:
#             rruleset = event.createDateUtilFromRule()
#             lastPast = rruleset.before(getNow(TimeZone.default))
#             if lastPast is not None:
#                 # convert to UTC if not floating
#                 if lastPast.tzinfo != TimeZone.floating:
#                     lastPast = lastPast.astimezone(TimeZone.utc)
#                 lastPast = toICalendarDateTime(lastPast, event.allDay,
#                                                event.anyTime)

        rrule = exrule = rdate = exdate = None

        yield model.EventRecord(
            event,                            # uuid
            start,                            # dtstart
            duration,                         # duration
            self.obfuscate(event.location),   # location
            rrule,                            # rrule
            exrule,                           # exrule
            rdate,                            # rdate
            exdate,                           # exdate
            transparency,                     # status
            eim.NoChange,                     # lastPastOccurrence
        )



    @model.EventRecord.deleter
    def delete_event(self, record):
        uuid, recurrence_id = splitUUID(record.uuid)
        item = eim.get_item_for_uuid(uuid)
        if item is not None and item.isLive() and pim.has_stamp(item,
            EventStamp):
            if recurrence_id:
                occurrence = EventStamp(item).getRecurrenceID(recurrence_id)
                occurrence.unmodify(partial=True)
            else:
                EventStamp(item).remove()

    # DisplayAlarmRecord -------------

    @model.DisplayAlarmRecord.importer
    def import_alarm(self, record):

        @self.withItemForUUID(record.uuid, pim.ContentItem)
        def do(item):
            # Rather than simply leaving out a DisplayAlarmRecord, we're using
            # a trigger value of None to indicate there is no alarm:
            if record.trigger is None:
                item.reminders = []

            elif record.trigger not in noChangeOrInherit:
                # trigger translates to either a pim.Reminder (if a date(time),
                # or a pim.RelativeReminder (if a timedelta).
                kw = dict(itsView=item.itsView)
                reminderFactory = None

                try:
                    val = fromICalendarDateTime(record.trigger)[0]
                    val = val.astimezone(TimeZone.default)
                except:
                    pass
                else:
                    reminderFactory = pim.Reminder
                    kw.update(absoluteTime=val)

                if reminderFactory is None:
                    try:
                        val = stringToDurations(record.trigger)[0]
                    except:
                        pass
                    else:
                        reminderFactory = pim.RelativeReminder
                        kw.update(delta=val)

                if reminderFactory is not None:
                    item.reminders = [reminderFactory(**kw)]


            reminder = item.getUserReminder()
            if reminder is not None:

                if (record.description not in noChangeOrInherit and
                    record.description is not None):
                    reminder.description = record.description

                if record.duration not in noChangeOrInherit:
                    if record.duration is None:
                        delattr(reminder, 'duration') # has a defaultValue
                    else:
                        reminder.duration = stringToDurations(record.duration)[0]

                if record.repeat not in noChangeOrInherit:
                    if record.repeat is None:
                        reminder.repeat = 0
                    else:
                        reminder.repeat = record.repeat

    @model.DisplayAlarmRecord.deleter
    def delete_alarm(self, record):
        item = eim.get_item_for_uuid(self.getUUIDForAlias(record.uuid))
        item.reminders = []






class DumpTranslator(SharingTranslator):

    URI = "cid:dump-translator@osaf.us"
    version = 1
    description = u"Translator for Chandler items (PIM and non-PIM)"


    # Mapping for well-known names to/from their current repository path
    path_to_name = {
        "//parcels/osaf/app/sidebarCollection" : "@sidebar",
    }
    name_to_path = dict([[v, k] for k, v in path_to_name.items()])


    def exportItem(self, item):
        """
        Export an item and its stamps, if any.

        Recurrence changes:
        - Avoid exporting occurrences unless they're modifications.
        - Don't serialize recurrence rule items

        """

        if not isinstance(item, self.approvedClasses):
            return

        elif isinstance(item, Occurrence):
            if not EventStamp(item).modificationFor:
                return

        for record in super(DumpTranslator, self).exportItem(item):
            yield record


    # - - Collection  - - - - - - - - - - - - - - - - - - - - - - - - - - -
    @model.CollectionRecord.importer
    def import_collection(self, record):
        @self.withItemForUUID(record.uuid, pim.SmartCollection)
        def add_source(collection):
            if record.mine == 1:
                schema.ns('osaf.pim', self.rv).mine.addSource(collection)
            if record.colorRed is not None:
                UserCollection(collection).color = ColorType(
                    record.colorRed, record.colorGreen, record.colorBlue,
                    record.colorAlpha
                )
            UserCollection(collection).checked = bool(record.checked)

    @eim.exporter(Collection)
    def export_collection(self, collection):
        try:
            color = UserCollection (collection).color
            red = color.red
            green = color.green
            blue = color.blue
            alpha = color.alpha
        except AttributeError: # collection has no color
            red = green = blue = alpha = None

        yield model.CollectionRecord(
            collection,
            int (collection in schema.ns('osaf.pim', self.rv).mine.sources),
            red,
            green,
            blue,
            alpha,
            int(UserCollection(collection).checked)
        )
        for record in self.export_collection_memberships (collection):
            yield record


    def export_collection_memberships(self, collection):
        index = 0

        # For well-known collections, use their well-known name rather than
        # their UUID
        collectionID = self.path_to_name.get(str(collection.itsPath),
            collection.itsUUID.str16())

        for item in collection.inclusions:
            # We iterate inclusions directly because we want the proper
            # trash behavior to get reloaded -- we want to keep track that
            # a trashed item was in the inclusions of a collection.
            # By default we don't include items that are in
            # //parcels since they are not created by the user


            # For items in the sidebar, if they're not of an approved class
            # then skip them.
            # TODO: When we have a better solution for filtering plugin data
            # this check should be removed:
            if (collectionID == "@sidebar" and
                not isinstance(item, self.approvedClasses)):
                continue


            if (not str(item.itsPath).startswith("//parcels") and
                not isinstance(item, Occurrence)):
                yield model.CollectionMembershipRecord(
                    collectionID,
                    item.itsUUID,
                    index,
                )
                index = index + 1

    @model.CollectionMembershipRecord.importer
    def import_collectionmembership(self, record):

        # Don't add non-masters to collections:
        if record.itemUUID != getMasterAlias(record.itemUUID):
            return

        id = record.collectionID

        # Map old hard-coded sidebar UUID to its well-known name
        if id == "3c58ae62-d8d6-11db-86bb-0017f2ca1708":
            id = "@sidebar"

        id = self.name_to_path.get(id, id)

        if id.startswith("//"):
            collection = self.rv.findPath(id)
            # We're preserving order of items in collections
            # assert (self.indexIsInSequence (collection, record.index))
            @self.withItemForUUID(record.itemUUID, pim.ContentItem)
            def do(item):
                collection.add(item)

        else:
            # Assume that non-existent collections should be created as
            # SmartCollections; otherwise don't upgrade from ContentCollection
            # base
            collectionType = (
                pim.SmartCollection if eim.get_item_for_uuid(id) is None
                else pim.ContentCollection
            )
            @self.withItemForUUID(id, collectionType)
            def do(collection):
                # We're preserving order of items in collections
                # assert (self.indexIsInSequence (collection, record.index))
                @self.withItemForUUID(record.itemUUID, pim.ContentItem)
                def do(item):
                    collection.add(item)


    @model.DashboardMembershipRecord.importer
    def import_dashboard_membership(self, record):

        # Don't add non-masters to collections:
        if record.itemUUID != getMasterAlias(record.itemUUID):
            return

        @self.withItemForUUID(record.itemUUID, pim.ContentItem)
        def do(item):
            dashboard = schema.ns("osaf.pim", self.rv).allCollection
            dashboard.add(item)


    @model.PrefTimezonesRecord.importer
    def import_preftimezones(self, record):

        pref = schema.ns('osaf.pim', self.rv).TimezonePrefs
        pref.showUI = bool(record.showUI)
        pref.showPrompt = bool(record.showPrompt)

        tzitem = TimeZone.TimeZoneInfo.get(self.rv)
        tzitem.default = self.rv.tzinfo.getInstance(record.default)
        tzitem.wellKnownIDs = record.wellKnownIDs.split(',')

    # Called from finishExport( )
    def export_preftimezones(self):

        pref = schema.ns('osaf.pim', self.rv).TimezonePrefs
        tzitem = TimeZone.TimeZoneInfo.get(self.rv)
        yield model.PrefTimezonesRecord(
            pref.showUI,
            pref.showPrompt,
            olsonize(tzitem.default).tzid,
            ",".join(tzitem.wellKnownIDs)
        )

# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# Formatters for conflicts (not sure where these should live yet)

_ = lambda x: x

# don't use context sensitive formatters for special values like inherit
# global_formatters[Inherit] = lambda f, v: _('Inherit')

triage_code_map = {
    "100" : _(u'Now'),
    "200" : _(u'Later'),
    "300" : _(u'Done'),
}

@eim.format_field.when_object(model.ItemRecord.triage)
def format_item_triage(field, value):
    try:
        code, timestamp, auto = value.split(" ")
    except AttributeError:
        return _(u'Unknown')
    return triage_code_map.get(code, _(u'Unknown'))

event_status_map = {
    'cancelled' : _(u'FYI'),
    'confirmed' : _(u'Confirmed'),
    'tentative' : _(u'Tentative'),
}
@eim.format_field.when_object(model.EventRecord.status)
def format_event_status(field, value):
    return event_status_map.get(value.lower(), _(u'Unknown'))

@eim.format_field.when_object(model.EventRecord.dtstart)
def format_event_dtstart(field, value):
    start, allDay, anyTime = fromICalendarDateTime(value)
    s = str(start)
    if allDay:
        s = "%s (all day)" % s
    if anyTime:
        s = "%s (any time)" % s
    return s

@eim.format_field.when_object(model.EventRecord.duration)
def format_event_duration(field, value):
    duration = fromICalendarDuration(value)
    return "%s (hh:mm:ss)" % duration
