"""The campaign: six locations on the way down to hell, and the sigils a defence earns.

A :class:`Location` is everything one defence needs: its map, its waves, the gold it starts with and what the
player may use there (:class:`Arsenal`, fixed by the location's place in the campaign, so a replay is the same
puzzle). The words for its intro are here too, since they name the rules they describe. ``docs/campaign.md``
is the design.
"""

from __future__ import annotations

from dataclasses import dataclass

from hellward.sim import tuning
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


ALL_TOWERS = ("arrow", "pyre", "storm", "frost", "plague", "ballista")
ALL_SPELLS = ("smite", "hymn", "meteor", "orb")


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


def _corridor_level(name: str, width: int, height: int, waypoints: tuple[tuple[int, int], ...],
                    doors: tuple[tuple[int, int], ...], *,
                    obstacles: frozenset[tuple[int, int]] = frozenset(),
                    pools: frozenset[tuple[int, int]] = frozenset(),
                    extra_routes: tuple[Route, ...] = ()) -> Level:
    """Carve broad monster halls around authored route loops, leaving the rest for towers."""
    routes = (Route("main", waypoints), *extra_routes)
    centres = set().union(*(route.tiles for route in routes))
    portals = {route.entrance for route in routes} | {route.exit for route in routes}
    gate_walls = {(x + dx, y) for x, y in doors for dx in (-1, 1)}
    halls = {(x + dx, y + dy) for x, y in centres
             for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))
             if 0 <= x + dx < width and 0 <= y + dy < height
             and ((0 < x + dx < width - 1 and 0 < y + dy < height - 1)
                  or (x + dx, y + dy) in portals)}
    halls.difference_update(obstacles | pools | gate_walls)
    return Level(name, width, height, waypoints, doors, obstacles, pools, extra_routes,
                 halls=frozenset(halls))


TRISTRAM = Location(
    key="tristram",
    name="Tristram",
    level=_corridor_level(
        name="Tristram", width=33, height=18,
        waypoints=((0, 8), (15, 8), (15, 9), (32, 9)),
        doors=(),
        obstacles=frozenset({(3, 2), (16, 2), (28, 3), (4, 15), (27, 14), (16, 15)}),
        extra_routes=(
            Route("north", ((0, 8), (4, 6), (8, 4), (15, 4), (19, 7), (25, 7), (32, 9))),
            Route("south", ((0, 8), (5, 11), (10, 13), (18, 13), (22, 10), (32, 9))),
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
    arsenal=Arsenal(("arrow",), gates=False, spells=("smite",)),
    start_gold=BALANCE.starting_gold(0),
    theme="village",
    blurb="The village under the cathedral burns. The Fallen swarm through its lanes, the village dead walk behind "
          "them, and a shaman sings them on.",
    taunt="Huddle your towers together, if it comforts you. When my shaman's curse falls, it falls on all of them.",
    lesson="His curses fall on a tower and the towers beside it: spread your arrows.",
    life=BALANCE.location_growth ** 0 * tuning.number("campaign.life.tristram"),
)

GRAVEYARD = Location(
    key="graveyard",
    name="The Graveyard",
    level=_corridor_level(
        name="The Graveyard", width=33, height=18,
        waypoints=((0, 12), (12, 12), (12, 5), (32, 5)),
        doors=((12, 8),),
        obstacles=frozenset({(3, 2), (5, 17), (16, 15), (27, 13), (26, 2)}),
        pools=frozenset({(6, 17), (29, 15)}),
        extra_routes=(
            Route("meander", ((0, 12), (3, 9), (6, 9), (6, 15), (11, 15), (11, 12),
                              (12, 12), (12, 5), (32, 5))),
            Route("side", ((0, 3), (9, 3), (21, 5), (32, 5))),
            Route("side_detour", ((0, 3), (4, 6), (7, 1), (18, 1), (24, 5), (32, 5))),
            Route("breach", ((19, 0), (19, 2), (23, 3), (27, 5), (32, 5))),
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
    arsenal=Arsenal(("arrow",), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(1),
    theme="graveyard",
    blurb="The dead of Tristram's churchyard have left their graves. Two grave roads meet near the crypt arch, "
          "if someone wards it.",
    taunt="I buried every one of them, and they still come when I call. Build your gate. My acolytes will smother "
          "your arrows behind it.",
    lesson="A gate holds the dead in a queue. A hymned tower fires twice as fast, and the acolytes curse it first.",
    requires=("tristram",),
    life=BALANCE.location_growth ** 1 * tuning.number("campaign.life.graveyard"),
)

CATHEDRAL = Location(
    key="cathedral",
    name="The Cathedral",
    level=_corridor_level(
        name="The Desecrated Cathedral", width=33, height=18,
        waypoints=((0, 3), (13, 3), (13, 12), (32, 12)),
        doors=((13, 8),),
        obstacles=frozenset({(2, 8), (18, 3), (26, 3), (3, 16), (27, 16), (20, 6)}),
        extra_routes=(
            Route("meander", ((0, 3), (3, 6), (7, 6), (7, 1), (12, 1), (13, 3), (13, 12), (32, 12))),
            Route("side", ((0, 13), (7, 13), (21, 12), (32, 12))),
            Route("side_detour", ((0, 13), (3, 10), (8, 10), (8, 16), (17, 16), (22, 12), (32, 12))),
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
    arsenal=Arsenal(("arrow", "pyre"), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(2),
    theme="cathedral",
    blurb="The nave where the lamp hangs. Two open aisles lead from separate doors toward one sanctuary arch.",
    taunt="Two nights you have kept my lamp. It changes nothing. The witch will make your towers old, and the "
          "goatmen will take both aisles.",
    lesson="Two aisles split the host: place arrows where they cover both before spending on fire.",
    requires=("graveyard",),
    life=BALANCE.location_growth ** 2 * tuning.number("campaign.life.cathedral"),
)

CATACOMBS = Location(
    key="catacombs",
    name="The Catacombs",
    level=_corridor_level(
        name="The Catacombs", width=33, height=18,
        waypoints=((5, 0), (5, 10), (15, 10), (15, 14), (27, 14), (27, 17)),
        doors=((5, 6),),
        obstacles=frozenset({(2, 3), (11, 2), (17, 3), (2, 14), (31, 2)}),
        pools=frozenset({(10, 15), (14, 5), (30, 14)}),
        extra_routes=(
            Route("meander", ((5, 0), (5, 3), (9, 3), (9, 8), (13, 8), (13, 13),
                              (19, 13), (19, 8), (27, 8), (27, 17))),
            Route("side", ((23, 0), (23, 7), (27, 12), (27, 17))),
            Route("side_detour", ((23, 0), (23, 2), (29, 3), (29, 9), (23, 9), (21, 14),
                                  (27, 14), (27, 17))),
            Route("breach", ((32, 8), (30, 8), (28, 11), (27, 17))),
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
    arsenal=Arsenal(("arrow", "pyre", "frost", "ballista"), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(3),
    theme="catacombs",
    blurb="Under the nave, two bone halls cross an open ossuary. Overlords break gates for a living.",
    taunt="One gate between you and the dark. I have watched the Overlords break it. Why are you "
          "still here?",
    lesson="An Overlord's armor takes half an arrow's hit and little of a Ballista's bolt; frost weakens its blows.",
    requires=("cathedral",),
    life=BALANCE.location_growth ** 3 * tuning.number("campaign.life.catacombs"),
)

CAVES = Location(
    key="caves",
    name="The Caves",
    level=_corridor_level(
        name="The Caves", width=33, height=18,
        waypoints=((16, 0), (16, 9), (27, 9), (27, 5), (32, 5)),
        doors=((16, 4),),
        obstacles=frozenset({(3, 3), (10, 2), (24, 2), (3, 16), (30, 14)}),
        pools=frozenset({(x, y) for x in range(2, 7) for y in range(4, 6)}
                        | {(x, 16) for x in range(13, 19)}),
        extra_routes=(
            Route("meander", ((16, 0), (16, 2), (21, 2), (21, 12), (25, 12), (25, 5), (32, 5))),
            Route("side", ((0, 13), (9, 13), (18, 11), (28, 11), (28, 5), (32, 5))),
            Route("side_detour", ((0, 13), (5, 9), (12, 9), (12, 15), (21, 15), (24, 9), (32, 5))),
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
    arsenal=Arsenal(("arrow", "pyre", "frost", "plague", "ballista"), gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(4),
    theme="caves",
    blurb="Below the catacombs the caves open onto lava. Gargoyles nest in the vault and fly where they please.",
    taunt="Walls mean nothing to wings. Look up. And tell me, keeper: why do my bones never show your face?",
    lesson="Wings ignore the gate, and the lava leaves fewer places to build.",
    requires=("catacombs",),
    life=BALANCE.location_growth ** 4 * tuning.number("campaign.life.caves"),
)

HELLS_GATE = Location(
    key="hells_gate",
    name="Hell's Gate",
    level=_corridor_level(
        name="Hell's Gate", width=33, height=18,
        waypoints=((0, 3), (13, 3), (13, 13), (32, 13)),
        doors=((13, 8),),
        obstacles=frozenset({(2, 2), (27, 2), (2, 16), (19, 6), (29, 16)}),
        pools=frozenset({(5, 16), (18, 5), (3, 8)}),
        extra_routes=(
            Route("meander", ((0, 3), (4, 6), (4, 11), (8, 11), (8, 1), (13, 1),
                              (13, 13), (32, 13))),
            Route("side", ((0, 13), (8, 13), (20, 12), (32, 13))),
            Route("side_detour", ((0, 13), (4, 9), (10, 9), (10, 16), (22, 16), (26, 12), (32, 13))),
            Route("breach", ((22, 0), (22, 2), (24, 4), (29, 9), (31, 13), (32, 13))),
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
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(5),
    theme="hell",
    blurb="The door your saints built the cathedral on. Azazel the Flayer waits behind it with the council of curses.",
    taunt="In every night I have seen, the lamp goes out. I have begun to wonder what I have not seen.",
    lesson="Every curse at once, and Azazel: no element bites him, and the shrine only sends him back to walk again.",
    requires=("caves",),
    life=BALANCE.location_growth ** 5 * tuning.number("campaign.life.hells_gate"),
)


def _water(*blocks: tuple[int, int, int, int]) -> frozenset[tuple[int, int]]:
    """Pools from (x0, y0, x1, y1) blocks, both ends inclusive."""
    return frozenset((x, y) for x0, y0, x1, y1 in blocks for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))


ALL_TOWERS_II = ("arrow", "pyre", "storm", "frost", "plague", "ballista", "altar", "hook", "knife")
EVERY_TOWER = ("arrow", "pyre", "storm", "frost", "plague", "ballista", "altar", "hook", "knife", "grove")


DOCKS = Location(
    key="docks",
    name="Kurast Docks",
    act=2,
    level=_corridor_level(
        name="Kurast Docks", width=33, height=18,
        waypoints=((17, 0), (17, 10), (27, 10), (27, 4), (32, 4)),
        doors=((17, 5),),
        obstacles=frozenset({(4, 2), (9, 10), (30, 10), (6, 14)}),
        pools=_water((0, 16, 32, 17), (2, 11, 5, 13), (11, 14, 15, 15)),
        extra_routes=(
            Route("meander", ((17, 0), (17, 2), (12, 2), (12, 8), (20, 8), (20, 4), (32, 4))),
            Route("side", ((0, 4), (8, 4), (22, 4), (32, 4))),
            Route("side_detour", ((0, 4), (4, 7), (9, 7), (9, 1), (25, 1), (25, 4), (32, 4))),
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
    arsenal=Arsenal(ALL_TOWERS_II, gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(6),
    theme="docks",
    blurb="Kurast's harbour: rotting piers over black water, and the Flayers waiting along them.",
    taunt="You crossed a sea for a lamp that is not yours. My shaman will raise every Flayer you leave whole.",
    lesson="Hooks drag Flayers back under your towers, knives make the gate a kill zone; kill the shaman before it raises the dead.",
    requires=("hells_gate",),
    life=BALANCE.location_growth ** 6 * tuning.number("campaign.life.docks"),
)

SPIDER_FOREST = Location(
    key="spider_forest",
    name="The Spider Forest",
    act=2,
    level=_corridor_level(
        name="The Spider Forest", width=33, height=18,
        waypoints=((9, 0), (9, 9), (22, 9), (22, 14), (32, 14)),
        doors=((9, 5),),
        obstacles=frozenset({(3, 3), (4, 6), (17, 2), (5, 17), (29, 16)}),
        pools=frozenset({(3, 8), (17, 3), (26, 2)}),
        extra_routes=(
            Route("meander", ((9, 0), (9, 2), (14, 2), (14, 13), (18, 13), (18, 5),
                              (25, 5), (25, 14), (32, 14))),
            Route("side", ((0, 14), (8, 14), (21, 13), (32, 14))),
            Route("side_detour", ((0, 14), (4, 10), (12, 10), (12, 16), (22, 16),
                                  (25, 13), (32, 14))),
            Route("breach", ((32, 3), (28, 6), (28, 11), (32, 14))),
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
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("smite", "hymn")),
    start_gold=BALANCE.starting_gold(7),
    theme="spider_forest",
    blurb="The road to the temples, through a forest the spiders own. In a clearing, the druids' ring of oaks.",
    taunt="The old trees have taken your side. Stand close to them, then. One curse will find you all.",
    lesson="Venom barely bites the spiders here. A grove makes a bunch worth its risk.",
    requires=("docks",),
    life=BALANCE.location_growth ** 7 * tuning.number("campaign.life.spider_forest"),
)

JUNGLE = Location(
    key="jungle",
    name="The Flayer Jungle",
    act=2,
    level=_corridor_level(
        name="The Flayer Jungle", width=33, height=18,
        waypoints=((0, 3), (12, 3), (12, 10), (25, 10), (25, 14), (32, 14)),
        doors=((12, 7),),
        obstacles=frozenset({(3, 8), (18, 3), (28, 3), (4, 17), (28, 16)}),
        pools=frozenset({(20, 4), (29, 6), (6, 16)}),
        extra_routes=(
            Route("meander", ((0, 3), (4, 6), (4, 12), (10, 12), (10, 1), (15, 1),
                              (15, 8), (25, 8), (25, 14), (32, 14))),
            Route("side", ((0, 14), (9, 14), (21, 13), (32, 14))),
            Route("side_detour", ((0, 14), (5, 10), (10, 10), (10, 16), (22, 16),
                                  (27, 12), (32, 14))),
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
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("smite", "hymn", "orb")),
    start_gold=BALANCE.starting_gold(8),
    theme="jungle",
    blurb="The jungle closes over two entrances, and the zealots of the fallen church run between the trees.",
    taunt="My inquisitors do not chant. You will know their curse when the ground burns under your towers, and not before.",
    lesson="The inquisitors mark their spot long before the curse falls: kill them first.",
    requires=("spider_forest",),
    life=BALANCE.location_growth ** 8 * tuning.number("campaign.life.jungle"),
)

DROWNED_CITY = Location(
    key="drowned_city",
    name="The Drowned City",
    act=2,
    level=_corridor_level(
        name="The Drowned City", width=33, height=18,
        waypoints=((11, 0), (11, 10), (23, 10), (23, 4), (32, 4)),
        doors=((11, 6),),
        obstacles=frozenset({(3, 12), (7, 2), (20, 3), (28, 15)}),
        pools=_water((2, 15, 8, 16), (12, 15, 17, 16), (25, 15, 30, 16)),
        extra_routes=(
            Route("meander", ((11, 0), (11, 2), (16, 2), (16, 14), (21, 14),
                              (21, 6), (27, 6), (27, 4), (32, 4))),
            Route("side", ((0, 5), (8, 5), (20, 5), (32, 4))),
            Route("side_detour", ((0, 5), (4, 8), (8, 8), (8, 1), (22, 1), (25, 6), (32, 4))),
            Route("breach", ((32, 13), (28, 10), (28, 6), (32, 4))),
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
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=("smite", "hymn", "orb")),
    start_gold=BALANCE.starting_gold(9),
    theme="drowned_city",
    blurb="Half of Kurast has sunk into the swamp: its streets are canals, and the Hulks walk them.",
    taunt="The Hulks were drowned men once. They do not tire, and your gates are cloth to them.",
    lesson="Frost barely slows the drowned; fire and lightning must. The gate falls fast.",
    requires=("jungle",),
    life=BALANCE.location_growth ** 9 * tuning.number("campaign.life.drowned_city"),
)

TRAVINCAL = Location(
    key="travincal",
    name="Travincal",
    act=2,
    level=_corridor_level(
        name="Travincal", width=33, height=18,
        waypoints=((8, 0), (8, 9), (21, 9), (21, 15), (32, 15)),
        doors=((8, 5),),
        obstacles=frozenset({(3, 3), (17, 3), (29, 3), (3, 16), (15, 5)}),
        pools=frozenset({(16, 6), (26, 2), (6, 17)}),
        extra_routes=(
            Route("meander", ((8, 0), (8, 2), (13, 2), (13, 13), (18, 13), (18, 4),
                              (26, 4), (26, 15), (32, 15))),
            Route("side", ((0, 14), (9, 14), (20, 13), (32, 15))),
            Route("side_detour", ((0, 14), (4, 10), (10, 10), (10, 16), (23, 16),
                                  (26, 12), (32, 15))),
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
    lesson="Curses from every side: spread wide, and kill the elders first.",
    requires=("drowned_city",),
    life=BALANCE.location_growth ** 10 * tuning.number("campaign.life.travincal"),
)

TEMPLE = Location(
    key="temple",
    name="The Temple of Light",
    act=2,
    level=_corridor_level(
        name="The Temple of Light", width=33, height=18,
        waypoints=((9, 0), (9, 8), (21, 8), (21, 12), (32, 12)),
        doors=((9, 4),),
        obstacles=frozenset({(3, 3), (17, 3), (28, 2), (4, 16), (27, 16)}),
        pools=frozenset({(3, 8), (17, 15)}),
        extra_routes=(
            Route("meander", ((9, 0), (9, 2), (14, 2), (14, 13), (18, 13),
                              (18, 5), (26, 5), (26, 12), (32, 12))),
            Route("side", ((0, 12), (8, 12), (20, 11), (32, 12))),
            Route("side_detour", ((0, 12), (4, 15), (11, 15), (11, 9), (24, 9),
                                  (27, 12), (32, 12))),
            Route("breach", ((32, 2), (28, 5), (28, 9), (31, 12), (32, 12))),
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
    lesson="Each curse of his that lands burns your mana for every tower it catches: spread out, and spend it first.",
    requires=("travincal",),
    life=BALANCE.location_growth ** 11 * tuning.number("campaign.life.temple"),
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
