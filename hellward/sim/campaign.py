"""The campaign: six locations on the way down to hell, the three difficulties, and the sigils a defence earns.

A :class:`Location` is everything one defence needs: its map, its waves, the gold it starts with and what the
player may use there (:class:`Arsenal`, fixed by the location's place in the campaign, so a replay is the same
puzzle). The words for its intro are here too, since they name the rules they describe. ``docs/campaign.md``
is the design.
"""

from __future__ import annotations

from dataclasses import dataclass

from hellward.sim.content import Group, Wave
from hellward.sim.level import Level
from hellward.sim.sums import int_sum


@dataclass(frozen=True)
class Arsenal:
    towers: tuple[str, ...]
    gates: bool
    spells: tuple[str, ...]


@dataclass(frozen=True)
class Location:
    key: str
    name: str
    level: Level
    waves: tuple[Wave, ...]
    wave_names: tuple[str, ...]
    arsenal: Arsenal
    start_gold: int
    theme: str                        # the floor's look, for art/mapart.py
    blurb: str                        # what the place is, one or two sentences
    taunt: str                        # the Bone Priest, who has seen this fight before
    requires: tuple[str, ...] = ()    # the location that must be held first
    life: float = 1.0                 # every monster's life here, and the spells' strength, is multiplied by this: the
                                      # location's difficulty, tuned by simulation (docs/campaign.md); the waves' own
                                      # life multipliers give the ramp within it

    def __post_init__(self) -> None:
        if len(self.wave_names) != len(self.waves):
            raise ValueError(f"{self.key}: {len(self.waves)} waves but {len(self.wave_names)} names")
        if self.level.doors and not self.arsenal.gates:
            raise ValueError(f"{self.key}: arches but no gates to put in them")

    @property
    def called(self) -> str:
        """The name as it reads inside a sentence: "the Graveyard", "Tristram"."""
        return "the" + self.name[3:] if self.name.startswith("The ") else self.name

    @property
    def monsters(self) -> tuple[str, ...]:
        """Every monster kind that comes here, in the order they first appear."""
        seen: dict[str, None] = {}
        for wave in self.waves:
            for group in sorted(wave.groups, key=lambda g: g.start):
                seen.setdefault(group.kind, None)
        return tuple(seen)


@dataclass(frozen=True)
class Difficulty:
    key: str
    name: str
    hp: float              # every monster's life is multiplied by this
    leader_pace: float     # and every leader's cooldown by this
    requires: str | None   # the difficulty whose last location must fall first


NORMAL = Difficulty("normal", "Normal", 1.0, 1.0, None)
HELL = Difficulty("hell", "Hell", 2.2, 0.75, "normal")
DIFFICULTIES: dict[str, Difficulty] = {d.key: d for d in (NORMAL, HELL)}

SIGIL_LIVES = (1, 10, 18)   # sanctuary life to keep for one, two and three sigils (a victory keeps at least one)


def sigils(outcome: str | None, lives: int) -> int:
    """Sigils a defence earns: none for a fall, then one, two or three by the life kept."""
    if outcome != "victory":
        return 0
    return int_sum(1 for need in SIGIL_LIVES if lives >= need)


ALL_TOWERS = ("pyre", "storm", "frost", "plague")
ALL_SPELLS = ("cleanse", "smite", "meteor", "orb")


def _waves(*rows: tuple[tuple[Group, ...], int, float]) -> tuple[Wave, ...]:
    return tuple(Wave(groups, bonus, hp) for groups, bonus, hp in rows)


def g(kind: str, count: int, interval: float = 1.0, start: float = 0.0) -> Group:
    return Group(kind, count, interval, start)


TRISTRAM = Location(
    key="tristram",
    name="Tristram",
    level=Level(
        name="Tristram", width=25, height=14,
        waypoints=((0, 4), (9, 4), (9, 10), (17, 10), (17, 5), (24, 5)),
        doors=(),
        obstacles=frozenset({(3, 1), (13, 2), (21, 2), (5, 12), (22, 10), (13, 7)}),
    ),
    waves=_waves(
        ((g("fallen", 8, 1.2),), 30, 1.0),
        ((g("fallen", 10, 0.9), g("zombie", 2, 3.0, start=4.0)), 40, 1.1),
        ((g("fallen", 10, 0.8), g("zombie", 3, 2.5, start=2.0), g("shaman", 1, start=5.0)), 50, 1.2),
        ((g("fallen", 16, 0.6), g("zombie", 4, 2.0, start=3.0), g("shaman", 2, 6.0, start=3.0)), 60, 1.35),
        ((g("fallen", 22, 0.5), g("zombie", 6, 1.8, start=4.0), g("shaman", 3, 5.0, start=2.0)), 0, 1.5),
    ),
    wave_names=("The Fallen Swarm", "The Village Dead", "The Shaman Sings", "Red Knives", "The Burning of Tristram"),
    arsenal=Arsenal(("pyre", "frost"), gates=False, spells=("cleanse",)),
    start_gold=220,
    theme="village",
    blurb="The village under the cathedral burns. The Fallen swarm through its lanes, the village dead walk behind "
          "them, and a shaman sings them on.",
    taunt="Every one of them has died before. My shaman sings them up again. When he looks at your fire, "
          "it will falter.",
)

GRAVEYARD = Location(
    key="graveyard",
    name="The Graveyard",
    level=Level(
        name="The Graveyard", width=25, height=14,
        waypoints=((0, 10), (5, 10), (5, 3), (12, 3), (12, 10), (19, 10), (19, 3), (24, 3)),
        doors=((12, 6), (19, 7)),
        obstacles=frozenset({(2, 2), (8, 7), (15, 6), (22, 8), (16, 12), (9, 12), (2, 6)}),
        pools=frozenset({(8, 5), (15, 8), (22, 11)}),
    ),
    waves=_waves(
        ((g("skeleton", 8, 1.3),), 40, 1.0),
        ((g("zombie", 5, 2.0), g("skeleton", 6, 1.0, start=4.0)), 50, 1.1),
        ((g("skeleton", 10, 1.0), g("priest", 1, start=6.0)), 60, 1.2),
        ((g("zombie", 8, 1.5), g("skeleton", 8, 1.0, start=3.0), g("priest", 1, start=5.0)), 70, 1.35),
        ((g("skeleton", 14, 0.7), g("zombie", 6, 1.4, start=5.0), g("priest", 2, 8.0, start=4.0)), 80, 1.5),
        ((g("zombie", 10, 1.1), g("skeleton", 16, 0.6, start=2.0), g("priest", 2, 7.0, start=3.0)), 0, 1.65),
    ),
    wave_names=("Rattling Bones", "The Hungry Dead", "The Priest Walks", "Open Graves", "The Charnel March",
                "All Souls' Night"),
    arsenal=Arsenal(("pyre", "storm", "frost"), gates=True, spells=("cleanse", "smite")),
    start_gold=300,
    theme="graveyard",
    blurb="The dead of Tristram's churchyard have left their graves. The crypt arches still stand, if someone "
          "wards them.",
    taunt="I buried every one of them, and they still come when I call. Build your gates. I will cage the fire "
          "behind them.",
    requires=("tristram",),
)

CATHEDRAL = Location(
    key="cathedral",
    name="The Cathedral",
    level=Level(
        name="The Desecrated Cathedral", width=25, height=14,
        waypoints=((0, 2), (8, 2), (8, 6), (3, 6), (3, 11), (12, 11), (12, 4), (18, 4), (18, 10), (24, 10)),
        doors=((3, 9), (12, 7), (18, 8)),
        obstacles=frozenset({(15, 1), (21, 2), (22, 6), (1, 12), (21, 12), (10, 1)}),
    ),
    waves=_waves(
        ((g("fallen", 14, 0.8),), 40, 1.0),
        ((g("goatman", 8, 1.2), g("shaman", 1, start=6.0)), 50, 1.1),
        ((g("fallen", 16, 0.6), g("goatman", 6, 1.0, start=4.0), g("shaman", 1, start=5.0), g("skeleton", 6, 1.0, start=8.0)), 60, 1.25),
        ((g("goatman", 10, 1.0), g("witch", 1, start=5.0)), 70, 1.4),
        ((g("fallen", 20, 0.5), g("goatman", 8, 0.9, start=3.0), g("witch", 1, start=4.0), g("shaman", 1, start=9.0)), 80, 1.55),
        ((g("goatman", 14, 0.8), g("skeleton", 8, 0.8, start=2.0), g("shaman", 2, 6.0, start=3.0), g("witch", 1, start=6.0)), 90, 1.7),
        ((g("fallen", 24, 0.45), g("goatman", 14, 0.8, start=4.0), g("witch", 2, 8.0, start=3.0),
          g("shaman", 2, 7.0, start=6.0)), 0, 1.9),
    ),
    wave_names=("The Nave Fills", "Horns in the Aisle", "The Warband", "The Blood Witch", "Vespers",
                "The Choir of Curses", "The Lamp Gutters"),
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=("cleanse", "smite", "meteor")),
    start_gold=320,
    theme="cathedral",
    blurb="The nave where the lamp hangs. A torn carpet runs from the portal to the sanctuary gate, past three "
          "arches.",
    taunt="This was my house before it was yours. The witch will make your towers old, and the goatmen do not "
          "fear your thunder.",
    requires=("graveyard",),
)

CATACOMBS = Location(
    key="catacombs",
    name="The Catacombs",
    level=Level(
        name="The Catacombs", width=25, height=14,
        waypoints=((4, 0), (4, 11), (12, 11), (12, 2), (20, 2), (20, 13)),
        doors=((4, 4), (4, 8), (12, 6), (20, 8)),
        obstacles=frozenset({(8, 6), (16, 8), (1, 12), (23, 1), (16, 4), (8, 1), (1, 3), (23, 11)}),
        pools=frozenset({(8, 9), (16, 11), (1, 7)}),
    ),
    waves=_waves(
        ((g("skeleton", 12, 0.9),), 50, 1.3),
        ((g("zombie", 6, 1.6), g("overlord", 1, start=6.0)), 60, 1.4),
        ((g("skeleton", 14, 0.7), g("overlord", 2, 6.0, start=4.0), g("priest", 1, start=5.0)), 70, 1.5),
        ((g("zombie", 8, 1.3), g("skeleton", 10, 0.8, start=3.0), g("witch", 1, start=4.0)), 80, 1.6),
        ((g("overlord", 3, 4.0), g("skeleton", 12, 0.6, start=2.0), g("priest", 1, start=3.0), g("witch", 1, start=8.0)), 90, 1.75),
        ((g("zombie", 10, 1.0), g("overlord", 4, 3.5, start=4.0), g("priest", 1, start=2.0), g("witch", 1, start=7.0)), 100, 1.9),
        ((g("skeleton", 20, 0.5), g("overlord", 5, 3.0, start=3.0), g("zombie", 8, 1.0, start=6.0),
          g("priest", 2, 8.0, start=2.0), g("witch", 2, 8.0, start=6.0)), 0, 2.1),
    ),
    wave_names=("The Bone Halls", "Doorbreaker", "The Ossuary", "Rot Below", "The Overlords' Tread",
                "Iron and Bone", "The Deep Charnel"),
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=ALL_SPELLS),
    start_gold=380,
    theme="catacombs",
    blurb="Under the nave the bone halls run straight and narrow, arch after arch. Overlords break doors for a living.",
    taunt="Four doors between you and the dark. An Overlord needs a few breaths for each, and my priest will "
          "blind whatever watches them.",
    requires=("cathedral",),
)

CAVES = Location(
    key="caves",
    name="The Caves",
    level=Level(
        name="The Caves", width=25, height=14,
        waypoints=((12, 0), (12, 4), (3, 4), (3, 10), (21, 10), (21, 4), (24, 4)),
        doors=((3, 7), (21, 7)),
        obstacles=frozenset({(16, 2), (7, 1), (1, 12), (23, 12), (18, 7)}),
        pools=frozenset({(9, 6), (10, 6), (11, 7), (12, 7), (13, 7), (14, 6), (10, 7), (12, 8)}),
    ),
    waves=_waves(
        ((g("goatman", 10, 1.0),), 50, 1.3),
        ((g("gargoyle", 6, 1.2), g("fallen", 12, 0.6, start=3.0)), 60, 1.4),
        ((g("goatman", 12, 0.9), g("shaman", 1, start=3.0), g("witch", 1, start=7.0)), 70, 1.5),
        ((g("gargoyle", 10, 0.9), g("goatman", 8, 1.0, start=4.0)), 80, 1.6),
        ((g("fallen", 24, 0.4), g("shaman", 2, 5.0, start=2.0), g("witch", 1, start=5.0), g("gargoyle", 6, 1.0, start=8.0)), 90, 1.75),
        ((g("goatman", 14, 0.7), g("gargoyle", 10, 0.8, start=3.0), g("witch", 2, 7.0, start=4.0)), 100, 1.9),
        ((g("gargoyle", 16, 0.6), g("goatman", 16, 0.7, start=2.0), g("fallen", 20, 0.4, start=6.0),
          g("witch", 2, 8.0, start=3.0), g("shaman", 2, 8.0, start=7.0)), 0, 2.1),
    ),
    wave_names=("The Goatman Clans", "Wings in the Dark", "The Den", "The Roost", "Lava Light", "The Stampede",
                "The Burning Vault"),
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=ALL_SPELLS),
    start_gold=380,
    theme="caves",
    blurb="Below the catacombs the caves open onto lava. Gargoyles nest in the vault and fly where they please.",
    taunt="Walls mean nothing to wings. Look up.",
    requires=("catacombs",),
)

HELLS_GATE = Location(
    key="hells_gate",
    name="Hell's Gate",
    level=Level(
        name="Hell's Gate", width=25, height=14,
        waypoints=((0, 2), (6, 2), (6, 11), (12, 11), (12, 2), (18, 2), (18, 11), (24, 11)),
        doors=((6, 7), (12, 6), (18, 7)),
        obstacles=frozenset({(3, 5), (15, 8), (21, 5), (9, 1), (22, 2)}),
        pools=frozenset({(2, 9), (3, 11), (9, 7), (15, 4), (22, 7), (21, 8)}),
    ),
    waves=_waves(
        ((g("fallen", 20, 0.5),), 60, 2.0),
        ((g("goatman", 12, 0.8), g("shaman", 1, start=3.0), g("priest", 1, start=6.0)), 70, 2.1),
        ((g("gargoyle", 10, 0.8), g("overlord", 3, 4.0, start=3.0), g("witch", 1, start=5.0)), 80, 2.2),
        ((g("goatman", 16, 0.7), g("fallen", 24, 0.4, start=2.0), g("shaman", 1, start=3.0), g("priest", 1, start=6.0),
          g("witch", 1, start=9.0)), 90, 2.35),
        ((g("overlord", 5, 3.0), g("gargoyle", 12, 0.7, start=4.0), g("priest", 2, 6.0, start=3.0)), 100, 2.5),
        ((g("goatman", 18, 0.6), g("overlord", 5, 3.0, start=3.0), g("witch", 2, 6.0, start=4.0), g("shaman", 1, start=8.0)), 110, 2.65),
        ((g("fallen", 30, 0.35), g("gargoyle", 14, 0.6, start=3.0), g("overlord", 6, 2.5, start=6.0),
          g("priest", 1, start=4.0), g("witch", 1, start=8.0), g("shaman", 1, start=12.0)), 120, 2.8),
        ((g("azazel", 1, start=4.0), g("goatman", 20, 0.6), g("priest", 1, start=2.0), g("witch", 1, start=6.0),
          g("shaman", 1, start=10.0), g("gargoyle", 10, 0.8, start=10.0)), 0, 3.0),
    ),
    wave_names=("The Gate Opens", "The Council Gathers", "Wings and Iron", "The Horde", "The Siege",
                "The Choir of Hell", "The Last Night", "Azazel the Flayer"),
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=ALL_SPELLS),
    start_gold=450,
    theme="hell",
    blurb="The door your saints built the cathedral on. Azazel the Flayer waits behind it with the council of curses.",
    taunt="I have watched this fight more times than you have drawn breath. In every one of them, the lamp goes out.",
    requires=("caves",),
)

LOCATIONS: dict[str, Location] = {loc.key: loc for loc in (TRISTRAM, GRAVEYARD, CATHEDRAL, CATACOMBS, CAVES, HELLS_GATE)}
ORDER = tuple(LOCATIONS)   # the campaign's order, which the balance tools also use for the points a player holds
LAST = HELLS_GATE.key


def first_offering(thing: str) -> Location:
    """The first location in the campaign that offers a tower kind, a spell, or "gate"."""
    for key in ORDER:
        arsenal = LOCATIONS[key].arsenal
        if thing in arsenal.towers or thing in arsenal.spells or (thing == "gate" and arsenal.gates):
            return LOCATIONS[key]
    raise KeyError(thing)


def offers(location: Location, thing: str) -> bool:
    arsenal = location.arsenal
    return thing in arsenal.towers or thing in arsenal.spells or (thing == "gate" and arsenal.gates)


def idle(location: Location, needs: tuple[str, ...]) -> bool:
    """Whether a skill that works on ``needs`` does nothing here: none of them is offered."""
    return bool(needs) and not any(offers(location, thing) for thing in needs)
