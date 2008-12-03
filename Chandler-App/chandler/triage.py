import peak.events.trellis as trellis
from peak.util import plugins
import peak.events.activity as activity
from chandler.time_services import nowTimestamp, is_past_timestamp
from chandler.core import ConstraintError, ItemAddOn

### Constants ###

NOW = 100.0
LATER = 200.0
DONE = 300.0

TRIAGE_HOOK  = plugins.Hook('chandler.domain.triage')

### Domain model ###

def triage_status_timeline(triage):
    """Yield all (timestamp, status) pairs for the given item."""
    yield (0, NOW) # default
    manual_pair = triage.manual_timestamp, triage.manual
    if None not in manual_pair:
        yield manual_pair
    for iterable in TRIAGE_HOOK.query(triage._item):
        for pair in iterable:
            yield pair

def filter_on_time(triage, future=True):
    """Yield all past or future (timestamp, status) pairs for the given item."""
    for timestamp, status in triage_status_timeline(triage):
        if future ^ is_past_timestamp(timestamp): # ^ means XOR
            yield timestamp, status


class Triage(ItemAddOn):
    trellis.attrs(
        manual=None,
        manual_timestamp=None,
        auto_source=None
    )

    @trellis.compute
    def auto(self):
        max_timestamp, status = max(filter_on_time(self, future=False))
        return status


    @trellis.compute
    def calculated(self):
        if self.manual is not None and self.manual_timestamp is None:
            return self.manual
        if self.auto is not None:
            return self.auto
        return NOW

    @trellis.maintain
    def constraints(self):
        for cell in (self.manual, self.auto):
            if cell is not None and int(cell) < 100:
                raise TriageRangeError(cell)

class TriagePosition(ItemAddOn):
    trellis.attrs(
        pinned_triage_section=None,
        pinned_position=None
    )

    @trellis.compute
    def _triage_addon(self):
        return Triage(self._item)

    @trellis.compute
    def default_position(self):
        triage = Triage(self._item)
        if self._triage_addon.calculated == LATER:
            future_choices = list(filter_on_time(triage, future=True))
            if future_choices:
                return min(future_choices)[0]
        # if LATER but no known triage change in the future, use NOW behavior
        last_past = max(filter_on_time(triage, future=False))
        # never return a timestamp less than the item's creation timestamp
        return max(self._item.created, last_past[0])


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

class TriageRangeError(ConstraintError):
    cell_description = "triage status"
