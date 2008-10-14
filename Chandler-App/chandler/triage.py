import peak.events.trellis as trellis
from peak.util import plugins
from peak.util.addons import AddOn
from chandler.time_services import nowTimestamp
from chandler.core import ConstraintError

### Constants ###

NOW = 100.0
LATER = 200.0
DONE = 300.0

TRIAGE_HOOK  = plugins.Hook('chandler.domain.triage')
POSITION_HOOK = plugins.Hook('chandler.interaction.triage_position')

### Domain model ###

class Triage(AddOn, trellis.Component):
    trellis.attrs(
        _item=None,
        manual=None,
        auto_source=None
    )

    def __init__(self, item, **kwargs):
        self._item = item

    @trellis.compute
    def auto(self):
        if self.auto_source:
            pass # make use of auto_source when reminders have been fleshed out
        else:
            positions = list(TRIAGE_HOOK.query(self._item))
            # default to NOW if nothing else applies
            positions.append((0, NOW))
            max_weight, position = max(positions)
            return position


    @trellis.compute
    def calculated(self):
        if self.manual is not None:
            return self.manual
        if self.auto is not None:
            return self.auto
        return NOW

    @trellis.maintain
    def constraints(self):
        for cell in (self.manual, self.auto):
            if cell is not None and int(cell) < 100:
                raise TriageRangeError(cell)

class TriageRangeError(ConstraintError):
    cell_description = "triage status"

### Interaction model ###
class TriagePosition(AddOn, trellis.Component):
    trellis.attrs(
        _item=None,
        _triage_addon=None,
        pinned_triage_section=None,
        pinned_position=None
    )

    def __init__(self, item, **kwargs):
        self._item = item
        # AddOn/Components like Triage need to be added outside of rules
        self._triage_addon = Triage(item)
        trellis.Component.__init__(self, **kwargs)

    @trellis.compute
    def default_position(self):
        ### needs fleshing out with entry points
        return self._item.created

    @trellis.compute
    def default_triage_section(self):
        return self._triage_addon.calculated

    @trellis.compute
    def position(self):
        if self.pinned_position is None:
            return self.default_position
        else:
            return self.pinned_position

    @trellis.compute
    def triage_section(self):
        if self.pinned_triage_section is None:
            return self.default_triage_section
        else:
            return self.pinned_triage_section

    ### Modifiers ###
    @trellis.modifier
    def pin(self):
        if self.pinned_triage_section is None and self.pinned_position is None:
            self.pinned_triage_section = self.default_triage_section
            self.pinned_position = self.default_position

    @trellis.modifier
    def clear_pinned(self):
        self.pinned_position = self.pinned_triage_section = None

    @trellis.modifier
    def pin_to_now(self):
        self.pinned_triage_section = NOW
        self.pinned_position = nowTimestamp()
