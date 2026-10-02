"""The adaptive defender: it reads the fight as it goes instead of following a recipe.

It keeps a picture of the path, cut into one-tile bins, learned from the monsters it watches: how long each
kind of monster spends in each bin (a queue at a gate holds it for seconds, a frost shrine slows it), how
crowded the bin is (a fireball or a leap of lightning is worth more in a crowd), and which kinds get through
to the sanctuary. A monster's trail joins the picture when it dies or leaks, so the picture shows where
monsters really get to under the towers already standing. Before the first monster it is a guess from the map
and the location's roster, as a person has it from the intro; while a wave runs, the monsters on the map and
still to come weigh in with the trails their kinds usually walk. Which kinds are still to come is what a person who
has replayed the location knows: the panel counts the monsters abroad, and each wave's host comes in the same order
every time.

From that picture every build and upgrade is priced as the damage it would deal per wave, each hit felt as the
rules feel it (:func:`~hellward.sim.content.felt_hit`: protections, vulnerabilities, armor), weighted towards the
kinds that leak and the leaders, per gold; the best is bought, or saved for. A frost shrine is also priced by
the damage its chill lets the other towers deal, a plague totem only by the venom that finds room, a knife post
by its doubled knives on the small monsters queued at a gate, a hook tower by the damage the towers standing deal
the small monsters it drags back under them, and an upgrade loses what the leaders' curses have been taking from
its tower. Gates go into arches the towers watch
and back up as soon as the arch is clear. In the last stretch, once the last wave has sent everything, only
the monsters left are priced, and the towers that will never see a monster again, all of them having walked
past, are sold to stand where the monsters are going: Azazel dies that way on Hell's Gate.

It also keeps, per kind, the damage a monster takes from anywhere on the path to the sanctuary, so it can tell
which monster is about to get through. Mana is kept for Smite while leaders walk: a chant at a tower that matters
dies with its leader when one Smite kills it, a leader Smite can finish is finished, and a monster Smite can stop is
stopped. What mana is left goes to the damage that saves most lives: Meteor on a thick crowd, a Frozen Orb on a gate
about to break (its health bar falling fast) or a clump getting through, a Smite on whatever costs many lives, a
Battle Hymn on the tower doing the most, and never a full orb wasting its flow. A break is cut short for its gold when the last wave cost nothing and the mana is in
hand.

Its skills come from a themed order of the tree (:data:`ORDERS`), cut to the sigils in hand and to what the
location offers. Which order suits a location was found by playing each on training seeds
(``tools/adaptive_skills.py``); the choice is kept in ``plans/adaptive.json``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from hellward.sim.campaign import ORDER, Location
from hellward.sim.content import (
    CURSES, MONSTERS, SPELLS, TOWERS, Curse, Element, Group, MonsterKind, TowerLevel, felt_hit,
)
from hellward.sim.model import DOOR_STOP, HOOK_PAST, HOOK_PULL, JOSTLE, KNIFE_STANDING, Monster, Refused, Tower, World
from hellward.sim.players.hands import AIM_GAP, Hands, REACT, ready
from hellward.sim.players.spacing import max_curse_radius, score_with_spacing
from hellward.sim.skills import PHYSICAL, SKILLS, can_learn

SAMPLE = 0.25          # seconds between two looks at where the monsters are
THINK = 0.25           # seconds between two decisions about gold
REFRESH = 4.0          # seconds between two re-readings of the picture while a wave runs
GUESS = 3.0            # monsters of each kind the first guess is worth against what is seen
NOW = 2.0              # what a monster of this wave, on the map or still to come, weighs against one seen before
FADE = 0.75            # what an older wave's monsters still weigh when a new wave starts
QUEUE_GUESS = 4.0      # seconds a monster is reckoned to wait at a standing gate, before any is seen
URGENCY = 1.2          # how much more a bin by the sanctuary is worth than one at the portal (found on training seeds)
LEAKY = 4.0            # how much more damage to a kind is worth when all of it leaks
LEADER = 1.5           # how much more damage to a leader is worth
SPLASH_HIT = 0.6       # a fireball's share on the monsters around its target (the rules' number)
VENOM_ROOM = 1.0       # venom darts a second one monster can take: four stacks that last four seconds
VENOM_TRUST = 0.6      # how far the estimate of a plague totem is trusted, and a frost nova's: both found by
NOVA_TRUST = 1.45      # playing training seeds, where totems proved worth less and novas more than estimated
SETTLE = 0.8           # an affordable buy this close to the best is taken instead of saving for the best
CALL_MANA = 0.92       # share of a full orb an early call needs in hand
ELEMENTS = tuple(Element)
SEVERITY = {Curse.WEAKEN: 1.0 - CURSES[Curse.WEAKEN].damage, Curse.DECREPIFY: 1.0 - CURSES[Curse.DECREPIFY].rate,
            Curse.DIM_VISION: 0.5, Curse.BONE_PRISON: 1.0}
SMITE_SHARE = 0.04     # a chant at a tower doing this share of the damage is worth a Smite that kills its leader
HYMN_SHARE = 0.08      # a tower doing this share of the damage, with monsters in reach, is worth a Battle Hymn
HOOK_TRUST = 1.0       # how far the estimate of a hook's pulls is trusted
PASSED = 0.5           # a monster presses once it has walked past this share of the towers' fire, and would survive
CALM = 0.25            # damage to a monster the towers will kill anyway, against one that would get through
HOLD = 2.0             # a Frozen Orb's worth over its damage: the frozen stay under the towers, a gate stops breaking
METEOR_WORTH = 3.0     # a Meteor falls unpressed where it would take at least this many times its damage off the pack
ORB_CROWD = 4          # monsters at a gate about to break that are worth a Frozen Orb

PLANS = Path(__file__).parent / "plans" / "adaptive.json"
ORDERS: dict[str, tuple[str, ...]] = {
    "mixed": ("adept_fire", "adept_cold", "holy_shield", "warmth", "fire_ball", "glacial_spike",
              "adept_lightning", "chain_lightning", "adept_poison", "contagion",
              "soul_harvest", "master_fire", "master_cold", "master_lightning", "master_poison",
              "thorns", "blaze", "shatter", "static_field", "lower_resist", "spell_mastery",
              "adept_bone", "corpse_explosion", "master_bone", "life_tap",
              "adept_nature", "hurricane", "master_nature", "twister"),
    "warden": ("holy_shield", "warmth", "adept_cold", "adept_fire", "adept_poison",
               "adept_lightning", "fire_ball", "glacial_spike", "chain_lightning", "contagion",
               "thorns", "soul_harvest", "master_fire", "master_cold", "master_lightning", "master_poison",
               "adept_bone", "corpse_explosion", "master_bone", "life_tap",
               "adept_nature", "hurricane", "master_nature", "twister"),
    "sorcerer": ("warmth", "soul_harvest", "spell_mastery", "holy_shield", "adept_cold", "adept_fire",
                 "adept_poison", "adept_lightning", "fire_ball", "glacial_spike", "chain_lightning",
                 "contagion", "master_fire", "master_cold", "master_lightning", "master_poison",
                 "adept_bone", "corpse_explosion", "master_bone", "life_tap",
                 "adept_nature", "hurricane", "master_nature", "twister"),
    "frost": ("adept_cold", "glacial_spike", "holy_shield", "warmth", "master_cold", "shatter",
              "adept_fire", "adept_poison", "fire_ball", "contagion", "master_fire", "master_poison",
              "adept_bone", "corpse_explosion", "master_bone", "life_tap",
              "adept_nature", "hurricane", "master_nature", "twister"),
    "fire": ("adept_fire", "fire_ball", "holy_shield", "warmth", "adept_cold", "master_fire", "blaze",
             "glacial_spike", "master_cold",
             "adept_bone", "corpse_explosion", "master_bone", "life_tap",
             "adept_nature", "hurricane", "master_nature", "twister"),
    "storm": ("adept_lightning", "chain_lightning", "holy_shield", "warmth", "adept_cold", "master_lightning",
              "static_field", "glacial_spike", "master_cold",
              "adept_bone", "corpse_explosion", "master_bone", "life_tap",
              "adept_nature", "hurricane", "master_nature", "twister"),
    "venom": ("adept_poison", "holy_shield", "contagion", "warmth", "adept_cold", "master_poison",
              "lower_resist", "glacial_spike", "master_cold",
              "adept_bone", "corpse_explosion", "master_bone", "life_tap",
              "adept_nature", "hurricane", "master_nature", "twister"),
}
DEFAULT_ORDER = "mixed"
TOWER_OF = {"fire": "pyre", "lightning": "storm", "cold": "frost", "poison": "plague",
            "bone": "altar", "nature": "grove"}


def useful(location: Location, key: str) -> bool:
    """Whether a skill does anything here: its tower is offered, its gates, its spells, its leaders."""
    skill = SKILLS[key]
    arsenal = location.arsenal
    leaders = any(MONSTERS[k].leader is not None for k in location.monsters)
    if skill.column in TOWER_OF:
        return TOWER_OF[skill.column] in arsenal.towers
    if skill.column == "arrow":
        return any(kind in arsenal.towers for kind in PHYSICAL)
    if key in ("holy_shield", "thorns"):
        return arsenal.gates
    if key == "soul_harvest":
        return leaders
    if key == "spell_mastery":
        return any(s in arsenal.spells for s in ("smite", "meteor", "orb"))
    return len(arsenal.spells) > 1 or leaders


def learn(location: Location, sigils: int, order: tuple[str, ...]) -> frozenset[str]:
    """The skills an order buys with these sigils: its own useful ones first, then the rest of the tree, going
    through the list again while something new has become learnable."""
    every = [*order, *(k for k in SKILLS if k not in order)]
    every.sort(key=lambda k: not useful(location, k))   # a stable sort: the useful first, each in its order
    learned: frozenset[str] = frozenset()
    stage = ORDER.index(location.key)
    while True:
        before = learned
        for key in every:
            if can_learn(learned, key, sigils, stage):
                learned |= {key}
        if learned == before:
            return learned


@dataclass
class Trail:
    """Where one monster has been: per bin, seconds spent (discounted as it weakens) and the crowd around it."""

    kind: MonsterKind
    seconds: dict[int, float] = field(default_factory=dict)
    near: dict[int, float] = field(default_factory=dict)    # seconds × monsters within a bin
    around: dict[int, float] = field(default_factory=dict)  # seconds × monsters within three bins
    remaining: float = 0.0


class Picture:
    """What the monsters did on this path, summed over every monster watched and faded wave by wave: per kind and
    bin, the seconds spent there; per bin, the crowd; per kind, how many came and how many got through."""

    def __init__(self, bins: int) -> None:
        self.bins = bins
        self.seconds: dict[str, list[float]] = {}
        self.near = [0.0] * bins
        self.around = [0.0] * bins
        self.came: dict[str, float] = {}
        self.leaked: dict[str, float] = {}

    def fold(self, trail: Trail, leaked: bool) -> None:
        key = trail.kind.key
        seconds = self.seconds.setdefault(key, [0.0] * self.bins)
        for b, t in trail.seconds.items():
            seconds[b] += t
            self.near[b] += trail.near[b]
            self.around[b] += trail.around[b]
        self.came[key] = self.came.get(key, 0.0) + 1.0
        self.leaked[key] = self.leaked.get(key, 0.0) + (1.0 if leaked else 0.0)

    def fade(self, share: float) -> None:
        for values in (*self.seconds.values(), self.near, self.around):
            for b in range(self.bins):
                values[b] *= share
        for counts in (self.came, self.leaked):
            for key in counts:
                counts[key] *= share


@dataclass
class View:
    """The picture blended with the guess and this wave, per bin: what the prices are read from. ``worth[e]`` is
    the seconds monsters spend in a bin times what a point of that element's damage is worth on them; ``venom`` the
    same for the strongest monster a plague totem can poison there."""

    seconds: list[float]
    near: list[float]      # monsters within a bin of a monster here
    around: list[float]    # monsters within three bins
    worth: dict[Element, list[float]]
    venom: list[float]
    poisonable: list[float]
    room: list[float]      # venom darts a second the poisonable monsters here can take before stacks are wasted
    here: dict[str, list[float]]   # per monster kind: its seconds here times what damage to it is worth
    small: list[float]     # seconds small monsters spend here
    pace: list[float]      # seconds a small monster here takes to walk a tile


class Adaptive:
    name = "adaptive"
    reaction: tuple[float, float] = REACT
    aim_gap: float = AIM_GAP

    def __init__(self, order: str = "") -> None:
        self.order = order                    # a themed order of the skill tree; empty takes the plan's
        self.study: Study | None = None
        self.picture: Picture | None = None
        self.view: View | None = None
        self.trails: dict[int, Trail] = {}
        self.sample_at = 0.0
        self.think_at = 0.0
        self.refresh_at = 0.0
        self.wave = -1
        self.lives_at_wave = 0
        self.lost_last = 0
        self.prices: dict[tuple, float] = {}
        self.cheapest = 0
        self.tower_worth: dict[int, float] = {}
        self.density: dict[tuple[str, int], list[float]] = {}
        self.felt: dict[tuple[str, float, str, float], int] = {}   # a hit as a monster kind feels it (_felt)
        self.firepower: list[float] = []      # per bin: worth of the damage the towers standing deal there
        self.chilled: list[float] = []        # per bin: the deepest chill a frost shrine lays there
        self.darts: list[float] = []          # per bin: venom darts a second from the totems standing
        self.ahead: dict[str, list[float]] = {}
        self.cursed: dict[int, float] = {}    # per tower: seconds cursed, weighted by how badly, while monsters walked
        self.watched: dict[int, float] = {}   # per tower: seconds it stood while monsters walked
        self.aimed_at = -1e9
        self.endgame = False                  # the last wave has sent every monster it has
        self.host: list[tuple[str, str]] = []  # this wave's kinds and authored entrances, in spawn order
        self.gate_hp: dict[int, float] = {}   # per gate: its life at the last look
        self.battered: dict[int, float] = {}  # per gate: life it lost a second since the look before

    # -- Skills --------------------------------------------------------------------------------------

    def skills(self, location: Location, sigils: int) -> frozenset[str]:
        order = self.order
        if not order:
            plans = json.loads(PLANS.read_text()) if PLANS.exists() else {}
            order = plans.get(location.key, DEFAULT_ORDER)
        return learn(location, sigils, ORDERS[order])

    # -- Every step ----------------------------------------------------------------------------------

    def act(self, hands: Hands) -> None:
        world = hands.world
        if self.study is None or self.study.side_included != bool(_announced_breach_groups(world)):
            self.study = Study(world)
            self.view = None
            if self.picture is None:
                self.picture = Picture(self.study.bins)
                self.lives_at_wave = world.lives
        if world.time >= self.sample_at - 1e-9:
            self.sample_at = world.time + SAMPLE
            self._watch(world)
        if world.wave != self.wave:
            self._new_wave(world)
        if not self.endgame and world.wave == len(world.location.waves) - 1 and not self._to_come(world):
            self.endgame = True
            self.view = None
        if self.view is None or world.time >= self.refresh_at:
            self.refresh_at = world.time + REFRESH
            self._reread(world)
        self._spells(hands)
        self._gates(world)
        if world.time >= self.think_at - 1e-9:
            self.think_at = world.time + THINK
            self._salvage(world)
            self._spend(world)
            self._call(world)

    # -- Watching ------------------------------------------------------------------------------------

    def _watch(self, world: World) -> None:
        """Note where every monster stands and how crowded it is there, and which towers carry curses; fold the
        trails of the monsters gone."""
        assert self.study is not None and self.picture is not None
        study = self.study
        counts = [0] * study.bins
        for m in world.monsters:
            counts[study.bin(m.s, m.route)] += 1
        prefix = [0]
        for c in counts:
            prefix.append(prefix[-1] + c)
        alive = set()
        for m in world.monsters:
            alive.add(m.id)
            trail = self.trails.get(m.id)
            if trail is None:
                trail = self.trails[m.id] = Trail(m.kind)
            b = study.bin(m.s, m.route)
            weight = SAMPLE * (0.3 + 0.7 * m.hp / m.max_hp)
            start, end = study.bounds(m.route)
            near = prefix[min(end, b + 2)] - prefix[max(start, b - 1)]
            around = prefix[min(end, b + 4)] - prefix[max(start, b - 3)]
            trail.seconds[b] = trail.seconds.get(b, 0.0) + weight
            trail.near[b] = trail.near.get(b, 0.0) + weight * near
            trail.around[b] = trail.around.get(b, 0.0) + weight * around
            trail.remaining = world.remaining(m)
        if world.monsters:
            for t in world.towers.values():
                self.watched[t.id] = self.watched.get(t.id, 0.0) + SAMPLE
                if t.curses:
                    self.cursed[t.id] = self.cursed.get(t.id, 0.0) + SAMPLE * max(SEVERITY[c] for c in t.curses)
        for key in [k for k in self.trails if k not in alive]:
            trail = self.trails.pop(key)
            self.picture.fold(trail, leaked=trail.remaining <= trail.kind.speed * SAMPLE * 2)
        for d in world.doors:
            self.battered[d.index] = max(0.0, self.gate_hp.get(d.index, d.hp) - d.hp) / SAMPLE
            self.gate_hp[d.index] = d.hp

    def _new_wave(self, world: World) -> None:
        assert self.picture is not None
        self.lost_last = self.lives_at_wave - world.lives
        self.lives_at_wave = world.lives
        self.wave = world.wave
        self.picture.fade(FADE)
        self.view = None
        groups = world.location.waves[world.wave].groups
        spec = world.breach_spec
        if spec is not None and world.breach_opened and world.wave == spec.after_wave + 1:
            groups = (*groups, *spec.groups)
        self.host = [(kind, route) for _, kind, route in sorted(
            (group.start + i * group.interval, group.kind, group.route)
            for group in groups for i in range(group.count))]

    def _to_come(self, world: World) -> list[tuple[str, str]]:
        """The kinds this wave has still to send: the last of its host, as many as the panel's count of monsters
        abroad has beyond those on the map."""
        left = len(world.schedule)   # what the panel adds to the monsters on the map
        return self.host[len(self.host) - left:] if left else []

    def _reread(self, world: World) -> None:
        """Blend the picture with the guess from the map and the roster, and with the monsters of this wave (on the
        map and still to come, each walking the rest of its kind's usual trail); then price everything anew."""
        assert self.study is not None and self.picture is not None
        study, picture = self.study, self.picture
        bins = study.bins
        coming: dict[str, list[float]] = {}
        for m in world.monsters:
            coming.setdefault(m.kind.key, [0.0] * bins)[study.bin(m.s, m.route)] += 1.0
        for key, route in self._to_come(world):
            choices = study.spawn_routes(key, route)
            for choice in choices:
                coming.setdefault(key, [0.0] * bins)[study.bin(0.0, choice)] += 1.0 / len(choices)
        seconds = [0.0] * bins
        worth = {e: [0.0] * bins for e in ELEMENTS}
        venom = [0.0] * bins
        pull = [0.0] * bins          # seconds × life³ of poisonable monsters: who a totem aims at
        poisonable = [0.0] * bins
        valued: dict[str, list[float]] = {}
        small = [0.0] * bins
        tiles = [0.0] * bins         # tiles small monsters walk here: with ``small``, their pace
        for key in study.roster:
            kind: MonsterKind = MONSTERS[key]
            came = picture.came.get(key, 0.0)
            seen = picture.seconds.get(key)
            usual = [t / came for t in seen] if seen is not None and came >= 1.0 else study.guess[key]
            past = 0.0 if self.endgame else 1.0   # in the last stretch only the monsters left matter
            here = [past * study.guess[key][b] * GUESS for b in range(bins)]
            if seen is not None:
                here = [h + past * t for h, t in zip(here, seen)]
            starts = coming.get(key)
            if starts is not None:
                for route in study.routes:
                    walking = 0.0
                    start, end = study.bounds(route.key)
                    share = study.route_share[key][route.key]
                    for b in range(start, end):
                        walking += starts[b]
                        if walking > 0:
                            here[b] += NOW * walking * usual[b] / share
            leaked = picture.leaked.get(key, 0.0) / came if came > 0 else 0.0
            value = (1.0 + LEAKY * leaked) * (LEADER if kind.leader is not None else 1.0)
            size = kind.hp ** 3
            poison = _taken(kind, Element.POISON)
            valued[key] = [t * value for t in here]
            for b in range(bins):
                t = here[b]
                if t <= 0:
                    continue
                seconds[b] += t
                if kind.small:
                    small[b] += t
                    tiles[b] += t * kind.speed
                for e in ELEMENTS:
                    worth[e][b] += t * value * _taken(kind, e)
                if poison > 0:
                    venom[b] += t * size * value * poison
                    pull[b] += t * size
                    poisonable[b] += t
        near = [1.0] * bins
        around = [1.0] * bins
        for b in range(bins):
            guessed = study.guess_seconds[b] * GUESS
            total = guessed + sum(picture.seconds[k][b] for k in picture.seconds)
            if total > 0:
                near[b] = max(1.0, (study.guess_near[b] * guessed + picture.near[b]) / total)
                around[b] = max(1.0, (study.guess_around[b] * guessed + picture.around[b]) / total)
            if pull[b] > 0:
                venom[b] = venom[b] / pull[b] * poisonable[b]
        room = [VENOM_ROOM * min(2.0, max(1.0, around[b] * poisonable[b] / seconds[b])) if seconds[b] > 0 else 0.0
                for b in range(bins)]
        pace = [small[b] / tiles[b] if tiles[b] > 0 else 0.0 for b in range(bins)]
        self.view = View(seconds, near, around, worth, venom, poisonable, room, valued, small, pace)
        self.density = {}
        for tower_kind in world.location.arsenal.towers:
            for level, stats in enumerate(world.tower_levels[tower_kind]):
                self.density[(tower_kind, level)] = [self._urgency(b) * self._density(world, tower_kind, stats, b) if seconds[b] > 0
                                                else 0.0 for b in range(bins)]
        self._price(world)

    # -- Prices --------------------------------------------------------------------------------------

    def _urgency(self, b: int) -> float:
        assert self.study is not None
        start, end = self.study.bin_bounds[b]
        return 1.0 + (URGENCY + 0.1 * self.lost_last) * (b - start) / (end - start)

    def _density(self, world: World, kind: str, stats: TowerLevel, b: int) -> float:
        """Worth of the damage a tower of this kind and rank deals per wave from one bin of path it reaches: its hits
        a second, each as the monsters here feel it, weighted by their seconds here and what hurting them is worth."""
        assert self.view is not None and self.study is not None
        view = self.view
        tower = TOWERS[kind]
        attack = tower.attack
        around = view.around[b]
        if attack == "venom":
            stacks = min(4.0, stats.poison_time * stats.rate)
            crowd = max(1.0, around * view.poisonable[b] / view.seconds[b])
            return VENOM_TRUST * (stats.damage * stats.rate + stats.poison * stacks) * view.venom[b] / crowd
        standing = kind == "knife" and b in self.study.queues   # a knife on a small monster queued at a gate
        felt = 0.0
        for key, valued in view.here.items():
            monster = MONSTERS[key]
            if valued[b] <= 0 or (attack == "hook" and not monster.small):   # a hook hits only what it hooks
                continue
            factor = KNIFE_STANDING if standing and monster.small else 1.0
            felt += valued[b] * self._felt(kind, stats, monster, factor)
        hits = stats.rate * felt
        if attack == "nova":
            return NOVA_TRUST * hits
        busy = hits / around
        if attack == "chain":
            reached = min(1.0 + stats.chains, around)
            keeps = world.perks.leap_keeps
            return busy * sum(keeps ** i * min(1.0, reached - i) for i in range(math.ceil(reached)))
        if stats.splash > 0:
            return busy * (1.0 + SPLASH_HIT * min(3.0, (view.near[b] - 1.0) * min(1.0, stats.splash / 1.2)))
        return busy

    def _felt(self, kind: str, stats: TowerLevel, monster: MonsterKind, factor: float) -> int:
        """A hit of this tower kind and rank as a monster of this kind feels it, kept once worked out."""
        key = (kind, stats.damage, monster.key, factor)
        found = self.felt.get(key)
        if found is None:
            found = self.felt[key] = felt_hit(stats.damage, TOWERS[kind].element, monster, factor)
        return found

    def worth(self, kind: str, level: int, stats: TowerLevel, tile: tuple[int, int], chilled: list[float],
              darts: list[float]) -> float:
        """Worth of the damage per wave a tower of this kind and rank would deal on this tile, from the picture;
        a frost shrine adds what its chill lets the others deal where nothing chills yet, and a plague totem counts
        only the venom that finds room: four stacks on a monster at most, and every totem aims at the strongest."""
        assert self.study is not None
        density = self.density[(kind, level)]
        value = 0.0
        cover = self.study.cover(tile, stats.range)
        if stats.chill > 0:
            gain = _slowed(stats.chill)
            for b, share in cover:
                value += share * (density[b] + max(0.0, gain - _slowed(chilled[b])) * self.firepower[b])
            return value
        if stats.poison > 0:
            assert self.view is not None
            room = self.view.room
            for b, share in cover:
                value += share * density[b] * min(1.0, max(0.1, (room[b] - darts[b]) / stats.rate))
            return value
        if TOWERS[kind].attack == "hook":
            return value + self._pulls(stats, tile, cover, density)
        for b, share in cover:
            value += share * density[b]
        return value

    def _pulls(self, stats: TowerLevel, tile: tuple[int, int], cover: tuple[tuple[int, float], ...],
               density: list[float]) -> float:
        """A hook's worth on a tile: its own hits, and its pulls. Past its spot (each route's point nearest it), it
        hooks a small monster about as often as one is there to hook; each pull walks that monster HOOK_PULL tiles
        more under the towers there, which deal it what they deal a monster there in that time."""
        assert self.study is not None and self.view is not None
        study, view = self.study, self.view
        value = 0.0
        for b, share in cover:
            start, _ = study.bin_bounds[b]
            if b - start < study.level.nearest(study.bin_route[b], tile) + HOOK_PAST - 0.5:
                continue   # before its spot: nothing there is hooked
            value += share * density[b]
            if view.seconds[b] > 0:
                pulls = stats.rate * view.small[b] / view.around[b]
                value += HOOK_TRUST * share * pulls * HOOK_PULL * view.pace[b] * self.firepower[b] / view.seconds[b]
        return value

    def _price(self, world: World) -> None:
        """Price every tower that could stand and every upgrade: worth per gold."""
        assert self.study is not None
        study = self.study
        bins = study.bins
        self.firepower = [0.0] * bins
        self.chilled = [0.0] * bins
        self.darts = [0.0] * bins
        frosts = [t for t in world.towers.values() if t.stats.chill > 0]
        for t in world.towers.values():
            if t.stats.poison > 0:
                for b, _ in study.cover(t.tile, t.stats.range):
                    self.darts[b] += t.stats.rate
            if t.stats.chill > 0:
                for b, _ in study.cover(t.tile, t.stats.range):
                    self.chilled[b] = max(self.chilled[b], t.stats.chill)
            else:
                density = self.density[(t.kind.key, t.level)]
                for b, share in study.cover(t.tile, t.stats.range):
                    self.firepower[b] += share * density[b]
        self._ahead(world)
        self.tower_worth = {}
        prices: dict[tuple, float] = {}
        for t in world.towers.values():
            chilled = self._chilled_but(t, frosts) if t.stats.chill > 0 else self.chilled
            darts = self.darts
            if t.stats.poison > 0:
                own = {b for b, _ in study.cover(t.tile, t.stats.range)}
                darts = [d - t.stats.rate if b in own else d for b, d in enumerate(self.darts)]
            self.tower_worth[t.id] = self.worth(t.kind.key, t.level, t.stats, t.tile, chilled, darts)
            cost = world.upgrade_cost(t)
            if cost is not None and world.rank_needs(t) is None:
                better = self.worth(t.kind.key, t.level + 1, t.levels[t.level + 1], t.tile, chilled, darts)
                prices[("upgrade", t.id)] = (better - self.tower_worth[t.id]) * (1.0 - self._curse_share(t)) / cost
        standing = {t.tile for t in world.towers.values()}
        existing_tiles = list(standing)
        radius = max_curse_radius(world.location)
        for kind in world.location.arsenal.towers:
            stats = world.tower_levels[kind][0]
            for tile in study.tiles:
                if tile not in standing:
                    worth = self.worth(kind, 0, stats, tile, self.chilled, self.darts)
                    if radius > 0:
                        worth = score_with_spacing(worth, existing_tiles, tile, world.location)
                    prices[("build", kind, tile)] = worth / stats.cost
        self.prices = prices
        cheapest = min((self._cost(world, k) for k in prices), default=0)
        self.cheapest = cheapest if cheapest is not None else 0

    def _chilled_but(self, tower: Tower, frosts: list[Tower]) -> list[float]:
        assert self.study is not None
        chilled = [0.0] * self.study.bins
        for t in frosts:
            if t is not tower:
                for b, _ in self.study.cover(t.tile, t.stats.range):
                    chilled[b] = max(chilled[b], t.stats.chill)
        return chilled

    def _curse_share(self, tower: Tower) -> float:
        """How much of its work the leaders' curses have taken from this tower so far."""
        watched = self.watched.get(tower.id, 0.0)
        return min(0.8, self.cursed.get(tower.id, 0.0) / watched) if watched > 10.0 else 0.0

    # -- Who gets through ----------------------------------------------------------------------------

    def _ahead(self, world: World) -> None:
        """Per kind and bin, the damage a monster of that kind takes from there to the sanctuary under the towers
        standing, sharing their fire with its usual crowd: what a person weighs when asking whether it gets through."""
        study, view = self.study, self.view
        assert study is not None and view is not None
        bins = study.bins
        gates = [d for d in world.doors if d.built]
        self.ahead = {}
        for key in study.roster:
            kind = MONSTERS[key]
            hurt = [0.0] * bins   # what the towers deal a monster of this kind a second, as it feels their hits
            for t in world.towers.values():
                stats = t.stats
                if t.kind.attack in ("aura", "amplify"):
                    continue
                dps = self._felt(t.kind.key, stats, kind, 1.0) * stats.rate
                if t.kind.attack == "venom":
                    dps += stats.poison * min(4.0, stats.poison_time * stats.rate) * kind.taken(Element.POISON)
                for b, share in study.cover(t.tile, stats.range):
                    hurt[b] += share * dps
            dwell = [1.0 / kind.speed] * bins
            if not kind.flying:
                for d in gates:
                    for queue_bin in study.queue_bins[d.index]:
                        dwell[queue_bin] += QUEUE_GUESS
            ahead = [0.0] * bins
            for route in study.routes:
                total = 0.0
                start, end = study.bounds(route.key)
                for b in range(end - 1, start - 1, -1):
                    total += dwell[b] * hurt[b] / view.around[b] ** 0.5
                    ahead[b] = total
            self.ahead[key] = ahead

    def threat(self, m: Monster) -> float:
        """Life a monster is likely to carry into the sanctuary; zero or less if the towers ahead should kill it."""
        assert self.study is not None
        return m.hp - self.ahead[m.kind.key][self.study.bin(m.s, m.route)]

    def pressing(self, m: Monster) -> bool:
        """A monster that would get through and has already walked past most of the towers' fire (a person trusts
        the towers with a monster at the portal), or one that costs many lives."""
        assert self.study is not None
        ahead = self.ahead[m.kind.key]
        passed = ahead[self.study.bin(m.s, m.route)] <= PASSED * ahead[self.study.bin(0.0, m.route)]
        return self.threat(m) > 0 and (passed or m.kind.boss)

    # -- Gold ----------------------------------------------------------------------------------------

    def _spend(self, world: World) -> None:
        """Buy the best-priced build or upgrade; when it is out of reach, one nearly as good that is not, else save."""
        while self.prices:
            spare = world.gold - self._keep(world)
            if spare < self.cheapest:
                return
            prices = self.prices
            top = max(prices, key=lambda k: prices[k])
            best = prices[top]
            if best <= 0:
                return
            choice = top if self._cost(world, top) <= spare else None
            if choice is None:
                near = [k for k, v in prices.items() if v >= best * SETTLE and self._cost(world, k) <= spare]
                if not near:
                    return
                choice = max(near, key=lambda k: prices[k])
            if choice[0] == "build":
                world.build(choice[1], choice[2])
            else:
                world.upgrade(choice[1])
            self._price(world)

    def _salvage(self, world: World) -> None:
        """In the last wave, once every monster has come, sell the towers all of them have walked past: those will
        never fire again, and their gold can still stand where the monsters are going."""
        if not self.endgame or not world.monsters:
            return
        assert self.study is not None
        behind = [t for t in world.towers.values() if not t.curses and all(
            all(b + 1 < m.s for _, b in world.level.route(m.route).coverage(t.tile, t.stats.range))
            for m in world.monsters)]
        for t in behind:
            world.sell(t.id)
        if behind:
            self._price(world)

    def _cost(self, world: World, choice: tuple) -> int:
        if choice[0] == "build":
            return world.cost(choice[1])
        cost = world.upgrade_cost(world.towers[choice[1]])
        return cost if cost is not None else 0

    def _keep(self, world: World) -> int:
        """Gold held back for a gate that is down or failing, where towers watch its queue."""
        for d in world.doors:
            if self._guarded(d.index) and (not d.built or d.hp < world.gate_life * 0.35):
                return world.door_cost
        return 0

    def _guarded(self, index: int) -> bool:
        assert self.study is not None
        return bool(self.firepower) and any(self.firepower[b] > 0 for b in self.study.queue_bins[index])

    def _gates(self, world: World) -> None:
        if not world.location.arsenal.gates or world.gold < world.door_cost:
            return
        for d in world.doors:
            if not d.built and not d.rubble and self._guarded(d.index) and world.gold >= world.door_cost:
                try:
                    world.build_door(d.index)
                except Refused:   # monsters stand in the arch: it goes up once they have passed
                    continue

    def _call(self, world: World) -> None:
        """Cut a break short for its gold when the last wave cost nothing and the mana is in hand."""
        if not world.can_call_wave or world.break_left is None or world.wave < 0 or world.monsters:
            return
        if world.lives == self.lives_at_wave and world.mana >= world.mana_max * CALL_MANA:
            world.call_wave()

    # -- Spells --------------------------------------------------------------------------------------

    def _spells(self, hands: Hands) -> None:
        world = hands.world
        if world.monsters:
            self._hymn(hands)
        if world.time - self.aimed_at < self.aim_gap - 1e-9 or not world.monsters:
            return
        if self._answer(hands) or self._strike(hands):
            self.aimed_at = world.time

    def _reserve(self, world: World) -> float:
        """Mana kept for Smite while a leader walks or is still to come in this wave."""
        if "smite" not in world.location.arsenal.spells:
            return 0.0
        coming = any(MONSTERS[key].leader is not None for key, _ in self._to_come(world))
        walking = any(m.kind.leader is not None for m in world.monsters)
        return world.spell_cost("smite") if coming or walking else 0.0

    def _share(self, tower_id: int) -> float:
        total = sum(self.tower_worth.values()) or 1.0
        return self.tower_worth.get(tower_id, 0.0) / total

    def _can(self, world: World, spell: str) -> bool:
        return ready(world, spell)

    def _answer(self, hands: Hands) -> bool:
        """The leaders first: a Smite that kills a leader chanting at a tower that matters (its curse dies with it),
        a Smite that finishes a leader, and a Smite that stops a monster getting through."""
        world = hands.world
        if not self._can(world, "smite"):
            return False
        full = world.mana >= world.mana_max - 5
        blow = SPELLS["smite"].damage * world.power()
        for sign in hands.threats():
            m = world.monster(sign.leader)
            if sign.kind != "chant" or m is None or sign.curse is None or m.hp > felt_hit(blow, None, m.kind):
                continue
            share = sum(self._share(t.id) for t in world.caught(sign.spot, sign.radius))
            if share * SEVERITY[sign.curse] >= SMITE_SHARE or full:
                hands.smite(m.id)
                return True
        for m in world.leaders():
            if m.hp <= felt_hit(blow, None, m.kind):
                hands.smite(m.id)
                return True
        assert self.study is not None
        rescue = [m for m in world.monsters if 0 < self.threat(m) <= felt_hit(blow, None, m.kind)
                  and world.remaining(m) < world.level.route(m.route).length * 0.5]
        if rescue:
            hands.smite(max(rescue, key=lambda m: (m.kind.lives, -world.remaining(m))).id)
            return True
        return False

    def _strike(self, hands: Hands) -> bool:
        """Mana beyond what the leaders need buys damage where it saves most: on monsters that would get through,
        above all. Smite, Meteor and Frozen Orb are weighed by that damage per mana, and the best is cast while
        someone presses, or on a crowd worth it, or when the orb is full."""
        world = hands.world
        full = world.mana >= world.mana_max - 5
        spare = world.mana - self._reserve(world)
        danger = {m.id: self.pressing(m) for m in world.monsters}
        pressed = any(danger.values())
        power = world.power()

        def weight(m: Monster) -> float:
            return m.kind.lives * (1.0 if danger[m.id] else CALM) * (LEADER if m.kind.leader is not None else 1.0)

        options: list[tuple[float, str, int | tuple[float, float]]] = []
        if self._can(world, "smite") and (spare >= world.spell_cost("smite") or full):
            blow = SPELLS["smite"].damage * power
            m = max(world.monsters, key=lambda m: (min(blow, m.hp) * weight(m), -world.remaining(m)))
            options.append((min(blow, m.hp) * weight(m) / world.spell_cost("smite"), "smite", m.id))
        if self._can(world, "meteor") and (spare >= world.spell_cost("meteor") or full):
            spec = SPELLS["meteor"]
            blow = (spec.damage + spec.burn * spec.lasting * 0.5) * power
            at, got, crowd = self._crowd(world, spec.radius * 0.85, spec.delay, blow, Element.FIRE, weight)
            if at is not None and (pressed or full or crowd >= METEOR_WORTH * blow):
                options.append((got / world.spell_cost("meteor"), "meteor", at))
        if self._can(world, "orb") and (spare >= world.spell_cost("orb") or full):
            spec = SPELLS["orb"]
            at, got, _ = self._crowd(world, spec.radius * 0.9, 0.0, spec.damage * power, Element.COLD, weight)
            if at is not None and self.firepower[self.study.nearest_bin(at)] <= 0:
                at = None   # frozen where no tower fires, a monster only waits
            gate = self._failing_gate(world)
            if gate is not None:
                options.append((HOLD * max(got, 1.0) / world.spell_cost("orb"), "orb", gate))
            elif at is not None and pressed:
                options.append((HOLD * got / world.spell_cost("orb"), "orb", at))
        if not options or not (pressed or full or any(o[1] == "meteor" for o in options)):
            return False
        _, spell, target = max(options, key=lambda o: o[0])
        if spell == "smite":
            if not (pressed or full):
                return False
            assert isinstance(target, int)
            hands.smite(target)
        elif spell == "meteor":
            assert isinstance(target, tuple)
            hands.meteor(*target)
        else:
            assert isinstance(target, tuple)
            hands.orb(*target)
        return True

    def _crowd(self, world: World, radius: float, delay: float, blow: float, element: Element, weight) -> tuple:
        """Where a spell falling ``delay`` from now does the most weighted damage: (where, weighted damage, damage)."""
        ahead = [(m, world.level.route(m.route).point(_landing(world, m, delay))) for m in world.monsters]
        best, best_raw, best_at = 0.0, 0.0, None
        for _, at in ahead:
            got = raw = 0.0
            for m, where in ahead:
                if _dist(where, at) <= radius:
                    hurt = min(m.hp, felt_hit(blow, element, m.kind))
                    raw += hurt
                    got += hurt * weight(m)
            if got > best:
                best, best_raw, best_at = got, raw, at
        return best_at, best, best_raw

    def _failing_gate(self, world: World) -> tuple[float, float] | None:
        """The queue at a gate whose health bar, falling as fast as it did since the last look, empties within two
        seconds, when enough monsters batter it."""
        for d in world.doors:
            if not d.built or d.hp >= self.battered[d.index] * 2.0:
                continue
            batterers = [m for m in world.monsters if m.door == d.index]
            if len(batterers) >= ORB_CROWD:
                return world.position(batterers[0])
        return None

    def _hymn(self, hands: Hands) -> None:
        """Battle Hymn on the tower doing the most, while monsters are in its reach and the leaders' Smite stays in
        hand; any tower with work when the orb is full."""
        world = hands.world
        if not self._can(world, "hymn") or world.mana - self._reserve(world) < world.spell_cost("hymn"):
            return
        best, best_share = None, 0.0
        for t in world.towers.values():
            share = self._share(t.id)
            if share > best_share and not t.silenced and any(world.in_reach(t, m.s, m.route) for m in world.monsters):
                best, best_share = t, share
        if best is not None and (best_share >= HYMN_SHARE or world.mana >= world.mana_max - 5):
            hands.hymn(best.id)


def _taken(kind: MonsterKind, element: Element) -> float:
    return max(0.0, kind.taken(element))


def _slowed(chill: float) -> float:
    """How much longer a monster stays under the towers when chilled this deep."""
    return chill / (1.0 - chill)


def _landing(world: World, m: Monster, delay: float) -> float:
    if m.door >= 0 or m.frozen >= delay:
        return m.s
    s = m.s + m.speed * delay
    if not m.kind.flying:
        for index, crossing in world.level.crossings(m.route):
            if world.doors[index].built and crossing > m.s:
                return min(s, max(m.s, crossing - DOOR_STOP - JOSTLE / 2))
    return s


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _announced_breach_groups(world: World) -> tuple[Group, ...]:
    """The accepted side pack while it is upcoming or still visible on the map."""
    spec = world.breach_spec
    if spec is None or not world.breach_opened:
        return ()
    if spec.after_wave <= world.wave <= spec.after_wave + 1 or any(m.route == "breach" for m in world.monsters):
        return spec.groups
    return ()


class Study:
    """One independent run of bins per entrance route, and a first guess at where monsters spend time."""

    def __init__(self, world: World) -> None:
        level = world.level
        side_groups = _announced_breach_groups(world)
        self.side_included = bool(side_groups)
        self.level = level
        self.routes = level.routes
        self.route_bounds: dict[str, tuple[int, int]] = {}
        self.bin_bounds: list[tuple[int, int]] = []
        self.bin_route: list[str] = []
        self.centres: list[tuple[float, float]] = []
        for route in self.routes:
            start = len(self.centres)
            count = math.ceil(route.length) + 1
            end = start + count
            self.route_bounds[route.key] = start, end
            self.bin_bounds.extend([(start, end)] * count)
            self.bin_route.extend([route.key] * count)
            self.centres.extend(route.point(min(route.length, s + 0.5)) for s in range(count))
        self.bins = len(self.centres)
        self.tiles = [(x, y) for y in range(level.height) for x in range(level.width) if level.buildable(x, y)]
        self.queue_bins: dict[int, tuple[int, ...]] = {
            door.index: tuple(self.bin(s - DOOR_STOP - JOSTLE / 2, route.key)
                              for route in self.routes for index, s in level.crossings(route.key)
                              if index == door.index)
            for door in world.doors}
        self._cover: dict[tuple, tuple[tuple[int, float], ...]] = {}
        self.roster = tuple(dict.fromkeys((*world.location.monsters, *(group.kind for group in side_groups))))
        gates = world.location.arsenal.gates
        counts: dict[tuple[str, str], float] = {}
        groups = (group for wave in world.waves for group in wave.groups)
        for group in (*groups, *side_groups):
            choices = self.spawn_routes(group.kind, group.route)
            for route in choices:
                pair = group.kind, route
                counts[pair] = counts.get(pair, 0.0) + group.count / len(choices)
        self.route_share: dict[str, dict[str, float]] = {}
        self.guess: dict[str, list[float]] = {}
        for key in self.roster:
            kind = MONSTERS[key]
            total = sum(counts.get((key, route.key), 0.0) for route in self.routes)
            assert total > 0
            seconds = [0.0] * self.bins
            self.route_share[key] = {}
            for route in self.routes:
                start, end = self.bounds(route.key)
                share = counts.get((key, route.key), 0.0) / total
                self.route_share[key][route.key] = share
                for b in range(start, end):
                    seconds[b] = share / kind.speed
                if gates and not kind.flying:
                    for _, s in level.crossings(route.key):
                        seconds[self.bin(s - DOOR_STOP - JOSTLE / 2, route.key)] += QUEUE_GUESS * share
            self.guess[key] = seconds
        self.guess_seconds = [sum(self.guess[k][b] for k in self.roster) for b in range(self.bins)]
        self.queues: set[int] = {b for bins in self.queue_bins.values() for b in bins} if gates else set()
        self.guess_near = [4.0 if b in self.queues else 1.5 for b in range(self.bins)]
        self.guess_around = [5.0 if b in self.queues else 3.0 for b in range(self.bins)]

    def spawn_routes(self, kind: str, authored: str) -> tuple[str, ...]:
        if MONSTERS[kind].movement != "wander":
            return (authored,)
        entrance = self.level.route(authored).entrance
        return tuple(route.key for route in self.routes if route.entrance == entrance)

    def bounds(self, route: str) -> tuple[int, int]:
        return self.route_bounds[route]

    def bin(self, s: float, route: str = "main") -> int:
        start, end = self.bounds(route)
        return min(end - 1, max(start, start + int(s)))

    def nearest_bin(self, at: tuple[float, float]) -> int:
        return min(range(self.bins), key=lambda b: (self.centres[b][0] - at[0]) ** 2
                   + (self.centres[b][1] - at[1]) ** 2)

    def cover(self, tile: tuple[int, int], reach: float) -> tuple[tuple[int, float], ...]:
        """The bins a tile's reach covers, each with the length of path in it that is covered."""
        key = (tile, round(reach, 3))
        found = self._cover.get(key)
        if found is None:
            shares: dict[int, float] = {}
            for route in self.routes:
                for a, b in route.coverage(tile, reach):
                    k = int(a)
                    while k < b:
                        index = self.bin(k, route.key)
                        shares[index] = shares.get(index, 0.0) + min(b, k + 1) - max(a, k)
                        k += 1
            found = self._cover[key] = tuple(sorted(shares.items()))
        return found
