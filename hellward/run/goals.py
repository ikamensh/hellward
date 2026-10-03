"""The run's level goals: each a fold over the defence's events, judged over the whole defence.

A :class:`Goal` is a live state (``open``, ``met`` or ``failed``): the server feeds it the world's events as they
happen, plus ``("step", t)`` second marks from its own clock, and sends ``goal`` events when the verdict changes.
:func:`describe` is the camp's line for a drawn goal; :meth:`Goal.warn` is the client's warning before an order
that would fail one. At the defence's end the ``("end",)`` mark finalizes countable goals, and an ``open``
verdict closes to :attr:`Goal.close_default` (a goal nothing violated is met; a goal nothing achieved is failed).

The family and leaders folds read the kinds the simulation's ``("built", id, kind)`` and ``("spawn", id, kind)``
events carry; over an older recording without them they stay open.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from hellward.sim.content import SPELLS, TOWERS

OPEN: str = "open"
MET: str = "met"
FAILED: str = "failed"


@dataclass(frozen=True)
class Drawn:
    """One goal a run drew for a location: its type and its parameter (a count, an element, a kind)."""

    key: str
    arg: str


def describe(drawn: Drawn) -> str:
    """The camp's line for a drawn goal."""
    if drawn.key == "lean":
        return f"a lean defence: at most {drawn.arg} towers stand at any moment"
    if drawn.key == "gate":
        return "the gate holds: a gate stands by wave 2 and never falls"
    if drawn.key == "family":
        return ("one family: no tower built is physical" if drawn.arg == "!physical"
                else f"one family: every tower built is {drawn.arg}")
    if drawn.key == "leaders":
        return f"the leaders die first: every {drawn.arg} dies before its first curse lands"
    if drawn.key == "hymn":
        return f"a fragile hymn: Battle Hymn is cast {drawn.arg} times with no curse on the hymned tower"
    if drawn.key == "bonus":
        return f"the bonus: a bonus wave is cleared at stake {drawn.arg} or more"
    raise KeyError(f"unknown goal {drawn.key!r}")


class Goal:
    """One goal's fold: :meth:`start` on the defence's Kit, :meth:`observe` per event, :meth:`verdict` live."""

    key: ClassVar[str] = ""
    close_default: ClassVar[str] = MET   # what an open verdict closes to at the defence's end

    def __init__(self, arg: str) -> None:
        self.arg = arg
        self.state = OPEN

    def start(self, kit: Any) -> None:
        """Take the defence's Kit; most goals need nothing from it."""

    def observe(self, event: tuple) -> None:
        """Fold one event in."""

    def verdict(self) -> str:
        return self.state

    def warn(self, name: str, args: dict[str, Any]) -> str | None:
        """Why the client's order (a battle order's name and args) would fail this goal, or None."""
        return None


class Lean(Goal):
    """At most N towers stand at any moment."""

    key: ClassVar[str] = "lean"

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.standing = 0

    def observe(self, event: tuple) -> None:
        if event[0] == "built":
            self.standing += 1
            if self.standing > int(self.arg):
                self.state = FAILED
        elif event[0] == "sold":
            self.standing -= 1

    def warn(self, name: str, args: dict[str, Any]) -> str | None:
        if name == "build" and self.state == OPEN and self.standing >= int(self.arg):
            return f"Building would fail the goal: at most {self.arg} towers may stand."
        return None


class Gate(Goal):
    """A gate is built by wave 2 (before the third wave is called) and never falls."""

    key: ClassVar[str] = "gate"

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.built = False

    def observe(self, event: tuple) -> None:
        if event[0] == "door_built":
            self.built = True
        elif event[0] == "door_broken":
            self.state = FAILED
        elif event[0] == "wave" and event[1] >= 2 and not self.built:
            self.state = FAILED


class Family(Goal):
    """Every tower built is of the named element, or (``!physical``) none is physical."""

    key: ClassVar[str] = "family"

    def _breaks(self, element: str) -> bool:
        return element == "physical" if self.arg == "!physical" else element != self.arg

    def observe(self, event: tuple) -> None:
        if event[0] != "built" or len(event) < 3:   # an older recording, without the kind
            return
        if self._breaks(TOWERS[event[2]].element.value):
            self.state = FAILED

    def warn(self, name: str, args: dict[str, Any]) -> str | None:
        if name != "build" or self.state != OPEN:
            return None
        if self._breaks(TOWERS[str(args["kind"])].element.value):
            want = "no physical tower" if self.arg == "!physical" else f"only {self.arg} towers"
            return f"Building it would fail the goal: {want} may stand."
        return None


class Leaders(Goal):
    """Every leader of the named kind dies before its first curse lands."""

    key: ClassVar[str] = "leaders"

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.alive: set[int] = set()
        self.seen = False

    def observe(self, event: tuple) -> None:
        if event[0] == "spawn" and len(event) >= 3:   # older recordings carry the id alone
            if event[2] == self.arg:
                self.alive.add(event[1])
                self.seen = True
        elif event[0] == "death" and event[1] in self.alive:
            self.alive.discard(event[1])
            if not self.alive:
                self.state = MET
        elif event[0] == "cursed" and event[1] in self.alive:
            self.state = FAILED


class Hymn(Goal):
    """Battle Hymn is cast N times without the hymned tower being cursed during it.

    A hymn is tainted when a curse lands on its tower before the hymn's seconds run out; a tainted hymn
    counts for nothing but fails nothing. The ``("step", t)`` marks time the windows; the ``("end",)`` mark
    finalizes hymns still open.
    """

    key: ClassVar[str] = "hymn"
    close_default: ClassVar[str] = FAILED

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.clean = 0
        self.open: dict[int, list] = {}   # tower id to [cast second, tainted]
        self.now = 0.0

    def _close_lapsed(self) -> None:
        lasting = SPELLS["hymn"].lasting
        for tower in [tower for tower, (cast, _) in self.open.items() if cast + lasting <= self.now]:
            _, tainted = self.open.pop(tower)
            if not tainted:
                self.clean += 1

    def observe(self, event: tuple) -> None:
        if event[0] == "step":
            self.now = float(event[1])
            self._close_lapsed()
        elif event[0] == "hymn":
            self.open[event[1]] = [self.now, False]
        elif event[0] == "cursed":
            for tower in event[4]:
                if tower in self.open:
                    self.open[tower][1] = True
        elif event[0] == "end":
            self._close_lapsed()
            for _, tainted in self.open.values():
                if not tainted:
                    self.clean += 1
            self.open.clear()
        if self.clean >= int(self.arg):
            self.state = MET


class Bonus(Goal):
    """A bonus wave is cleared at the named stake or more."""

    key: ClassVar[str] = "bonus"
    close_default: ClassVar[str] = FAILED

    def observe(self, event: tuple) -> None:
        if event[0] == "bonus" and event[2] == "cleared" and int(event[1]) >= int(self.arg):
            self.state = MET


GOALS: dict[str, type[Goal]] = {"lean": Lean, "gate": Gate, "family": Family, "leaders": Leaders,
                               "hymn": Hymn, "bonus": Bonus}


def make(drawn: Drawn) -> Goal:
    """The fold for a drawn goal."""
    if drawn.key not in GOALS:
        raise KeyError(f"unknown goal {drawn.key!r}")
    return GOALS[drawn.key](drawn.arg)
