"""Six optional side entrances: authored packs, distinct elites and their offer timing."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from hellward.sim.content import Group


@dataclass(frozen=True)
class BreachSpec:
    location: str
    name: str
    after_wave: int
    elite_name: str
    elite: Group
    pack: tuple[Group, ...]
    elite_hp_factor: float = 2.0
    elite_speed_factor: float = 1.0
    blurb: str = ""

    def __post_init__(self) -> None:
        if self.elite.count != 1 or self.elite.route != "breach":
            raise ValueError("a breach must have one elite from its sealed entrance")
        if not self.pack or any(group.route != "breach" for group in self.pack):
            raise ValueError("a breach pack must use its sealed entrance")
        if self.after_wave < 0 or self.elite_hp_factor <= 1 or self.elite_speed_factor <= 0:
            raise ValueError("invalid breach timing or elite strength")

    @property
    def groups(self) -> tuple[Group, ...]:
        return (self.elite, *self.pack)

    @property
    def count(self) -> int:
        total = 0
        for group in self.groups:
            total += group.count
        return total


BREACHES: Final[Mapping[str, BreachSpec]] = MappingProxyType({spec.location: spec for spec in (
    BreachSpec("graveyard", "The Ash Crypt", 1, "Ashwing",
               Group("gargoyle", 1, 1.0, start=3.0, route="breach"),
               (Group("fallen", 4, 0.8, route="breach"),),
               elite_speed_factor=1.2, blurb="A fast flyer ignores the graveyard gate."),
    BreachSpec("catacombs", "The Iron Ossuary", 2, "The Door Eater",
               Group("hulk", 1, 1.0, start=4.0, route="breach"),
               (Group("skeleton", 4, 0.8, route="breach"),),
               blurb="A hulking gatebreaker leads the dead through a side arch."),
    BreachSpec("hells_gate", "The Red Kennel", 3, "The Blood Caller",
               Group("fetish", 1, 1.0, start=3.0, route="breach"),
               (Group("flayer", 5, 0.5, route="breach"),),
               blurb="A foreign shaman raises its fallen pack."),
    BreachSpec("spider_forest", "The Root Pit", 2, "The Rootbreaker",
               Group("hulk", 1, 1.0, start=3.0, route="breach"),
               (Group("drowned", 3, 1.1, route="breach"),),
               blurb="A giant batters gates while the drowned cross the clearing."),
    BreachSpec("drowned_city", "The Bell Tower", 3, "The Saltwing",
               Group("gargoyle", 1, 1.0, start=2.0, route="breach"),
               (Group("bat", 6, 0.5, route="breach"),),
               elite_speed_factor=1.25, blurb="Wings fly past every flooded gate."),
    BreachSpec("temple", "The Lightless Choir", 3, "The Last Warden",
               Group("overlord", 1, 1.0, start=4.0, route="breach"),
               (Group("inquisitor", 2, 2.0, route="breach"),),
               elite_hp_factor=2.5, blurb="A doorbreaker crosses with two silent curse bearers."),
)})
