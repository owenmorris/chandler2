import peak.events.trellis as trellis
from peak.util.addons import AddOn

### Constants ###

NOW = 100.0
LATER = 200.0
DONE = 300.0

### Domain model ###

class TriageRangeError(Exception):
    pass

class Triage(AddOn, trellis.Component):
    trellis.attrs(
        manual=None,
        auto=None
    )

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
                raise TriageRangeError, "Can't set triage status to %s" % cell


### Interaction model ###
class TriagePosition(AddOn, trellis.Component):
    trellis.attrs(
        _triage_addon=None,
        pinned_triage_section=None,
        pinned_position=None
    )

    def __init__(self, subject, **kwargs):
        self._triage_addon = Triage(subject)
        trellis.Component.__init__(self, **kwargs)

    @trellis.compute
    def default_position(self):
        ### needs fleshing out with entry points
        return self._triage_addon.calculated

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

    @trellis.modifier
    def pin(self):
        if self.pinned_triage_section is None and self.pinned_position is None:
            self.pinned_triage_section = self.default_triage_section
            self.pinned_position = self.default_position

    @trellis.modifier
    def clear_pinned(self):
        self.pinned_position = self.pinned_triage_section = None

    @trellis.modifier
    def pop_to_now(self, timestamp=None):
        self.pinned_triage_section = NOW
