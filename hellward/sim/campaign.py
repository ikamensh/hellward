"""The campaign: six locations on the way down to hell, and the sigils a defence earns.

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
    taunt="Huddle your towers together, if it comforts you. When my shaman's curse falls, it falls on all of them.",
    lesson="His curses fall on a tower and the towers beside it: spread your fire and frost.",
    life=1.49,
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
    taunt="I buried every one of them, and they still come when I call. Build your gates. My acolytes will cage "
          "the fire behind them.",
    lesson="A gate holds the dead in a queue, and Smite on the sign stops a curse before it comes.",
    requires=("tristram",),
    life=1.46,
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
    taunt="Two nights you have kept my lamp. It changes nothing. The witch will make your towers old, and the "
          "goatmen do not fear your thunder.",
    lesson="Goatmen shrug off lightning and skeletons venom: mix your towers by what comes.",
    requires=("graveyard",),
    life=3.27,
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
    taunt="Four doors between you and the dark. I have watched the Overlords break every one of them. Why are you "
          "still here?",
    lesson="Overlords break gates in seconds; frost weakens their blows and venom seeks the biggest.",
    requires=("cathedral",),
    life=2.0,
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
          g("witch", 2, 8.0, start=3.0), g("shaman", 2, 8.0, start=7.0), g("fallen", 30, 0.3, start=20.0)), 0, 2.1),
    ),
    wave_names=("The Goatman Clans", "Wings in the Dark", "The Den", "The Roost", "Lava Light", "The Stampede",
                "The Burning Vault"),
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=ALL_SPELLS),
    start_gold=380,
    theme="caves",
    blurb="Below the catacombs the caves open onto lava. Gargoyles nest in the vault and fly where they please.",
    taunt="Walls mean nothing to wings. Look up. And tell me, keeper: why do my bones never show your face?",
    lesson="Wings ignore gates, and the lava leaves few places to build.",
    requires=("catacombs",),
    life=2.54,
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
          g("shaman", 1, start=10.0), g("gargoyle", 10, 0.8, start=10.0), g("fallen", 30, 0.3, start=22.0)), 0, 3.0),
    ),
    wave_names=("The Gate Opens", "The Council Gathers", "Wings and Iron", "The Horde", "The Siege",
                "The Choir of Hell", "The Last Night", "Azazel the Flayer"),
    arsenal=Arsenal(ALL_TOWERS, gates=True, spells=ALL_SPELLS),
    start_gold=450,
    theme="hell",
    blurb="The door your saints built the cathedral on. Azazel the Flayer waits behind it with the council of curses.",
    taunt="In every night I have seen, the lamp goes out. I have begun to wonder what I have not seen.",
    lesson="Every curse at once, and Azazel will not burn.",
    requires=("caves",),
    life=1.41,
)


def _water(*blocks: tuple[int, int, int, int]) -> frozenset[tuple[int, int]]:
    """Pools from (x0, y0, x1, y1) blocks, both ends inclusive."""
    return frozenset((x, y) for x0, y0, x1, y1 in blocks for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))


ALL_TOWERS_II = ("pyre", "storm", "frost", "plague", "altar")
EVERY_TOWER = ("pyre", "storm", "frost", "plague", "altar", "grove")


DOCKS = Location(
    key="docks",
    name="Kurast Docks",
    act=2,
    level=Level(
        name="Kurast Docks", width=25, height=14,
        waypoints=((0, 3), (8, 3), (8, 10), (16, 10), (16, 3), (24, 3)),
        doors=((8, 6), (16, 6)),
        obstacles=frozenset({(3, 1), (12, 1), (21, 1), (20, 5)}),
        pools=_water((0, 12, 24, 13), (10, 5, 14, 8), (0, 6, 5, 11), (19, 7, 24, 11)),
    ),
    waves=_waves(
        ((g("flayer", 14, 0.7),), 40, 1.0),
        ((g("zealot", 8, 1.2), g("flayer", 8, 0.6, start=5.0)), 50, 1.1),
        ((g("flayer", 16, 0.55), g("fetish", 1, start=4.0)), 60, 1.2),
        ((g("zealot", 10, 1.0), g("flayer", 12, 0.5, start=3.0), g("fetish", 1, start=6.0)), 70, 1.35),
        ((g("flayer", 24, 0.4), g("zealot", 8, 0.9, start=4.0), g("fetish", 2, 6.0, start=3.0)), 80, 1.5),
        ((g("zealot", 14, 0.8), g("flayer", 30, 0.35, start=2.0), g("fetish", 2, 7.0, start=4.0)), 0, 1.7),
    ),
    wave_names=("The Piers", "Zealots Ashore", "The Shaman's Song", "Faith and Knives", "Low Tide", "The Harbour Burns"),
    arsenal=Arsenal(ALL_TOWERS_II, gates=True, spells=ALL_SPELLS),
    start_gold=420,
    theme="docks",
    blurb="Kurast's harbour: rotting piers over black water, and the Flayers waiting along them.",
    taunt="You crossed a sea for a lamp that is not yours. My shaman will raise every Flayer you leave whole.",
    lesson="Amplify where your towers' reaches cross; kill the shaman, or burst the dead so they stay down.",
    requires=("hells_gate",),
)

SPIDER_FOREST = Location(
    key="spider_forest",
    name="The Spider Forest",
    act=2,
    level=Level(
        name="The Spider Forest", width=25, height=14,
        waypoints=((0, 11), (4, 11), (4, 2), (10, 2), (10, 8), (14, 8), (14, 4), (20, 4), (20, 11), (24, 11)),
        doors=((4, 6), (20, 8)),
        obstacles=frozenset({(2, 4), (2, 8), (7, 5), (7, 9), (12, 5), (12, 11), (17, 1), (17, 7), (22, 2), (22, 7),
                             (7, 12), (16, 11), (1, 1), (23, 13)}),
        pools=frozenset({(6, 6), (8, 11), (17, 9), (23, 5)}),
    ),
    waves=_waves(
        ((g("spider", 10, 1.0),), 40, 1.0),
        ((g("bat", 12, 0.6), g("spider", 6, 1.0, start=4.0)), 50, 1.1),
        ((g("spider", 12, 0.8), g("witch", 1, start=5.0)), 60, 1.2),
        ((g("flayer", 16, 0.5), g("spider", 8, 0.8, start=3.0), g("fetish", 1, start=4.0)), 70, 1.35),
        ((g("bat", 16, 0.5), g("spider", 12, 0.7, start=3.0), g("witch", 1, start=4.0), g("fetish", 1, start=8.0)), 80, 1.5),
        ((g("spider", 16, 0.6), g("flayer", 20, 0.4, start=3.0), g("witch", 2, 7.0, start=3.0)), 90, 1.65),
        ((g("spider", 24, 0.45), g("bat", 20, 0.4, start=4.0), g("witch", 1, start=3.0), g("fetish", 2, 6.0, start=6.0)), 0, 1.85),
    ),
    wave_names=("Webs", "Dusk Wings", "The Witch Walks", "Brood", "The Canopy Moves", "Old Growth", "The Queen's Children"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=440,
    theme="spider_forest",
    blurb="The road to the temples, through a forest the spiders own. In a clearing, the druids' ring of oaks.",
    taunt="The old trees have taken your side. Stand close to them, then. One curse will find you all.",
    lesson="Poison is useless here. A grove makes a bunch worth its risk.",
    requires=("docks",),
)

JUNGLE = Location(
    key="jungle",
    name="The Flayer Jungle",
    act=2,
    level=Level(
        name="The Flayer Jungle", width=25, height=14,
        waypoints=((0, 2), (20, 2), (20, 7), (4, 7), (4, 11), (24, 11)),
        doors=((20, 4), (4, 9)),
        obstacles=frozenset({(8, 4), (14, 5), (2, 9), (12, 9), (18, 13), (9, 0), (23, 4), (16, 13)}),
        pools=frozenset({(11, 4), (12, 4), (22, 9), (0, 13), (1, 13)}),
    ),
    waves=_waves(
        ((g("flayer", 18, 0.5),), 50, 1.0),
        ((g("zealot", 10, 1.0), g("inquisitor", 1, start=6.0)), 60, 1.1),
        ((g("spider", 12, 0.7), g("flayer", 14, 0.5, start=3.0), g("fetish", 1, start=4.0)), 70, 1.25),
        ((g("zealot", 12, 0.9), g("inquisitor", 2, 8.0, start=3.0)), 80, 1.4),
        ((g("flayer", 26, 0.4), g("fetish", 2, 6.0, start=2.0), g("spider", 10, 0.7, start=6.0)), 90, 1.55),
        ((g("zealot", 16, 0.7), g("spider", 12, 0.6, start=3.0), g("inquisitor", 2, 7.0, start=3.0), g("fetish", 1, start=8.0)), 100, 1.7),
        ((g("zealot", 18, 0.6), g("flayer", 24, 0.4, start=2.0), g("inquisitor", 2, 6.0, start=3.0), g("fetish", 2, 7.0, start=5.0)), 0, 1.9),
    ),
    wave_names=("Green Gloom", "White and Gold", "The Hunt", "Inquisition", "Blood Sport", "The March", "No Prayer"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=460,
    theme="jungle",
    blurb="The jungle closes over two long straight roads, and the zealots of the fallen church march down them.",
    taunt="My inquisitors do not chant. You will know their curse when the ground burns under your towers, and not before.",
    lesson="The inquisitors curse without a chant: ward the marked towers, and kill them first.",
    requires=("spider_forest",),
)

DROWNED_CITY = Location(
    key="drowned_city",
    name="The Drowned City",
    act=2,
    level=Level(
        name="The Drowned City", width=25, height=14,
        waypoints=((0, 4), (9, 4), (9, 10), (17, 10), (17, 3), (24, 3)),
        doors=((9, 7), (17, 6)),
        obstacles=frozenset({(3, 1), (12, 2), (20, 12), (2, 11), (23, 8)}),
        pools=frozenset({(6, y) for y in range(14) if y != 4} | {(13, y) for y in range(14) if y != 10}
                        | {(21, y) for y in range(14) if y != 3} | {(x, 7) for x in range(25) if x not in (6, 9, 13, 17, 21)}),
    ),
    waves=_waves(
        ((g("drowned", 8, 1.4),), 50, 1.0),
        ((g("bat", 14, 0.5), g("drowned", 6, 1.3, start=4.0)), 60, 1.1),
        ((g("drowned", 10, 1.2), g("hulk", 1, start=8.0), g("inquisitor", 1, start=4.0)), 70, 1.25),
        ((g("drowned", 14, 1.0), g("witch", 1, start=4.0), g("bat", 10, 0.5, start=8.0)), 80, 1.4),
        ((g("hulk", 3, 4.0), g("drowned", 12, 0.9, start=2.0), g("inquisitor", 1, start=3.0), g("witch", 1, start=7.0)), 90, 1.55),
        ((g("drowned", 18, 0.8), g("hulk", 3, 4.0, start=4.0), g("bat", 14, 0.45, start=6.0), g("inquisitor", 2, 7.0, start=3.0)), 100, 1.75),
        ((g("hulk", 5, 3.5), g("drowned", 20, 0.7, start=2.0), g("witch", 2, 8.0, start=3.0), g("inquisitor", 1, start=6.0),
          g("bat", 26, 0.35, start=14.0)), 0, 1.95),
    ),
    wave_names=("Black Water", "Wings over the Canals", "The First Hulk", "Tide of the Dead", "Thorns", "The Flood",
                "What the Swamp Keeps"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=480,
    theme="drowned_city",
    blurb="Half of Kurast has sunk into the swamp: its streets are canals, and the Hulks walk them.",
    taunt="The Hulks were drowned men once. They do not tire, and your gates are cloth to them.",
    lesson="Frost barely slows the drowned; fire and lightning must. Gates fall fast.",
    requires=("jungle",),
)

TRAVINCAL = Location(
    key="travincal",
    name="Travincal",
    act=2,
    level=Level(
        name="Travincal", width=25, height=14,
        waypoints=((0, 1), (5, 1), (5, 12), (11, 12), (11, 1), (17, 1), (17, 12), (24, 12)),
        doors=((5, 6), (11, 7), (17, 6)),
        obstacles=frozenset({(8, 4), (8, 9), (14, 4), (14, 9), (2, 8), (21, 5), (21, 9)}),
        pools=frozenset({(8, 6), (14, 6)}),
    ),
    waves=_waves(
        ((g("zealot", 12, 0.9),), 60, 1.0),
        ((g("flayer", 18, 0.5), g("fetish", 1, start=3.0), g("inquisitor", 1, start=6.0)), 70, 1.1),
        ((g("hulk", 2, 5.0), g("zealot", 10, 0.8, start=2.0), g("priest", 1, start=4.0)), 80, 1.2),
        ((g("zealot", 14, 0.7), g("witch", 1, start=3.0), g("shaman", 1, start=5.0), g("inquisitor", 1, start=8.0)), 90, 1.35),
        ((g("bat", 20, 0.4), g("hulk", 3, 4.0, start=4.0), g("fetish", 1, start=3.0), g("priest", 1, start=7.0)), 100, 1.5),
        ((g("flayer", 26, 0.35), g("zealot", 14, 0.7, start=3.0), g("witch", 1, start=2.0), g("inquisitor", 1, start=5.0),
          g("priest", 1, start=8.0)), 110, 1.65),
        ((g("hulk", 5, 3.0), g("zealot", 16, 0.6, start=2.0), g("fetish", 1, start=2.0), g("shaman", 1, start=4.0),
          g("witch", 1, start=6.0), g("inquisitor", 1, start=8.0), g("priest", 1, start=10.0)), 120, 1.8),
        ((g("zealot", 20, 0.5), g("hulk", 4, 3.5, start=3.0), g("inquisitor", 2, 6.0, start=2.0), g("witch", 1, start=5.0),
          g("priest", 1, start=8.0), g("bat", 30, 0.3, start=14.0)), 0, 2.0),
    ),
    wave_names=("The Terrace", "The First Elders", "Iron Faith", "The Council Speaks", "Wings of the Council",
                "Every Voice", "The Council Entire", "The Last Vote"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=500,
    theme="travincal",
    blurb="The temple terrace where the High Council meets, under the mother lamp. Every elder curses.",
    taunt="Turn back, and I will leave Tristram's lamp alone. It is a small lamp. No one would miss it.",
    lesson="Curses from every side: spread wide, ward what matters, and kill the elders first.",
    requires=("drowned_city",),
)

TEMPLE = Location(
    key="temple",
    name="The Temple of Light",
    act=2,
    level=Level(
        name="The Temple of Light", width=25, height=14,
        waypoints=((0, 2), (6, 2), (6, 11), (13, 11), (13, 4), (19, 4), (19, 9), (24, 9)),
        doors=((6, 6), (13, 8), (19, 6)),
        obstacles=frozenset({(3, 5), (3, 9), (10, 2), (10, 8), (16, 1), (16, 7), (22, 2), (22, 12)}),
        pools=frozenset({(9, 5), (16, 10)}),
    ),
    waves=_waves(
        ((g("zealot", 14, 0.8),), 70, 1.0),
        ((g("drowned", 10, 1.1), g("priest", 1, start=3.0), g("inquisitor", 1, start=7.0)), 80, 1.1),
        ((g("zealot", 16, 0.7), g("drowned", 8, 1.0, start=3.0), g("bat", 14, 0.45, start=8.0)), 90, 1.25),
        ((g("zealot", 14, 0.7), g("priest", 2, 6.0, start=2.0), g("inquisitor", 1, start=5.0)), 100, 1.4),
        ((g("drowned", 16, 0.8), g("bat", 18, 0.4, start=3.0), g("inquisitor", 2, 7.0, start=3.0)), 110, 1.55),
        ((g("zealot", 20, 0.55), g("drowned", 12, 0.8, start=3.0), g("priest", 1, start=3.0), g("inquisitor", 1, start=6.0)), 120, 1.7),
        ((g("bone_priest", 1, start=6.0), g("zealot", 16, 0.6), g("priest", 1, start=2.0), g("inquisitor", 1, start=8.0),
          g("bat", 30, 0.3, start=16.0)), 0, 1.8),
    ),
    wave_names=("The Doors Open", "Acolytes", "Gold and Rot", "The Choir", "The Oil Runs Low", "The Lamp Dims",
                "The Bone Priest"),
    arsenal=Arsenal(EVERY_TOWER, gates=True, spells=ALL_SPELLS),
    start_gold=520,
    theme="temple",
    blurb="The Temple of Light, where the mother lamp hangs dim over the altar and the Bone Priest waits beneath it.",
    taunt="I cannot see you in the bones. So I have come to see you myself.",
    lesson="Each curse of his that lands burns your mana for every tower it catches: spread out, and smite his chant.",
    requires=("travincal",),
)

LOCATIONS: dict[str, Location] = {loc.key: loc for loc in (
    TRISTRAM, GRAVEYARD, CATHEDRAL, CATACOMBS, CAVES, HELLS_GATE,
    DOCKS, SPIDER_FOREST, JUNGLE, DROWNED_CITY, TRAVINCAL, TEMPLE
)}
ORDER = tuple(LOCATIONS)   # the campaign's order, which the balance tools also use for the points a player holds
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
