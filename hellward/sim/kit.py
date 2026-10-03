"""Everything one defence starts from, as one immutable value.

A :class:`Kit` is the location, the learned skills, the loadout, the starting gold and sanctuary lives, and the
seed, with empty slots for stage 3's relics and carried counters. A replay is a Kit plus the order log. The
tool knobs (``hardness``, ``curse_scale``, ``record``, ``planner``) stay :class:`World` keyword arguments, passed
to :meth:`Kit.world`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hellward.sim.campaign import ORDER, Location
from hellward.sim.items import EMPTY_LOADOUT, Loadout
from hellward.sim.model import START_LIVES, Planner, World
from hellward.sim.skills import perks
from hellward.sim.xp import xp_next


@dataclass(frozen=True)
class Kit:
    """One defence's starting conditions."""

    location: Location
    learned: frozenset[str] = frozenset()
    loadout: Loadout = EMPTY_LOADOUT
    gold: int = 0
    lives: int = 0
    seed: int = 0
    relics: tuple = ()      # stage 3: the run's relics
    counters: tuple = ()    # stage 3: the counters carried into the defence
    xp: float = 0.0         # the run's progress to the next level: the world counts on from here
    level: int = 1          # the run's level: with the curve, the world knows every threshold past it
    xp_next: float = 0.0    # the XP to the next level at the deal, for the client's bar

    def __post_init__(self) -> None:
        if self.xp_next <= 0:   # reckoned, so the client's bar never reads a bare zero
            object.__setattr__(self, "xp_next", xp_next(self.level))

    def world(self, *, hardness: float = 1.0, curse_scale: float = 1.0, record: bool = True,
              planner: Planner | None = None) -> World:
        """The defence's opening world: what :func:`defend` builds, from this Kit."""
        stage = ORDER.index(self.location.key)
        world = World(self.location, hardness=hardness, perks=perks(self.learned, stage), seed=self.seed,
                      planner=planner, record=record, curse_scale=curse_scale, loadout=self.loadout,
                      xp=self.xp, xp_level=self.level)
        world.gold = self.gold
        world.lives = self.lives
        return world

    def to_json(self) -> dict[str, Any]:
        return {"location": self.location.key, "learned": sorted(self.learned),
                "loadout": list(self.loadout.equipped), "gold": self.gold, "lives": self.lives,
                "seed": self.seed, "relics": list(self.relics), "counters": list(self.counters),
                "xp": self.xp, "level": self.level, "xp_next": self.xp_next}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Kit:
        """A Kit from :meth:`to_json`'s shape; a location outside the campaign is refused."""
        from hellward.sim.campaign import LOCATIONS

        key = str(data["location"])
        if key not in LOCATIONS:
            raise ValueError(f"a replay's location is outside the campaign: {key!r}")
        level = int(data.get("level", 1))
        return cls(location=LOCATIONS[key], learned=frozenset(str(s) for s in data.get("learned", ())),
                   loadout=Loadout(tuple(str(p) for p in data.get("loadout", ()))),
                   gold=int(data.get("gold", LOCATIONS[key].start_gold)),
                   lives=int(data.get("lives", START_LIVES)), seed=int(data.get("seed", 0)),
                   relics=tuple(data.get("relics", ())), counters=tuple(data.get("counters", ())),
                   xp=float(data.get("xp", 0.0)), level=level,
                   xp_next=float(data.get("xp_next", xp_next(level))))
