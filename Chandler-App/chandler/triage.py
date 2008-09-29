import peak.events.trellis as trellis
from peak.util.addons import AddOn

NOW = 100.0
LATER = 200.0
DONE = 300.0

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
