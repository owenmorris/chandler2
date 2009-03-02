from peak.events import collections, trellis
from peak.util import addons, plugins
from chandler.event import Event
from chandler.starred import Starred
from chandler.reminder import ReminderList
from chandler.triage import Triage, TriagePosition, NOW
from chandler.time_services import is_past, timestamp, fromtimestamp
import chandler.core as core
import chandler.wxui.image as image

class AppDashboardEntry(addons.AddOn, trellis.Component):
    @trellis.make
    def subject(self):
        return None

    def __init__(self, subject, **kw):
        kw.update(subject=subject)
        trellis.Component.__init__(self, **kw)

    @trellis.compute
    def _item(self):
        return self.subject.subject_item

    @trellis.compute
    def triage_status(self):
        return Triage(self._item).calculated

    @trellis.compute
    def triage_position(self):
        return TriagePosition(self._item).position

    @trellis.compute
    def triage_section(self):
        return TriagePosition(self._item).triage_section

    @trellis.compute
    def is_event(self):
        return Event.installed_on(self._item)

    @trellis.compute
    def is_starred(self):
        return Starred.installed_on(self._item)

    @trellis.compute
    def _reminder(self):
        for reminder in ReminderList(self._item).reminders:
            return reminder

    @trellis.compute
    def _when_source(self):
        """
        Source for displayed date is either fixed_reminder trigger or
        event start.  If neither is available, fall back to created.

        The first-future, or last-past, user-defined date is used.

        """
        past = []
        future = []
        if self._reminder and self._reminder.fixed_trigger:
            fixed_trigger = self._reminder.fixed_trigger
            l = past if is_past(fixed_trigger) else future
            l.append((fixed_trigger, 'reminder'))
        if self.is_event:
            event_start = Event(self._item).start
            if event_start:
                l = past if is_past(event_start) else future
                l.append((event_start, 'event'))
        past.sort()
        future.sort()
        if future:
            return future[0][1]
        elif past:
            return past[-1][1]
        return 'created'

    @trellis.compute
    def when(self):
        if self._when_source == 'event':
            return Event(self._item).start
        elif self._when_source == 'reminder':
            return self._reminder.trigger
        else:
            return fromtimestamp(self._item.created)

    @trellis.compute
    def reminder_scheduled(self):
        if not self._reminder or not self._reminder.trigger:
            return False
        else:
            return not is_past(self._reminder.trigger)

    @trellis.compute
    def event_reminder_combined(self):
        """
        'reminder' if there's a future reminder, or if there was a
        past reminder and there's no event information.

        """
        if self.reminder_scheduled:
            return "reminder"
        elif self.is_event:
            return "event"
        elif self._reminder and self._reminder.trigger:
            return "reminder"
        else:
            return ""


plugins.Hook('chandler.domain.dashboard_entry_addon').register(AppDashboardEntry)

class AppEntryAggregate(core.AggregatedSet):
    """
    AggregatedSet that aggregates all AppDashboardEntry objects
    corresponding to the Items in its input.
    """

    def get_values(self, item):
        return tuple(AppDashboardEntry(subject) for subject in item.dashboard_entries)

class AppColumn(core.TableColumn):
    app_attr = trellis.attr(None)

    def __repr__(self):
        return '<%s "%s" (%s)>' % (self.__class__.__name__, self.label,
                                   self.app_attr)

    def get_value(self, entry):
        return getattr(entry, self.app_attr)
    
    @trellis.compute
    def bitmap(self):
        name = self.hints.get('header_icon')
        if name:
            return image.get_image(name, "Chandler_App")
        else:
            return None

class TriageColumn(AppColumn):
    label = trellis.attr('Triage')
    app_attr = trellis.attr('triage_status')

    def sort_key(self, entry):
        return entry.triage_section, entry.triage_position

class Dashboard(core.Table):
    @trellis.maintain
    def star_column(self):
        return AppColumn(scope=self, label=u'*', app_attr='is_starred',
                         hints={'width': 20, 'header_icon':'ColHStarred.png',
                                'type': 'DashboardStar'})

    @trellis.maintain
    def title_column(self):
        return core.TableColumn(scope=self, label='Title',
                                get_value=lambda entry:entry.subject.what,
                                hints={'width':160, 'scalable':True})

    @trellis.maintain
    def event_reminder_column(self):
        return AppColumn(scope=self, label='(( ))',
                         app_attr='event_reminder_combined',
                         hints={'width': 36, 'type': 'DashboardReminder',
                                'header_icon':'ColHEventReminder.png'})

    @trellis.maintain
    def when_column(self):
        return AppColumn(scope=self, label='Date', app_attr='when',
                         hints={'width':120})

    @trellis.maintain
    def triage_column(self):
        return TriageColumn(scope=self, hints={'width': 60,
                                        'header_icon':'ColHTriage.png'})


    @trellis.make
    def columns(self):
        return trellis.List([self.star_column, self.title_column,
                             self.event_reminder_column, self.when_column,
                             self.triage_column])

    @trellis.make
    def hints(self):
        return { 'column_headers': True }


import chandler.wxui.table as table
import chandler.wxui.multi_state as multi_state
from chandler.wxui.image import get_image

class DashboardIconRenderer(table.IconRenderer):
    def bitmapProvider(self, name):
        return get_image(name, "Chandler_App")

class StarRenderer(DashboardIconRenderer):
    def getStateInfos(self):
        for (state, normal, selected) in (
            (False, "pixel", "pixel"),
            (True, "StarStamped", "StarStampedSelected")
        ):
            bmInfo = multi_state.BitmapInfo()
            bmInfo.stateName = state
            bmInfo.normal = normal
            bmInfo.selected = selected
            bmInfo.rollover = "StarRollover"
            bmInfo.rolloverselected = "StarRolloverSelected"
            bmInfo.mousedown = "StarMousedown"
            bmInfo.mousedownselected = "StarMousedownSelected"
            yield bmInfo

    def advanceValue(self, value):
        # "advance" == "toggle"
        return not value

class ReminderRenderer(DashboardIconRenderer):
    def getStateInfos(self):
        kw = dict(rollover="DBReminderRollover",
                  rolloverselected="DBReminderRolloverSelected",
                  mousedown="DBReminderMousedown",
                  mousedownselected="DBReminderMousedownSelected")

        for (state, normal, selected) in (
            ("", "pixel", "pixel"),
            ("event", "DBEvent", "DBEventSelected"),
            ("reminder", "DBReminder", "DBReminderSelected"),
        ):
            kw.update(stateName=state, normal=normal, selected=selected)
            bmInfo = multi_state.BitmapInfo(**kw)

            yield bmInfo

def extend_table(table):
    table.RegisterDataType("DashboardStar", StarRenderer(), None)
    table.RegisterDataType("DashboardReminder", ReminderRenderer(), None)
