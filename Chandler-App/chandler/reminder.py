import peak.events.trellis as trellis
from peak.util.addons import AddOn
from chandler.core import ConstraintError
from chandler.event import Event
from chandler.triage import *

### Domain model ###

class ReminderList(AddOn, trellis.Component):
    _item = trellis.attr(None)
    reminders = trellis.make(trellis.List)

    def __init__(self, subject, **kwargs):
        self._item = subject
        trellis.Component.__init__(self, **kwargs)

    def add_reminder(self, **kwargs):
        reminder = Reminder(item=self._item, **kwargs)
        self.reminders.append(reminder)
        return reminder

class Reminder(trellis.Component):
    trellis.attrs(
        item=None,
        delta=None,
        fixed_trigger=None,
        snooze=None,
        cleared=False,
        type='triage',
    )

    @trellis.compute
    def trigger(self):
        if self.fixed_trigger is not None:
            return self.fixed_trigger
        elif self.delta is not None and self.item is not None:
            if Event.installed_on(self.item):
                start = Event(self.item).start
                if start is not None:
                    return start + self.delta
