from peak.events import collections, trellis
from peak.util import addons, plugins
from chandler.event import Event
from chandler.starred import Starred
from chandler.reminder import ReminderList
import chandler.triage as triage
from chandler.time_services import (TimeZone, is_past, timestamp, fromtimestamp,
                                    getNow)
import chandler.core as core
import chandler.wxui.image as image
from chandler.i18n import _
from datetime import datetime, timedelta

TRIAGE_HOOK  = plugins.Hook('chandler.dashboard.triage')

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
        return triage.Triage(self._item).calculated

    @trellis.compute
    def triage_position(self):
        return triage.TriagePosition(self._item).position

    @trellis.compute
    def triage_section(self):
        return triage.TriagePosition(self._item).triage_section

    @trellis.compute
    def is_event(self):
        return Event.installed_on(self._item)

    @trellis.compute
    def is_starred(self):
        return Starred.installed_on(self._item)

    @trellis.modifier
    def toggle_star(self):
        if Starred.installed_on(self._item):
            Starred(self._item).remove()
        else:
            Starred(self._item).add()

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
        return self._when_and_is_day[0]

    @trellis.compute
    def _when_and_is_day(self):
        if self._when_source == 'event':
            event = Event(self._item)
            return event.start, event.is_day
        elif self._when_source == 'reminder':
            return self._reminder.trigger, False
        else:
            return fromtimestamp(self._item.created), False

    @trellis.compute
    def display_date(self):
        when, is_day = self._when_and_is_day

        when = when.astimezone(TimeZone.default)
        when_date = when.date()

        # [@@@] Real date format support rather than strftime
        time_part = when.strftime("%X") if not is_day else ""

        # [@@@] Probably time_services should offer a today cell here
        since_today = (when_date - getNow().date()).days
        if since_today == -1:
            return _(u"Yesterday"), time_part
        elif since_today == 0:
            return _(u"Today"), time_part
        elif since_today == 1:
            return _(u"Tomorrow"), time_part
        else:
            return when.strftime("%x"), time_part

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

    _triage_values = None

    @property
    def triage_values(self):
        if self._triage_values is None:
            triage_values = []
            for iterable in TRIAGE_HOOK.query():
                for value, name, hsv in iterable:
                    triage_values.append((value, (name, hsv)))

            type(self)._triage_values = tuple(triage_values)
        return self._triage_values

    @trellis.modifier
    def action(self, selection):
        for app_entry in selection:
            old_value = app_entry.triage_section
            for index, value in enumerate(self.triage_values):
                if value[0] == old_value:
                    if index + 1 < len(self.triage_values):
                        new_value = self.triage_values[index+1][0]
                    else:
                        new_value = self.triage_values[0][0]
                    break
            else:
                new_value = self.triage_values[0][0]
            triage.Triage(app_entry._item).manual = new_value

class ReminderColumn(AppColumn):
    label = trellis.attr('(( ))')
    app_attr = trellis.attr('event_reminder_combined')

    def sort_key(self, entry):
        return entry.triage_section, entry.triage_position

    _triage_values = None

    @trellis.modifier
    def action(self, selection):
        for app_entry in selection:
            old_value = app_entry.event_reminder_combined
            rlist = ReminderList(app_entry._item)
            if old_value == 'reminder':
                rlist.remove_all_reminders()
            else:
                trigger = getNow()
                if trigger.hour < 17:
                    hour = 17
                else:
                    trigger += timedelta(days=1)
                    hour = 8
                trigger = trigger.replace(hour=hour, minute=0, second=0,
                                          microsecond=0)
                reminder = rlist.add_reminder()
                reminder.fixed_trigger = trigger


class StarredColumn(AppColumn):
    @staticmethod
    def action(selection):
        for app_entry in selection:
            app_entry.toggle_star()


@trellis.modifier
def set_item_title(entry, value):
    entry.subject.what = value

class Dashboard(core.Table):
    @trellis.maintain
    def star_column(self):
        return StarredColumn(scope=self, label=u'*', app_attr='is_starred',
                             hints={'width': 20,
                                    'header_icon':'ColHStarred.png',
                                    'type': 'DashboardStar'})

    @trellis.maintain
    def title_column(self):
        return core.TableColumn(scope=self, label='Title',
                                get_value=lambda entry:entry.subject.what,
                                set_text_value=set_item_title,
                                hints={'width':160, 'scalable':True})

    @trellis.maintain
    def event_reminder_column(self):
        return ReminderColumn(scope=self,
                              hints={'width': 36, 'type': 'DashboardReminder',
                                     'header_icon':'ColHEventReminder.png'})

    @trellis.maintain
    def date_column(self):
        return AppColumn(scope=self, label='Date', app_attr='display_date',
                         hints={'width':220, 'type':'DashboardDate'},
                         sort_key=lambda value:value._when_and_is_day)

    @trellis.maintain
    def triage_column(self):
        return TriageColumn(scope=self, hints={'width': 60,
                                        'header_icon':'ColHTriage.png',
                                        'type':'DashboardTriage'})


    @trellis.make
    def columns(self):
        return trellis.List([self.star_column, self.title_column,
                             self.event_reminder_column, self.date_column,
                             self.triage_column])

    @trellis.make
    def hints(self):
        return { 'column_headers': True }


import wx
import chandler.wxui.table as table
import chandler.wxui.multi_state as multi_state
from chandler.wxui.image import get_image
from colorsys import hsv_to_rgb

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


class TriageRenderer(table.wxGrid.PyGridCellRenderer):

    def __init__(self, font=None):
        if font is None:
            defaultFont = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
            font = wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.BOLD, False,
                           defaultFont.FaceName)
        super(TriageRenderer, self).__init__()
        self.font = font

    def _wx_Color(self, hsv, variant):
        h, s, v = hsv

        if "rollover" in variant:
            v = v + 0.33 * (1.0 - v)
            s = 0.65 * s

        if "mousedown" in variant:
            v = 0.67 * v

        if "border" in variant:
            v = v + 0.5 * (1.0 - v)
            s = 0.5 * s

        h = float(h)/360.0
        r, g, b = map(lambda val: (int)(val * 255 + 0.5), hsv_to_rgb(h, s, v))
        return wx.Colour(r, g, b)


    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        value = grid.Table.GetValue(row, col)

        if grid.clickRowCol == (row, col):
            variant = ('mousedown',)
        elif grid.overRowCol == (row, col):
            variant = ('rollover',)
        else:
            variant = ()

        gc = wx.GraphicsContext.Create(dc)

        for tvalue, tparams in grid.Table.table.columns[col].triage_values:
            if tvalue == value:
                text, hsv = tparams
                break
        else:
            assert False, "Invalid triage value %s" % (value,)

        bgColor = self._wx_Color(hsv, variant)
        borderColor = self._wx_Color(hsv, variant + ("border",))

        textXOffset = 0
        textYOffset = 1

        gc.SetBrush(wx.Brush(bgColor, wx.SOLID))
        gc.SetPen(wx.Pen(borderColor))
        gc.DrawRectangle(rect.X, rect.Y, rect.Width, rect.Height)

        gc.SetFont(self.font, wx.WHITE)

        width, height, descent, leading = gc.GetFullTextExtent(text)
        textLeft = rect.Left + int((rect.Width - width) / 2) - textXOffset
        textTop = rect.Top + int((height - descent) / 2) - textYOffset
        gc.DrawText(text, textLeft, textTop)
        del gc


def triage_presentation_values():
    return (
        (triage.NOW, _('NOW'), (120, 1.00, 0.80)),
        (triage.LATER, _('LATER'), (48, 1.00, 1.00)),
        (triage.DONE, _('DONE'), (0, 0.0, 0.33)),
    )


class DateRenderer(table.wxGrid.PyGridCellRenderer):

    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        date, time = grid.Table.GetValue(row, col)

        vAlign = attr.GetAlignment()[1]

        if isSelected:
            bg = grid.GetSelectionBackground()
            fg = grid.GetSelectionForeground()
        else:
            bg = attr.GetBackgroundColour()
            fg = attr.GetTextColour()

        dc.SetTextBackground(bg)
        dc.SetTextForeground(fg)

        dc.SetBrush(wx.Brush(bg, wx.SOLID))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangleRect(rect)

        grid.DrawTextRectangle(dc, date, rect, wx.ALIGN_LEFT, vAlign)
        grid.DrawTextRectangle(dc, time, rect, wx.ALIGN_RIGHT, vAlign)


def extend_table(table):
    table.RegisterDataType("DashboardStar", StarRenderer(), None)
    table.RegisterDataType("DashboardReminder", ReminderRenderer(), None)
    table.RegisterDataType("DashboardTriage", TriageRenderer(), None)
    table.RegisterDataType("DashboardDate", DateRenderer(), None)
