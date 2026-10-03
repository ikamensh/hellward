"""Bonus waves: the stake is a wager on a harder pack, drawn from the run's seed.

:func:`draw` deals one stake's pack: a coming host, tomorrow's (stake 1) or the wave after's (stakes 2
and 3), capped at the last wave, with an elite (stake 2) or a leader (stake 3) beside it. The extra monster
comes from the seed; at a breached location the stake-2 extra is the breach's own elite. The payout is paid
only when nothing of the pack leaks: the wager back plus a profit that grows faster than the stake, and XP
that scales the same way; each repeat at a location pays at ``bonus.repeat`` of the one before.

The :class:`World <hellward.sim.model.World>` summons the drawn pack: the wager leaves at once, the pack spawns
as :class:`Bonus` while the break clock stops, and the clear pays the profit and the XP. :mod:`hellward.run`
re-exports the draw for the camp's preview.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Final

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.breaches import BREACHES
from hellward.sim.content import MONSTERS, Group
from hellward.sim.locations.common import Location
from hellward.sim.sums import float_sum, int_sum
from hellward.sim.xp import XP_LIFE

UNITS: Final = tuple(int(u) for u in tuning.numbers("bonus.units"))
PROFIT: Final = tuning.numbers("bonus.profit_mult")
REPEAT: Final = tuning.number("bonus.repeat")
EARLY: Final = tuning.integer("bonus.early")
AHEAD: Final = tuple(int(a) for a in tuning.numbers("bonus.pack_ahead"))
LIFE: Final = tuning.numbers("bonus.life_factor")
EXTRA: Final = tuple(tuning.get("bonus.extra"))
FAIL: Final = tuning.integer("bonus.fail_lives")


@dataclass(frozen=True)
class BonusPack:
    """One stake's bonus wave: its pack, its wager, and what clearing it without a leak pays."""

    stake: int
    groups: tuple[Group, ...]
    life_factor: float
    extra: str | None             # the elite's or leader's kind, joining as one more monster
    wager: int                    # gold, taken when summoned
    profit: int                   # gold over the wager back, when nothing leaks
    xp: float
    lives: int                    # what the pack costs the pool if it all leaks
    fail: int = 0                 # what a failed pack ravages over its leaks (drawn packs: FAIL)

    @property
    def pack(self) -> tuple[Group, ...]:
        """The pack as summoned: the wave's groups and the extra monster, if any."""
        if self.extra is None:
            return self.groups
        return (*self.groups, Group(self.extra, 1, 1.0))

    @property
    def hp(self) -> float:
        """The pack's life to chew through: its groups and the extra, at the stake's factor."""
        kill = float_sum(group.count * MONSTERS[group.kind].hp for group in self.groups)
        if self.extra is not None:
            kill += MONSTERS[self.extra].hp
        return kill * self.life_factor


@dataclass
class Bonus:
    """The live pack a defence fights: what it pays, what of it stands, whether it already leaked."""

    stake: int
    wager: int
    profit: int
    xp: float
    life_factor: float
    alive: int
    fail: int = 0
    leaked: bool = False
    saved_break: float = 0.0      # the break's remainder when the pack came: the clock resumes here


def _elite(location: Location, rng: random.Random) -> str:
    """The elite: the breach's own where the location has one, else one of its three toughest ordinary kinds."""
    if location.key in BREACHES:
        return BREACHES[location.key].elite.kind
    kinds = sorted({group.kind for wave in location.waves for group in wave.groups
                    if not MONSTERS[group.kind].boss and MONSTERS[group.kind].leader is None},
                   key=lambda kind: MONSTERS[kind].hp, reverse=True)
    return rng.choice(kinds[:3])


def _leader(location: Location, rng: random.Random) -> str:
    """The leader: one of the kinds that curse here, or an elite where none does."""
    kinds = sorted({group.kind for wave in location.waves for group in wave.groups
                    if MONSTERS[group.kind].leader is not None})
    return rng.choice(kinds) if kinds else _elite(location, rng)


def draw(location: Location, stake: int, seed: int, index: int, repeats: int = 0,
         wave: int = 0) -> BonusPack:
    """The stake's bonus wave, drawn from the run's seed: a coming host's pack, its wager, and what
    a clean clear pays. ``wave`` is the latest cleared, from 0; the pack is that many waves ahead."""
    if stake not in (1, 2, 3):
        raise ValueError(f"a bonus wave's stake is 1, 2 or 3, not {stake}")
    rng = random.Random(f"bonus:{seed}:{index}:{stake}")
    waves = location.waves
    last = len(waves) - 2 if stake == 3 else len(waves) - 1   # the big bet never names the climax
    ahead = waves[min(wave + AHEAD[stake - 1], last)]
    groups = tuple(g for g in ahead.groups if not MONSTERS[g.kind].boss) or ahead.groups
    extra = {"none": None, "elite": _elite(location, rng), "leader": _leader(location, rng)}
    kind = extra[EXTRA[stake - 1]]
    unit = BALANCE.income_unit()
    wager = UNITS[stake - 1] * unit
    profit = round(PROFIT[stake - 1] * unit * REPEAT ** repeats)
    kill = float_sum(group.count * MONSTERS[group.kind].hp for group in groups)
    if kind is not None:
        kill += MONSTERS[kind].hp
    xp = kill / XP_LIFE * PROFIT[stake - 1] * REPEAT ** repeats
    lives = int_sum(group.count * MONSTERS[group.kind].lives for group in groups)
    if kind is not None:
        lives += MONSTERS[kind].lives
    return BonusPack(stake, groups, LIFE[stake - 1], kind, wager, profit, xp, lives, FAIL)


def preview(pack: BonusPack) -> str:
    """The bonus panel's preview: the pack's kinds and counts, the lives at stake, and the reward."""
    kinds = ", ".join(f"{group.count} {MONSTERS[group.kind].name}" + ("s" if group.count > 1 else "")
                      for group in sorted(pack.pack, key=lambda g: g.kind))
    harder = f", with {pack.life_factor:g}x life" if pack.life_factor != 1.0 else ""
    return (f"Stake {pack.stake} for {pack.wager} gold: {kinds}{harder}. {pack.lives} lives at stake. "
            f"Clear it with no leak for the wager back and {pack.profit} gold; "
            f"a leak fails it for the wager and {pack.fail} sanctuary life.")
