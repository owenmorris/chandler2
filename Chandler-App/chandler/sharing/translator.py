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

from chandler.core import Item, Collection, reset_cell_default, Extension
from chandler.event import Event
from chandler.recurrence import Recurrence, Occurrence, ModificationMask
from chandler.triage import Triage
from chandler.reminder import ReminderList

from itertools import chain
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
import colorsys

from vobject.icalendar import timedeltaToString, stringToDurations
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

class SharingMask(ModificationMask):
    def __init__(self, delegate):
        super(SharingMask, self).__init__(delegate, eim.Inherit)

def with_nochange(value, converter):
    """Convert value, as long as value isn't a special eim value."""
    if value in (eim.NoChange, eim.Inherit):
        return value
    return converter(value)

def datetimes_really_equal(dt1, dt2):
    return dt1.tzinfo == dt2.tzinfo and dt1 == dt2

def decimal_int(x):
    return Decimal(int(x))

def datetimeToDecimal(dt):
    return decimal_int(timestamp(dt))

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

def to_transparency(val):
    if val in emptyValues:
        return val
    val = str(val).upper()
    if val == 'FYI':
        val = 'CANCELLED'
    return val

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
        dtlist = tuple(dt_or_dtlist)

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
    item = event.item
    if not Recurrence.installed_on(item) or not Recurrence(item).rruleset:
        return (None, None, None, None)

    recur = Recurrence(item)
    if recur.frequency:
        rrule_dict = {}
        if recur.count:
            rrule_dict['COUNT'] = str(recur.count)
        elif recur.until:
            floating = event.start.tzinfo == TimeZone.floating
            until_tzinfo = TimeZone.floating if floating else TimeZone.utc
            until = recur.until.astimezone(until_tzinfo)
            rrule_dict['UNTIL'] = formatDateTime(until, False, False)

        for attr, tup in rrule_attr_dispatch.items():
            rule_key, ignore = tup
            value = getattr(recur, attr)
            if value:
                rrule_dict[rule_key] = str(value).upper()

        rrule = ";".join("=".join(tup) for tup in rrule_dict.items())
    else:
        rrule = None

    if len(recur.rdates) > 0:
        rdates = toICalendarDateTime(recur.rdates, event.is_day, False)
    else:
        rdates = None

    if len(recur.exdates) > 0:
        exdates = toICalendarDateTime(recur.exdates, event.is_day, False)
    else:
        exdates = None

    return rrule, None, rdates, exdates

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

def str_uuid_for(item):
    eim_wrapped = eim.EIM(item)
    if not eim.EIM.installed_on(item):
        eim_wrapped.add()
    return str(eim_wrapped.uuid)

def getAliasForItem(item_or_addon):
    item = getattr(item_or_addon, '_item', item_or_addon)
    if getattr(item, 'recurrence_id', None):
        recurrence_id = item.recurrence_id
        master = item.master
        tzinfo = recurrence_id.tzinfo
        # If recurrence_id isn't floating but the master is allDay or anyTime,
        # we have an off-rule modification, its recurrence-id shouldn't be
        # treated as date valued.
        date_value = Event(master).is_day and tzinfo == TimeZone.floating
        if tzinfo != TimeZone.floating:
            recurrence_id = recurrence_id.astimezone(TimeZone.utc)
        recurrence_id = formatDateTime(recurrence_id, date_value, date_value)
        return str_uuid_for(master) + ":" + recurrence_id
    else:
        return str_uuid_for(item)

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

def all_empty(obj, *attr_names):
    """True if obj.attr for all attr_names is in emptyValues."""
    for attr in attr_names:
        if getattr(obj, attr) not in emptyValues:
            return False
    return True

eim.add_converter(model.aliasableUUID, Item, getAliasForItem)
eim.add_converter(model.aliasableUUID, Collection, getAliasForItem)
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

    def getItemForAlias(self, alias):
        uuid, recurrence_id = splitUUID(alias)
        if not recurrence_id:
            return super(SharingTranslator, self).getItemForAlias(alias)

        master = eim.item_for_uuid(uuid)
        return Recurrence(master).get_occurrence(recurrence_id)

    def getAliasForItem(self, item):
        return getAliasForItem(item)


    def withItemForUUID(self, alias, itype=Item, **attrs):
        """Handle recurrence modification aliases."""
        uuid, recurrence_id = splitUUID(alias)
        if not recurrence_id:
            return super(SharingTranslator, self).withItemForUUID(uuid, itype, **attrs)

        occurrence = self.getItemForAlias(alias)
        master = self.getItemForAlias(uuid)
        master_recur = Recurrence(master)

        add_on = itype if itype is not Item else None

        # recurrence triage is a special case
        if add_on is Triage and 'manual' in attrs and 'manual_timestamp' in attrs:
            status, timestamp = attrs['manual'], attrs['manual_timestamp']
            if status is eim.Inherit:
                master_recur.clear_occurrence_triage(recurrence_id)
            else:
                master_recur.triage_occurrence(recurrence_id, timestamp, status)
            del attrs['manual']
            del attrs['manual_timestamp']

        for name, value in attrs.items():
            if value is eim.Inherit:
                occurrence.remove_change(add_on, name)
            elif value is not eim.NoChange:
                occurrence.modify(add_on, name, value)

        value = occurrence if add_on is None else add_on(occurrence)
        if issubclass(itype, Extension):
            if not itype.installed_on(occurrence) and attrs:
                value.add()

        def decorator(func):
            try:
                return func(value)
            except Exception, e:
                self.recordFailure(e)

        return decorator


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
        mask = SharingMask(item)

        triage = Triage(item)
        recurring = Recurrence.installed_on(item) and Recurrence(item).rruleset
        if recurring:
            encoded_triage = eim.NoChange
        elif triage.manual and triage.manual_timestamp:
            code = normalize_triage_code(triage.manual)
            manual_timestamp = -1 * triage.manual_timestamp
            encoded_triage = "%s %.2f 0" % (code, manual_timestamp)
        else:
            encoded_triage = eim.Inherit

        yield model.ItemRecord(
            item,                                        # uuid
            self.obfuscate(mask.title),                  # title
            encoded_triage,                              # triage
            with_nochange(mask.created, decimal_int),    # createdOn
            eim.NoChange,                                # hasBeenSent
            eim.NoChange,                                # needsReply
            eim.NoChange,                                # read
        )

        eim_wrapped = eim.EIM(item)

        yield model.NoteRecord(
            item,                                        # uuid
            self.obfuscate(mask.body),                   # body
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

        elif not getattr(item, 'recurrence_id', False):
            reminder = ReminderList(item).reminders[0]
            trigger = None
            if reminder.delta:
                trigger = timedeltaToString(reminder.delta)
            elif reminder.fixed_trigger:
                fixed = reminder.fixed_trigger.astimezone(TimeZone.utc)
                trigger = toICalendarDateTime(fixed, False)

            duration = eim.NoChange
            repeat = eim.NoChange
            description = getattr(reminder, 'description', None)
            if not description:
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

        self.withItemForUUID(record.uuid, Item,
            body=body
        )
        if record.uuid == getMasterAlias(record.uuid):
            self.withItemForUUID(record.uuid, eim.EIM,
                ical_uid = empty_as_inherit(record, 'icalUid'),
                ical_extra = empty_as_inherit(record, 'icalExtra')
            )

    # EventRecord -------------

    @model.EventRecord.importer
    def import_event(self, record):
        start, all_day, any_time = getTimeValues(record)
        uuid, recurrence_id = splitUUID(record.uuid)

        @self.withItemForUUID(record.uuid, Event,
            base_start=start,
            tzinfo=start.tzinfo if start not in emptyValues else eim.NoChange,
            all_day=all_day,
            base_any_time=any_time,
            base_duration=with_nochange(record.duration, fromICalendarDuration),
            location=record.location,
            base_transparency=with_nochange(record.status, from_transparency),
        )
        def do(event):
            if recurrence_id:
                return
            add_recurrence = not all_empty(record, 'rdate', 'rrule')
            recurrence_installed = Recurrence.installed_on(event.item)
            if not recurrence_installed and not add_recurrence:
                pass # no recurrence, nothing to do
            elif recurrence_id:
                pass # modification, no rules to set
            else:
                recur = Recurrence(event.item)
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

        event_mask = SharingMask(event)
        transparency = to_transparency(event_mask.base_transparency)

        if all_empty(event_mask, 'base_start', 'all_day', 'base_any_time', 'tzinfo'):
            start = eim.Inherit
        else:
            start = toICalendarDateTime(event.start, event.all_day, event.any_time)
        if all_empty(event_mask, 'base_duration', 'all_day', 'base_any_time'):
            duration = eim.Inherit
        else:
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

        rrule, exrule, rdates, exdates = getRecurrenceFields(event)

        yield model.EventRecord(
            event,                            # uuid
            start,                            # dtstart
            duration,                         # duration
            self.obfuscate(event.location),   # location
            rrule,                            # rrule
            exrule,                           # exrule
            rdates,                           # rdate
            exdates,                          # exdate
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
        # XXX need to deal with recurrence + reminders

        @self.withItemForUUID(record.uuid, ReminderList)
        def do(reminder_list):
            # Rather than simply leaving out a DisplayAlarmRecord, we're using
            # a trigger value of None to indicate there is no alarm:
            if record.trigger is None:
                if reminder_list.reminders:
                    reminder_list.reminders[:] = []
                return
            elif all_empty(record, 'trigger', 'description'):
                # no changes we understand
                return

            if reminder_list.reminders:
                reminder = reminder_list.reminders[0]
            else:
                reminder = reminder_list.add_reminder()

            # trigger may be a delta, or a datetime
            if record.trigger not in noChangeOrInherit:
                try:
                    val = fromICalendarDateTime(record.trigger)[0]
                    reminder.fixed_trigger = val.astimezone(TimeZone.default)
                except:
                    try:
                        reminder.delta = stringToDurations(record.trigger)[0]
                    except:
                        pass

            if (record.description not in noChangeOrInherit and
                record.description is not None):
                reminder.description = record.description

#             if record.repeat not in noChangeOrInherit:
#                 if record.repeat is None:
#                     reminder.repeat = 0
#                 else:
#                     reminder.repeat = record.repeat

    @model.DisplayAlarmRecord.deleter
    def delete_alarm(self, record):
        # XXX
#         item.reminders = []
        pass









class DumpTranslator(SharingTranslator):

    URI = "cid:dump-translator@osaf.us"
    version = 1
    description = u"Translator for Chandler items (PIM and non-PIM)"

    def exportItem(self, item):
        if isinstance(item, Occurrence):
            if not item.modification_recipe:
                return

        for record in super(DumpTranslator, self).exportItem(item):
            yield record


    # - - Collection  - - - - - - - - - - - - - - - - - - - - - - - - - - -
    @model.CollectionRecord.importer
    def import_collection(self, record):
        collection = eim.collection_for_name(record.uuid)
        if not isinstance(collection, Collection):
            raise TypeError("An Item was created instead of a Collection")

        # XXX need to assign color to appropriate SidebarEntries

    @eim.exporter(Collection)
    def export_collection(self, collection):
        red = green = blue = alpha = None

        yield model.ItemRecord(
            collection,                                  # uuid
            collection.title,                            # title
            eim.NoChange,                                # triage
            eim.NoChange,                                # createdOn
            eim.NoChange,                                # hasBeenSent
            eim.NoChange,                                # needsReply
            eim.NoChange,                                # read
        )

        yield model.CollectionRecord(
            collection,
            0, #mine
            red,
            green,
            blue,
            alpha,
            0 # checked
        )
        for record in self.export_collection_memberships(collection):
            yield record


    def export_collection_memberships(self, collection):
        eim_wrapped = eim.EIM(collection)
        collection_id = eim_wrapped.well_known_name or eim_wrapped.uuid

        for item in collection.items:
            yield model.CollectionMembershipRecord(
                collection_id,
                eim.EIM(item).uuid,
                eim.NoChange,
                )

    @model.CollectionMembershipRecord.importer
    def import_collectionmembership(self, record):

        # Don't add non-masters to collections:
        if record.itemUUID != getMasterAlias(record.itemUUID):
            return

        collection = eim.collection_for_name(record.collectionID)
        collection.add(eim.item_for_uuid(record.itemUUID))



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
