from peak.events import collections, trellis
from peak.util import addons, plugins
from chandler.event import Event
from chandler.starred import Starred
from chandler.reminder import ReminderList
from chandler.triage import Triage, TriagePosition, NOW
from chandler.time_services import is_past_timestamp, timestamp
import chandler.core as core

class AppDashboardEntry(addons.AddOn, trellis.Component):
    trellis.attrs(
        subject = None,
        triage_status = NOW,
        triage_position = 0,
    )

    @trellis.compute
    def _item(self):
        return self.subject.subject_item

    def __init__(self, subject, **kw):
        self.subject = subject
        # initialize compute cells, they're optional so may not be there yet
        item = subject.subject_item
        Triage(item).calculated
        TriagePosition(item).position
        kw.setdefault('triage_status',
                      trellis.Cells(Triage(item))['calculated'])
        kw.setdefault('triage_position',
                      trellis.Cells(TriagePosition(item))['position'])
        trellis.Component.__init__(self, **kw)

    @trellis.compute
    def is_event(self):
        if not self._item:
            return False
        return Event.installed_on(self._item)

    @trellis.compute
    def is_starred(self):
        if not self._item:
            return False
        return Starred.installed_on(self._item)

    @trellis.compute
    def reminder_scheduled(self):
        if not self._item:
            return False
        for reminder in ReminderList(self._item).reminders:
            trigger = reminder.trigger
            if trigger and not is_past_timestamp(timestamp(trigger)):
                return True
        return False

plugins.Hook('chandler.domain.dashboard_entry_addon').register(AppDashboardEntry)

class AppEntryAggregate(core.AggregatedSet):
    """
    AggregatedSet that aggregates all AppDashboardEntry objects
    corresponding to the Items in its input.
    """

    def get_values(self, item):
        return tuple(AppDashboardEntry(subject) for subject in item.dashboard_entries)

class Dashboard(core.Table):
    @trellis.maintain
    def star_column(self):
        return core.TableColumn(scope=self, label=u'*',
                                get_value=lambda entry:AppDashboardEntry(entry).is_starred)

    @trellis.make
    def columns(self):
        return trellis.List([self.star_column,])

