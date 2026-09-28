"""The campaign: six locations on the way down to hell, and the sigils a defence earns.

A :class:`Location` is everything one defence needs: its map, its waves, the gold it starts with and what the
player may use there (:class:`Arsenal`, fixed by the location's place in the campaign, so a replay is the same
puzzle). The words for its intro are here too, since they name the rules they describe. ``docs/campaign.md``
is the design.
"""

from __future__ import annotations

from dataclasses import dataclass

from hellward.sim.balance import BALANCE
from hellward.sim.content import Group, Wave
from hellward.sim.level import Level, Route
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
    taunt: str                        # the Bone Priest, who has watched this fight before
    lesson: str                       # the intro's one line of advice: what this place teaches
    requires: tuple[str, ...] = ()    # the location that must be held first
    life: float = 1.0                 # every monster's life here, and the spells' strength, is multiplied by this: the
                                       # location's tuning, by simulation (docs/campaign.md); the waves' own
                                       # life multipliers give the ramp within it
    act: int = 1                      # which act this location belongs to (1 or 2)

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


SIGIL_LIVES = (1, 10, 18)   # sanctuary life to keep for one, two and three sigils (a victory keeps at least one)


def sigils(outcome: str | None, lives: int) -> int:
    """Sigils a defence earns: none for a fall, then one, two or three by the life kept."""
    if outcome != "victory":
        return 0
    return int_sum(1 for need in SIGIL_LIVES if lives >= need)


ALL_TOWERS = ("arrow", "pyre", "storm", "frost", "plague")
ALL_SPELLS = ("cleanse", "smite", "meteor", "orb")


def _waves(stage: int, *rows: tuple[Group, ...]) -> tuple[Wave, ...]:
    waves: list[Wave] = []
    density = BALANCE.wave_density(stage)
    for index, groups in enumerate(rows):
        scaled = tuple(Group(group.kind, max(1, round(group.count * density)), group.interval, group.start, group.route)
                       for group in groups)
        bodies = int_sum(group.count for group in scaled)
        waves.append(Wave(scaled, BALANCE.wave_clear_bonus(stage, index, bodies), BALANCE.wave_growth ** index))
    return tuple(waves)


def g(kind: str, count: int, interval: float = 1.0, start: float = 0.0, *, route: str = "main") -> Group:
    return Group(kind, count, interval, start, route)


TRISTRAM = Location(
    key="tristram",
    name="Tristram",
    level=Level(
        name="Tristram", width=25, height=14,
        waypoints=((0, 6), (12, 6), (12, 7), (24, 7)),
        doors=(),
        obstacles=frozenset({(3, 1), (13, 2), (21, 2), (5, 12), (22, 10), (13, 11)}),
        extra_routes=(
            Route("north", ((0, 6), (4, 4), (9, 4), (15, 6), (24, 7))),
            Route("south", ((0, 6), (5, 9), (12, 9), (18, 7), (24, 7))),
        ),
    ),
    waves=_waves(0,
        (g("fallen", 8, 1.2),),
        (g("fallen", 10, 0.9), g("zombie", 2, 3.0, start=4.0)),
        (g("fallen", 10, 0.8), g("zombie", 3, 2.5, start=2.0), g("shaman", 1, start=5.0)),
        (g("fallen", 16, 0.6), g("zombie", 4, 2.0, start=3.0), g("shaman", 2, 6.0, start=3.0)),
        (g("fallen", 22, 0.5), g("zombie", 6, 1.8, start=4.0), g("shaman", 3, 5.0, start=2.0)),
    ),
    wave_names=("The Fallen Swarm", "The Village Dead", "The Shaman Sings", "Red Knives", "The Burning of Tristram"),
    arsenal=Arsenal(("arrow",), gates=False, spells=("cleanse",)),
    start_gold=BALANCE.starting_gold(0),
    theme="village",
    blurb="The village under the cathedral burns. The Fallen swarm through its lanes, the village dead walk behind "
          "them, and a shaman sings them on.",
    taunt="Huddle your towers together, if it comforts you. When my shaman's curse falls, it falls on all of them.",
    lesson="His curses fall on a tower and the towers beside it: spread your arrows.",
    life=BALANCE.location_growth ** 0,
)

GRAVEYARD = Location(
    key="graveyard",
    name="The Graveyard",
    level=Level(
        name="The Graveyard", width=25, height=14,
        waypoints=((0, 10), (10, 10), (10, 3), (24, 3)),
        doors=((10, 7),),
        obstacles=frozenset({(3, 6), (3, 11), (7, 12), (15, 10), (22, 12)}),
        pools=frozenset({(6, 11), (19, 12)}),
        extra_routes=(
            Route("meander", ((0, 10), (4, 8), (5, 3), (12, 2), (18, 11), (23, 3), (24, 3))),
            Route("side", ((0, 2), (6, 2), (14, 5), (24, 3))),
            Route("side_detour", ((0, 2), (4, 5), (15, 5), (15, 1), (24, 3))),
            Route("breach", ((12, 0), (15, 3), (20, 4), (24, 3))),
        ),
    ),
    waves=_waves(1,
        (g("skeleton", 8, 1.3),),
        (g("zombie", 5, 2.0), g("skeleton", 6, 1.0, start=4.0, route="side")),
        (g("skeleton", 10, 1.0, route="side"), g("priest", 1, start=6.0)),
        (g("zombie", 8, 1.5, route="side"), g("skeleton", 8, 1.0, start=3.0), g("priest", 1, start=5.0)),
        (g("skeleton", 14, 0.7, route="side"), g("zombie", 6, 1.4, start=5.0), g("priest", 2, 8.0, start=4.0)),
        (g("zombie", 10, 1.1, route="side"), g("skeleton", 16, 0.6, start=2.0), g("priest", 2, 7.0, start=3.0)),
    ),
    wave_names=("Rattling Bones", "The Hungry Dead", "The Priest Walks", "Open Graves", "The Charnel March",
                "All Souls' Night"),
    arsenal=Arsenal(("arrow",), gates=True, spells=("cleanse", "smite")),
    start_gold=BALANCE.starting_gold(1),
    theme="graveyard",
    blurb="The dead of Tristram's churchyard have left their graves. Two grave roads meet near the crypt arch, "
          "if someone wards it.",
    taunt="I buried every one of them, and they still come when I call. Build your gate. My acolytes will smother "
          "your arrows behind it.",
    lesson="A gate holds the dead in a queue. Smite on the sign stops a curse, but that leader's next one lands.",
    requires=("tristram",),
    life=BALANCE.location_growth ** 1,
)

CATHEDRAL = Location(
    key="cathedral",
    name="The Cathedral",
    level=Level(
        name="The Desecrated Cathedral", width=25, height=14,
        waypoints=((0, 2), (11, 2), (11, 10), (24, 10)),
        doors=((11, 6),),
        obstacles=frozenset({(2, 5), (8, 1), (21, 2), (22, 6), (2, 12), (20, 12)}),
        extra_routes=(
            Route("meander", ((0, 2), (5, 4), (7, 11), (8, 4), (16, 3), (19, 8), (24, 10))),
            Route("side", ((0, 11), (6, 11), (15, 8), (24, 10))),
            Route("side_detour", ((0, 11), (5, 8), (16, 7), (17, 12), (24, 10))),
        ),
    ),
    waves=_waves(2,
        (g("fallen", 14, 0.8),),
        (g("goatman", 8, 1.2, route="side"), g("shaman", 1, start=6.0)),
        (g("fallen", 16, 0.6, route="side"), g("goatman", 6, 1.0, start=4.0), g("shaman", 1, start=5.0), g("skeleton", 6, 1.0, start=8.0)),
        (g("goatman", 10, 1.0, route="side"), g("witch", 1, start=5.0)),
        (g("fallen", 20, 0.5, route="side"), g("goatman", 8, 0.9, start=3.0), g("witch", 1, start=4.0), g("shaman", 1, start=9.0)),
        (g("goatman", 14, 0.8), g("skeleton", 8, 0.8, start=2.0, route="side"), g("shaman", 2, 6.0, start=3.0), g("witch", 1, start=6.0)),
        (g("fallen", 24, 0.45), g("goatman", 14, 0.8, start=4.0, route="side"), g("witch", 2, 8.0, start=3.0),
          g("shaman", 2, 7.0, start=6.0)),
    ),
    wave_names=("The Nave Fills", "Horns in the Aisle", "The Warband", "The Blood Witch", "Vespers",
                "The Choir of Curses", "The Lamp Gutters"),
    arsenal=Arsenal(("arrow", "pyre"), gates=True, spells=("cleanse", "smite")),
    start_gold=BALANCE.starting_gold(2),
    theme="cathedral",
    blurb="The nave where the lamp hangs. Two open aisles lead from separate doors toward one sanctuary arch.",
    taunt="Two nights you have kept my lamp. It changes nothing. The witch will make your towers old, and the "
          "goatmen will take both aisles.",
    lesson="Two aisles split the host: place arrows where they cover both before spending on fire.",
    requires=("graveyard",),
    life=BALANCE.location_growth ** 2,
)

CATACOMBS = Location(
    key="catacombs",
    name="The Catacombs",
    level=Level(
        name="The Catacombs", width=25, height=14,
        waypoints=((4, 0), (4, 8), (12, 8), (12, 11), (20, 11), (20, 13)),
        doors=((4, 5),),
        obstacles=frozenset({(1, 3), (8, 1), (14, 3), (1, 11), (23, 1)}),
        pools=frozenset({(2, 9), (13, 5), (23, 10)}),
        extra_routes=(
            Route("meander", ((4, 0), (7, 4), (9, 10), (15, 11), (14, 5), (20, 10), (20, 13))),
            Route("side", ((17, 0), (17, 5), (15, 8), (20, 13))),
            Route("side_detour", ((17, 0), (17, 2), (19, 5), (21, 3), (21, 9), (20, 13))),
            Route("breach", ((24, 6), (21, 7), (20, 13))),
        ),
    ),
    waves=_waves(3,
        (g("skeleton", 12, 0.9),),
        (g("zombie", 6, 1.6, route="side"), g("overlord", 1, start=6.0)),
        (g("skeleton", 14, 0.7, route="side"), g("overlord", 2, 6.0, start=4.0), g("priest", 1, start=5.0)),
        (g("zombie", 8, 1.3, route="side"), g("skeleton", 10, 0.8, start=3.0), g("witch", 1, start=4.0)),
        (g("overlord", 3, 4.0), g("skeleton", 12, 0.6, start=2.0, route="side"), g("priest", 1, start=3.0), g("witch", 1, start=8.0)),
        (g("zombie", 10, 1.0, route="side"), g("overlord", 4, 3.5, start=4.0), g("priest", 1, start=2.0), g("witch", 1, start=7.0)),
        (g("skeleton", 20, 0.5, route="side"), g("overlord", 5, 3.0, start=3.0), g("zombie", 8, 1.0, start=6.0),
          g("priest", 2, 8.0, start=2.0), g("witch", 2, 8.0, start=6.0)),
    ),
    wave_names=("The Bone Halls", "Doorbreaker", "The Ossuary", "Rot Below", "The Overlords' Tread",
                "Iron and Bone", "The Deep Charnel"),
    arsenal=Arsenal(("arrow", "pyre", "frost"), gates=True, spells=("cleanse", "smite")),
    start_gold=BALANCE.starting_gold(3),
    theme="catacombs",
    blurb="Under the nave, two bone halls cross an open ossuary. Overlords break gates for a living.",
    taunt="One gate between you and the dark. I have watched the Overlords break it. Why are you "
          "still here?",
    lesson="Overlords break the gate in seconds; frost weakens their blows while arrows keep working.",
    requires=("cathedral",),
    life=BALANCE.location_growth ** 3,
)

CAVES = Location(
    key="caves",
    name="The Caves",
    level=Level(
        name="The Caves", width=25, height=14,
        waypoints=((12, 0), (12, 6), (21, 6), (21, 4), (24, 4)),
        doors=((12, 3),),
        obstacles=frozenset({(3, 3), (8, 2), (18, 2), (2, 12), (22, 11)}),
        pools=frozenset({(x, y) for x in range(8, 16) for y in (11, 12)}
                        | {(x, y) for x in range(2, 6) for y in (5, 6)}),
        extra_routes=(
            Route("meander", ((12, 0), (15, 3), (17, 10), (18, 4), (24, 4))),
            Route("side", ((0, 10), (7, 10), (14, 8), (22, 7), (23, 4), (24, 4))),
            Route("side_detour", ((0, 10), (5, 8), (16, 8), (14, 10), (19, 5), (24, 4))),
        ),
    ),
    waves=_waves(4,
        (g("goatman", 10, 1.0),),
        (g("gargoyle", 6, 1.2, route="side"), g("fallen", 12, 0.6, start=3.0)),
        (g("goatman", 12, 0.9, route="side"), g("shaman", 1, start=3.0), g("witch", 1, start=7.0)),
        (g("gargoyle", 10, 0.9, route="side"), g("goatman", 8, 1.0, start=4.0)),
        (g("fallen", 24, 0.4, route="side"), g("shaman", 2, 5.0, start=2.0), g("witch", 1, start=5.0), g("gargoyle", 6, 1.0, start=8.0)),
        (g("goatman", 14, 0.7, route="side"), g("gargoyle", 10, 0.8, start=3.0), g("witch", 2, 7.0, start=4.0)),
        (g("gargoyle", 16, 0.6, route="side"), g("goatman", 16, 0.7, start=2.0), g("fallen", 20, 0.4, start=6.0),
          g("witch", 2, 8.0, start=3.0), g("shaman", 2, 8.0, start=7.0), g("fallen", 30, 0.3, start=20.0)),
    ),
    wave_names=("The Goatman Clans", "Wings in the Dark", "The Den", "The Roost", "Lava Light", "The Stampede",
                "The Burning Vault"),
    arsenal=Arsenal(("arrow", "pyre", "frost", "plague"), gates=True, spells=("cleanse", "smite")),
    start_gold=BALANCE.starting_gold(4),
    theme="caves",
    blurb="Below the catacombs the caves open onto lava. Gargoyles nest in the vault and fly where they please.",
    taunt="Walls mean nothing to wings. Look up. And tell me, keeper: why do my bones never show your face?",
    lesson="Wings ignore the gate, and the lava leaves fewer places to build.",
    requires=("catacombs",),
    life=BALANCE.location_growth ** 4,
)

HELLS_GATE = Location(
    key="hells_gate",
    name="Hell's Gate",
    level=Level(
        name="Hell's Gate", width=25, height=14,
        waypoints=((0, 2), (10, 2), (10, 11), (24, 11)),
        doors=((10, 6),),
        obstacles=frozenset({(3, 6), (5, 1), (22, 3), (2, 12), (19, 12)}),
        pools=frozenset({(4, 11), (14, 6), (3, 9)}),
        extra_routes=(
            Route("meander", ((0, 2), (4, 4), (5, 11), (7, 11), (8, 3), (18, 3), (21, 9), (24, 11))),
            Route("side", ((0, 10), (7, 10), (15, 8), (24, 11))),
            Route("side_detour", ((0, 10), (5, 7), (16, 7), (21, 6), (20, 9), (24, 11))),
            Route("breach", ((13, 0), (16, 3), (20, 6), (23, 9), (23, 11), (24, 11))),
        ),
    ),
    waves=_waves(5,
        (g("fallen", 20, 0.5),),
        (g("goatman", 12, 0.8, route="side"), g("shaman", 1, start=3.0), g("priest", 1, start=6.0)),
        (g("gargoyle", 10, 0.8, route="side"), g("overlord", 3, 4.0, start=3.0), g("witch", 1, start=5.0)),
        (g("goatman", 16, 0.7), g("fallen", 24, 0.4, start=2.0, route="side"), g("shaman", 1, start=3.0), g("priest", 1, start=6.0),
          g("witch", 1, start=9.0)),
        (g("overlord", 5, 3.0), g("gargoyle", 12, 0.7, start=4.0, route="side"), g("priest", 2, 6.0, start=3.0)),
        (g("goatman", 18, 0.6, route="side"), g("overlord", 5, 3.0, start=3.0), g("witch", 2, 6.0, start=4.0), g("shaman", 1, start=8.0)),
        (g("fallen", 30, 0.35), g("gargoyle", 14, 0.6, start=3.0, route="side"), g("overlord", 6, 2.5, start=6.0),
          g("priest", 1, start=4.0), g("witch", 1, start=8.0), g("shaman", 1, start=12.0)),
        (g("azazel", 1, start=4.0), g("goatman", 20, 0.6), g("priest", 1, start=2.0), g("witch", 1, start=6.0),
          g("shaman", 1, start=10.0), g("gargoyle", 10, 0.8, start=10.0), g("fallen", 30, 0.3, start=22.0, route="side")),
    ),
    wave_names=("The Gate Opens", "The Council Gathers", "Wings and Iron", "The Horde", "The Siege",
                "The Choir of Hell", "The Last Night", "Azazel the Flayer"),
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=("cleanse", "smite")),
    start_gold=BALANCE.starting_gold(5),
    theme="hell",
    blurb="The door your saints built the cathedral on. Azazel the Flayer waits behind it with the council of curses.",
    taunt="In every night I have seen, the lamp goes out. I have begun to wonder what I have not seen.",
    lesson="Every curse at once, and Azazel will not burn.",
    requires=("caves",),
    life=BALANCE.location_growth ** 5,
)


def _water(*blocks: tuple[int, int, int, int]) -> frozenset[tuple[int, int]]:
    """Pools from (x0, y0, x1, y1) blocks, both ends inclusive."""
    return frozenset((x, y) for x0, y0, x1, y1 in blocks for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))


ALL_TOWERS_II = ("arrow", "pyre", "storm", "frost", "plague", "altar")
EVERY_TOWER = ("arrow", "pyre", "storm", "frost", "plague", "altar", "grove")


DOCKS = Location(
    key="docks",
    name="Kurast Docks",
    act=2,
    level=Level(
        name="Kurast Docks", width=25, height=14,
        waypoints=((13, 0), (13, 8), (21, 8), (21, 3), (24, 3)),
        doors=((13, 5),),
        obstacles=frozenset({(3, 5), (10, 6), (23, 7), (5, 10)}),
        pools=_water((0, 12, 24, 13), (2, 8, 5, 9), (10, 10, 14, 10)),
        extra_routes=(
            Route("meander", ((13, 0), (13, 2), (8, 4), (8, 9), (18, 8), (24, 3))),
            Route("side", ((0, 3), (7, 3), (18, 3), (24, 3))),
            Route("side_detour", ((0, 3), (5, 2), (19, 2), (18, 5), (24, 3))),
        ),
    ),
    waves=_waves(6,
        (g("flayer", 14, 0.7),),
        (g("zealot", 8, 1.2, route="side"), g("flayer", 8, 0.6, start=5.0)),
        (g("flayer", 16, 0.55, route="side"), g("fetish", 1, start=4.0)),
        (g("zealot", 10, 1.0, route="side"), g("flayer", 12, 0.5, start=3.0), g("fetish", 1, start=6.0)),
        (g("flayer", 24, 0.4, route="side"), g("zealot", 8, 0.9, start=4.0), g("fetish", 2, 6.0, start=3.0)),
        (g("zealot", 14, 0.8, route="side"), g("flayer", 30, 0.35, start=2.0), g("fetish", 2, 7.0, start=4.0)),
    ),
    wave_names=("The Piers", "Zealots Ashore", "The Shaman's Song", "Faith and Knives", "Low Tide", "The Harbour Burns"),
    arsenal=Arsenal(ALL_TOWERS_II, gates=True, spells=("cleanse", "smite")),
    start_gold=BALANCE.starting_gold(6),
    theme="docks",
    blurb="Kurast's harbour: rotting piers over black water, and the Flayers waiting along them.",
    taunt="You crossed a sea for a lamp that is not yours. My shaman will raise every Flayer you leave whole.",
    lesson="Amplify where your towers' reaches cross; kill the shaman before it raises the dead.",
    requires=("hells_gate",),
    life=BALANCE.location_growth ** 6,
)

SPIDER_FOREST = Location(
    key="spider_forest",
    name="The Spider Forest",
    act=2,
    level=Level(
        name="The Spider Forest", width=25, height=14,
        waypoints=((7, 0), (7, 7), (17, 7), (17, 11), (24, 11)),
        doors=((7, 4),),
        obstacles=frozenset({(2, 3), (4, 5), (12, 2), (15, 1), (22, 12), (4, 12)}),
        pools=frozenset({(3, 6), (12, 12), (18, 2)}),
        extra_routes=(
            Route("meander", ((7, 0), (7, 2), (7, 9), (11, 3), (20, 5), (21, 9), (24, 11))),
            Route("side", ((0, 11), (6, 11), (14, 9), (24, 11))),
            Route("side_detour", ((0, 11), (4, 8), (13, 8), (17, 5), (20, 10), (24, 11))),
            Route("breach", ((24, 2), (21, 4), (21, 8), (24, 11))),
        ),
    ),
    waves=_waves(7,
        (g("spider", 10, 1.0),),
        (g("bat", 12, 0.6, route="side"), g("spider", 6, 1.0, start=4.0)),
        (g("spider", 12, 0.8, route="side"), g("witch", 1, start=5.0)),
        (g("flayer", 16, 0.5, route="side"), g("spider", 8, 0.8, start=3.0), g("fetish", 1, start=4.0)),
        (g("bat", 16, 0.5, route="side"), g("spider", 12, 0.7, start=3.0), g("witch", 1, start=4.0), g("fetish", 1, start=8.0)),
        (g("spider", 16, 0.6, route="side"), g("flayer", 20, 0.4, start=3.0), g("witch", 2, 7.0, start=3.0)),
        (g("spider", 24, 0.45), g("bat", 20, 0.4, start=4.0, route="side"), g("witch", 1, start=3.0), g("fetish", 2, 6.0, start=6.0)),
    ),
    wave_names=("Webs", "Dusk Wings", "The Witch Walks", "Brood", "The Canopy Moves", "Old Growth", "The Queen's Children"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("cleanse", "smite")),
    start_gold=BALANCE.starting_gold(7),
    theme="spider_forest",
    blurb="The road to the temples, through a forest the spiders own. In a clearing, the druids' ring of oaks.",
    taunt="The old trees have taken your side. Stand close to them, then. One curse will find you all.",
    lesson="Poison is useless here. A grove makes a bunch worth its risk.",
    requires=("docks",),
    life=BALANCE.location_growth ** 7,
)

JUNGLE = Location(
    key="jungle",
    name="The Flayer Jungle",
    act=2,
    level=Level(
        name="The Flayer Jungle", width=25, height=14,
        waypoints=((0, 2), (9, 2), (9, 8), (19, 8), (19, 11), (24, 11)),
        doors=((9, 5),),
        obstacles=frozenset({(2, 6), (12, 1), (17, 2), (3, 12), (20, 5)}),
        pools=frozenset({(12, 5), (22, 5), (6, 12)}),
        extra_routes=(
            Route("meander", ((0, 2), (5, 4), (4, 11), (11, 11), (15, 4), (20, 7), (24, 11))),
            Route("side", ((0, 11), (8, 11), (16, 9), (24, 11))),
            Route("side_detour", ((0, 11), (5, 8), (15, 7), (16, 11), (21, 9), (24, 11))),
        ),
    ),
    waves=_waves(8,
        (g("flayer", 18, 0.5),),
        (g("zealot", 10, 1.0, route="side"), g("inquisitor", 1, start=6.0)),
        (g("spider", 12, 0.7, route="side"), g("flayer", 14, 0.5, start=3.0), g("fetish", 1, start=4.0)),
        (g("zealot", 12, 0.9, route="side"), g("inquisitor", 2, 8.0, start=3.0)),
        (g("flayer", 26, 0.4, route="side"), g("fetish", 2, 6.0, start=2.0), g("spider", 10, 0.7, start=6.0)),
        (g("zealot", 16, 0.7), g("spider", 12, 0.6, start=3.0, route="side"), g("inquisitor", 2, 7.0, start=3.0), g("fetish", 1, start=8.0)),
        (g("zealot", 18, 0.6, route="side"), g("flayer", 24, 0.4, start=2.0), g("inquisitor", 2, 6.0, start=3.0), g("fetish", 2, 7.0, start=5.0)),
    ),
    wave_names=("Green Gloom", "White and Gold", "The Hunt", "Inquisition", "Blood Sport", "The March", "No Prayer"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("cleanse", "smite", "orb")),
    start_gold=BALANCE.starting_gold(8),
    theme="jungle",
    blurb="The jungle closes over two entrances, and the zealots of the fallen church run between the trees.",
    taunt="My inquisitors do not chant. You will know their curse when the ground burns under your towers, and not before.",
    lesson="The inquisitors curse without a chant: ward the marked towers, and kill them first.",
    requires=("spider_forest",),
    life=BALANCE.location_growth ** 8,
)

DROWNED_CITY = Location(
    key="drowned_city",
    name="The Drowned City",
    act=2,
    level=Level(
        name="The Drowned City", width=25, height=14,
        waypoints=((8, 0), (8, 8), (17, 8), (17, 3), (24, 3)),
        doors=((8, 6),),
        obstacles=frozenset({(3, 6), (12, 6), (2, 8), (1, 1)}),
        pools=_water((1, 10, 5, 11), (10, 10, 15, 11), (19, 10, 22, 11)),
        extra_routes=(
            Route("meander", ((8, 0), (8, 8), (11, 9), (16, 1), (20, 8), (23, 3), (24, 3))),
            Route("side", ((0, 4), (5, 4), (14, 4), (24, 3))),
            Route("side_detour", ((0, 4), (4, 2), (15, 2), (18, 7), (24, 3))),
            Route("breach", ((24, 10), (21, 8), (21, 5), (24, 3))),
        ),
    ),
    waves=_waves(9,
        (g("drowned", 8, 1.4),),
        (g("bat", 14, 0.5, route="side"), g("drowned", 6, 1.3, start=4.0)),
        (g("drowned", 10, 1.2, route="side"), g("hulk", 1, start=8.0), g("inquisitor", 1, start=4.0)),
        (g("drowned", 14, 1.0), g("witch", 1, start=4.0), g("bat", 10, 0.5, start=8.0, route="side")),
        (g("hulk", 3, 4.0), g("drowned", 12, 0.9, start=2.0, route="side"), g("inquisitor", 1, start=3.0), g("witch", 1, start=7.0)),
        (g("drowned", 18, 0.8, route="side"), g("hulk", 3, 4.0, start=4.0), g("bat", 14, 0.45, start=6.0), g("inquisitor", 2, 7.0, start=3.0)),
        (g("hulk", 5, 3.5), g("drowned", 20, 0.7, start=2.0), g("witch", 2, 8.0, start=3.0), g("inquisitor", 1, start=6.0),
          g("bat", 26, 0.35, start=14.0, route="side")),
    ),
    wave_names=("Black Water", "Wings over the Canals", "The First Hulk", "Tide of the Dead", "Thorns", "The Flood",
                "What the Swamp Keeps"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("cleanse", "smite", "orb")),
    start_gold=BALANCE.starting_gold(9),
    theme="drowned_city",
    blurb="Half of Kurast has sunk into the swamp: its streets are canals, and the Hulks walk them.",
    taunt="The Hulks were drowned men once. They do not tire, and your gates are cloth to them.",
    lesson="Frost barely slows the drowned; fire and lightning must. The gate falls fast.",
    requires=("jungle",),
    life=BALANCE.location_growth ** 9,
)

TRAVINCAL = Location(
    key="travincal",
    name="Travincal",
    act=2,
    level=Level(
        name="Travincal", width=25, height=14,
        waypoints=((6, 0), (6, 7), (16, 7), (16, 12), (24, 12)),
        doors=((6, 4),),
        obstacles=frozenset({(2, 3), (13, 2), (22, 4), (2, 12), (11, 5)}),
        pools=frozenset({(12, 5), (19, 3), (8, 12)}),
        extra_routes=(
            Route("meander", ((6, 0), (6, 2), (6, 10), (10, 3), (18, 5), (21, 9), (24, 12))),
            Route("side", ((0, 11), (8, 11), (16, 9), (24, 12))),
            Route("side_detour", ((0, 11), (4, 8), (13, 8), (17, 5), (20, 10), (24, 12))),
        ),
    ),
    waves=_waves(10,
        (g("zealot", 12, 0.9),),
        (g("flayer", 18, 0.5, route="side"), g("fetish", 1, start=3.0), g("inquisitor", 1, start=6.0)),
        (g("hulk", 2, 5.0), g("zealot", 10, 0.8, start=2.0, route="side"), g("priest", 1, start=4.0)),
        (g("zealot", 14, 0.7, route="side"), g("witch", 1, start=3.0), g("shaman", 1, start=5.0), g("inquisitor", 1, start=8.0)),
        (g("bat", 20, 0.4, route="side"), g("hulk", 3, 4.0, start=4.0), g("fetish", 1, start=3.0), g("priest", 1, start=7.0)),
        (g("flayer", 26, 0.35, route="side"), g("zealot", 14, 0.7, start=3.0), g("witch", 1, start=2.0), g("inquisitor", 1, start=5.0),
          g("priest", 1, start=8.0)),
        (g("hulk", 5, 3.0), g("zealot", 16, 0.6, start=2.0, route="side"), g("fetish", 1, start=2.0), g("shaman", 1, start=4.0),
          g("witch", 1, start=6.0), g("inquisitor", 1, start=8.0), g("priest", 1, start=10.0)),
        (g("zealot", 20, 0.5), g("hulk", 4, 3.5, start=3.0), g("inquisitor", 2, 6.0, start=2.0), g("witch", 1, start=5.0),
          g("priest", 1, start=8.0), g("bat", 30, 0.3, start=14.0, route="side")),
    ),
    wave_names=("The Terrace", "The First Elders", "Iron Faith", "The Council Speaks", "Wings of the Council",
                "Every Voice", "The Council Entire", "The Last Vote"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=BALANCE.starting_gold(10),
    theme="travincal",
    blurb="The temple terrace where the High Council meets, under the mother lamp. Every elder curses.",
    taunt="Turn back, and I will leave Tristram's lamp alone. It is a small lamp. No one would miss it.",
    lesson="Curses from every side: spread wide, ward what matters, and kill the elders first.",
    requires=("drowned_city",),
    life=BALANCE.location_growth ** 10,
)

TEMPLE = Location(
    key="temple",
    name="The Temple of Light",
    act=2,
    level=Level(
        name="The Temple of Light", width=25, height=14,
        waypoints=((7, 0), (7, 6), (16, 6), (16, 9), (24, 9)),
        doors=((7, 3),),
        obstacles=frozenset({(2, 3), (11, 1), (18, 1), (3, 6), (12, 12), (22, 12)}),
        pools=frozenset({(3, 8), (18, 10)}),
        extra_routes=(
            Route("meander", ((7, 0), (7, 2), (11, 3), (13, 11), (19, 4), (21, 7), (24, 9))),
            Route("side", ((0, 9), (6, 9), (14, 8), (24, 9))),
            Route("side_detour", ((0, 9), (5, 11), (17, 11), (16, 8), (24, 9))),
            Route("breach", ((24, 1), (21, 3), (21, 6), (24, 9))),
        ),
    ),
    waves=_waves(11,
        (g("zealot", 14, 0.8),),
        (g("drowned", 10, 1.1, route="side"), g("priest", 1, start=3.0), g("inquisitor", 1, start=7.0)),
        (g("zealot", 16, 0.7, route="side"), g("drowned", 8, 1.0, start=3.0), g("bat", 14, 0.45, start=8.0)),
        (g("zealot", 14, 0.7, route="side"), g("priest", 2, 6.0, start=2.0), g("inquisitor", 1, start=5.0)),
        (g("drowned", 16, 0.8), g("bat", 18, 0.4, start=3.0, route="side"), g("inquisitor", 2, 7.0, start=3.0)),
        (g("zealot", 20, 0.55), g("drowned", 12, 0.8, start=3.0, route="side"), g("priest", 1, start=3.0), g("inquisitor", 1, start=6.0)),
        (g("bone_priest", 1, start=6.0), g("zealot", 16, 0.6), g("priest", 1, start=2.0), g("inquisitor", 1, start=8.0),
          g("bat", 30, 0.3, start=16.0, route="side")),
    ),
    wave_names=("The Doors Open", "Acolytes", "Gold and Rot", "The Choir", "The Oil Runs Low", "The Lamp Dims",
                "The Bone Priest"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=BALANCE.starting_gold(11),
    theme="temple",
    blurb="The Temple of Light, where the mother lamp hangs dim over the altar and the Bone Priest waits beneath it.",
    taunt="I cannot see you in the bones. So I have come to see you myself.",
    lesson="Each curse of his that lands burns your mana for every tower it catches: spread out, and smite his chant.",
    requires=("travincal",),
    life=BALANCE.location_growth ** 11,
)

LOCATIONS: dict[str, Location] = {loc.key: loc for loc in (
    TRISTRAM, GRAVEYARD, CATHEDRAL, CATACOMBS, CAVES, HELLS_GATE,
    DOCKS, SPIDER_FOREST, JUNGLE, DROWNED_CITY, TRAVINCAL, TEMPLE
)}
ORDER = tuple(LOCATIONS)   # the campaign's order, which the balance tools also use for the points a player holds
ACT_NAMES: dict[int, str] = {1: "The Descent", 2: "The Drowned Temples"}
ACT_ENDS: dict[int, str] = {1: "hells_gate", 2: "temple"}
ACTS: dict[int, tuple[str, ...]] = {
    1: ("tristram", "graveyard", "cathedral", "catacombs", "caves", "hells_gate"),
    2: ("docks", "spider_forest", "jungle", "drowned_city", "travincal", "temple"),
}


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
