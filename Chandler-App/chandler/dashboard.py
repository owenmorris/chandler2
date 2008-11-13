from peak.events import trellis
from peak.util import addons, plugins
from chandler.event import Event
from chandler.reminder import ReminderList
from chandler.triage import Triage, TriagePosition, NOW
from chandler.time_services import is_past_timestamp, timestamp

class AppDashboardEntry(addons.AddOn, trellis.Component):
    trellis.attrs(
        _item = None,
        triage_status = NOW,
        triage_position = 0,
    )

    def __init__(self, subject, **kw):
        self._item = item = subject.subject_item
        # initialize compute cells, they're optional so may not be there yet
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
    def reminder_scheduled(self):
        if not self._item:
            return False
        for reminder in ReminderList(self._item).reminders:
            trigger = reminder.trigger
            if trigger and not is_past_timestamp(timestamp(trigger)):
                return True
        return False

plugins.Hook('chandler.domain.dashboard_entry_addon').register(AppDashboardEntry)
