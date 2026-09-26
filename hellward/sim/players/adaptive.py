"""The adaptive defender: it reads the fight as it goes instead of following a recipe.

It keeps a picture of the path, cut into one-tile bins, learned from the monsters it watches: how long each
kind of monster spends in each bin (a queue at a gate holds it for seconds, a frost shrine slows it), how
crowded the bin is (a fireball or a leap of lightning is worth more in a crowd), and which kinds get through
to the sanctuary. A monster's trail joins the picture when it dies or leaks, so the picture shows where
monsters really get to under the towers already standing. Before the first monster it is a guess from the map
and the location's roster, as a person has it from the intro; while a wave runs, the monsters on the map and
still to come weigh in with the trails their kinds usually walk.

From that picture every build and upgrade is priced as the damage it would deal per wave, weighted towards the
kinds that leak and the leaders, per gold; the best is bought, or saved for. A frost shrine is also priced by
the damage its chill lets the other towers deal, a plague totem only by the venom that finds room, and an
upgrade loses what the leaders' curses have been taking from its tower. Gates go into arches the towers watch
and back up as soon as the arch is clear. A tower that stopped seeing monsters is sold between waves. In the
last stretch, once the last wave has sent everything, only the monsters left are priced, and the towers they
have all walked past are sold to stand where they are going: Azazel dies that way on Hell's Gate.

It also keeps, per kind, the damage a monster takes from anywhere on the path to the sanctuary, so it can tell
which monster is about to get through. Mana is kept for Smite while leaders walk: a chant at a tower that
matters is broken (two at once with a Frozen Orb), a leader Smite can finish is finished, and a monster Smite
can stop is stopped. What mana is left goes to the damage that saves most lives: Meteor on a thick crowd, a
Frozen Orb on a gate about to break or a clump getting through, a Smite on whatever costs many lives, and never
a full orb wasting its flow. Cleanse lifts the curse costing the most. A break is cut short for its gold when
the last wave cost nothing and the mana is in hand.

Its skills come from a themed order of the tree (:data:`ORDERS`), cut to the sigils in hand and to what the
location offers. Which order suits a location was found by playing each on training seeds
(``tools/adaptive_skills.py``); the choice is kept in ``plans/adaptive.json``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from hellward.sim.campaign import Difficulty, Location
from hellward.sim.content import (
    CURSES, DOOR, MONSTERS, SELL_REFUND, SPELLS, TOWERS, Curse, Element, MonsterKind, TowerLevel,
)
from hellward.sim.model import DOOR_STOP, JOSTLE, Monster, Refused, Tower, World
from hellward.sim.players.hands import AIM_GAP, Hands
from hellward.sim.skills import SKILLS, can_learn

SAMPLE = 0.25          # seconds between two looks at where the monsters are
THINK = 0.25           # seconds between two decisions about gold
REFRESH = 4.0          # seconds between two re-readings of the picture while a wave runs
GUESS = 3.0            # monsters of each kind the first guess is worth against what is seen
NOW = 2.0              # what a monster of this wave, on the map or still to come, weighs against one seen before
FADE = 0.75            # what an older wave's monsters still weigh when a new wave starts
QUEUE_GUESS = 4.0      # seconds a monster is guessed to wait at a standing gate, before any is seen
QUEUE_WAIT = 4.0       # seconds a monster is reckoned to wait at each standing gate ahead, asking who gets through
URGENCY = 1.2          # how much more a bin by the sanctuary is worth than one at the portal (found on training seeds)
LEAKY = 4.0            # how much more damage to a kind is worth when all of it leaks
LEADER = 1.5           # how much more damage to a leader is worth
SPLASH_HIT = 0.6       # a fireball's share on the monsters around its target (the rules' number)
VENOM_ROOM = 1.0       # venom darts a second one monster can take: four stacks that last four seconds
VENOM_TRUST = 0.6      # how far the estimate of a plague totem is trusted, and a frost nova's: both found by
NOVA_TRUST = 1.3       # playing training seeds, where totems proved worth less and novas more than estimated
STORM_TRUST = 1.0
FIRE_TRUST = 1.0
SETTLE = 0.8           # an affordable buy this close to the best is taken instead of saving for the best
IDLE = 5.0             # a tower is sold when its gold would buy this many times what it does
CALL_MANA = 0.92       # share of a full orb an early call needs in hand
ELEMENTS = tuple(Element)
SEVERITY = {Curse.WEAKEN: 1.0 - CURSES[Curse.WEAKEN].damage, Curse.DECREPIFY: 1.0 - CURSES[Curse.DECREPIFY].rate,
            Curse.DIM_VISION: 0.5, Curse.BONE_PRISON: 1.0}
SMITE_SHARE = 0.04     # a chant at a tower doing this share of the damage is worth a Smite
CLEANSE_SHARE = 0.15   # a curse on a tower doing this share of the damage is worth a Cleanse
PASSED = 0.5           # a monster presses once it has walked past this share of the towers' fire, and would survive
CALM = 0.25            # damage to a monster the towers will kill anyway, against one that would get through
HOLD = 2.0             # a Frozen Orb's worth over its damage: the frozen stay under the towers, a gate stops breaking
METEOR_WORTH = 3.0     # a Meteor falls unpressed where it would take at least this many times its damage off the pack
ORB_CROWD = 4          # monsters at a gate about to break that are worth a Frozen Orb
BOSS = 5               # lives a monster costs that make it worth every spare Smite

PLANS = Path(__file__).parent / "plans" / "adaptive.json"
ORDERS: dict[str, tuple[str, ...]] = {
    "mixed": ("holy_shield", "fire_mastery", "warmth", "cold_mastery", "fire_ball", "lightning_mastery",
              "chain_lightning", "salvation", "poison_mastery", "glacial_spike", "soul_harvest", "thorns",
              "spell_mastery"),
    "warden": ("holy_shield", "warmth", "cold_mastery", "salvation", "fire_mastery", "poison_mastery",
               "lightning_mastery", "thorns", "glacial_spike", "soul_harvest"),
    "sorcerer": ("warmth", "soul_harvest", "spell_mastery", "holy_shield", "cold_mastery", "fire_mastery",
                 "poison_mastery", "lightning_mastery", "glacial_spike"),
    "frost": ("cold_mastery", "glacial_spike", "holy_shield", "warmth", "shatter", "fire_mastery", "poison_mastery"),
    "fire": ("fire_mastery", "fire_ball", "holy_shield", "warmth", "cold_mastery", "blaze"),
    "storm": ("lightning_mastery", "chain_lightning", "holy_shield", "warmth", "cold_mastery", "static_field"),
    "venom": ("poison_mastery", "holy_shield", "contagion", "warmth", "cold_mastery", "lower_resist"),
}
DEFAULT_ORDER = "mixed"
TOWER_OF = {"fire": "pyre", "lightning": "storm", "cold": "frost", "poison": "plague"}


def useful(location: Location, key: str) -> bool:
    """Whether a skill does anything here: its tower is offered, its gates, its spells, its leaders."""
    skill = SKILLS[key]
    arsenal = location.arsenal
    leaders = any(MONSTERS[k].leader is not None for k in location.monsters)
    if skill.column in TOWER_OF:
        return TOWER_OF[skill.column] in arsenal.towers
    if key in ("holy_shield", "thorns"):
        return arsenal.gates
    if key in ("salvation", "soul_harvest"):
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
    while True:
        before = learned
        for key in every:
            if can_learn(learned, key, sigils):
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
    s: float = 0.0


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


class Adaptive:
    name = "adaptive"

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
        self.firepower: list[float] = []      # per bin: worth of the damage the towers standing deal there
        self.chilled: list[float] = []        # per bin: the deepest chill a frost shrine lays there
        self.darts: list[float] = []          # per bin: venom darts a second from the totems standing
        self.ahead: dict[str, list[float]] = {}
        self.cursed: dict[int, float] = {}    # per tower: seconds cursed, weighted by how badly, while monsters walked
        self.watched: dict[int, float] = {}   # per tower: seconds it stood while monsters walked
        self.aimed_at = -1e9
        self.sold = -2
        self.endgame = False                  # the last wave has sent every monster it has

    # -- Skills --------------------------------------------------------------------------------------

    def skills(self, location: Location, difficulty: Difficulty, sigils: int) -> frozenset[str]:
        order = self.order
        if not order:
            plans = json.loads(PLANS.read_text()) if PLANS.exists() else {}
            order = plans.get(difficulty.key, {}).get(location.key, DEFAULT_ORDER)
        return learn(location, sigils, ORDERS[order])

    # -- Every step ----------------------------------------------------------------------------------

    def act(self, hands: Hands) -> None:
        world = hands.world
        if self.study is None:
            self.study = Study(world)
            self.picture = Picture(self.study.bins)
            self.lives_at_wave = world.lives
        if world.time >= self.sample_at - 1e-9:
            self.sample_at = world.time + SAMPLE
            self._watch(world)
        if world.wave != self.wave:
            self._new_wave(world)
        if not self.endgame and world.wave == len(world.location.waves) - 1 and not world.schedule:
            self.endgame = True
            self.view = None
        if self.view is None or world.time >= self.refresh_at:
            self.refresh_at = world.time + REFRESH
            self._reread(world)
        self._spells(hands)
        self._gates(world)
        if world.time >= self.think_at - 1e-9:
            self.think_at = world.time + THINK
            self._sell(world)
            self._salvage(world)
            self._spend(world)
            self._call(world)

    # -- Watching ------------------------------------------------------------------------------------

    def _watch(self, world: World) -> None:
        """Note where every monster stands and how crowded it is there, and which towers carry curses; fold the
        trails of the monsters gone."""
        study = self.study
        counts = [0] * study.bins
        for m in world.monsters:
            counts[study.bin(m.s)] += 1
        prefix = [0]
        for c in counts:
            prefix.append(prefix[-1] + c)
        alive = set()
        for m in world.monsters:
            alive.add(m.id)
            trail = self.trails.get(m.id)
            if trail is None:
                trail = self.trails[m.id] = Trail(m.kind)
            b = study.bin(m.s)
            weight = SAMPLE * (0.3 + 0.7 * m.hp / m.max_hp)
            near = prefix[min(study.bins, b + 2)] - prefix[max(0, b - 1)]
            around = prefix[min(study.bins, b + 4)] - prefix[max(0, b - 3)]
            trail.seconds[b] = trail.seconds.get(b, 0.0) + weight
            trail.near[b] = trail.near.get(b, 0.0) + weight * near
            trail.around[b] = trail.around.get(b, 0.0) + weight * around
            trail.s = m.s
        if world.monsters:
            for t in world.towers.values():
                self.watched[t.id] = self.watched.get(t.id, 0.0) + SAMPLE
                if t.curses:
                    self.cursed[t.id] = self.cursed.get(t.id, 0.0) + SAMPLE * max(SEVERITY[c] for c in t.curses)
        for key in [k for k in self.trails if k not in alive]:
            trail = self.trails.pop(key)
            self.picture.fold(trail, leaked=trail.s + trail.kind.speed * SAMPLE * 2 >= study.length)

    def _new_wave(self, world: World) -> None:
        self.lost_last = self.lives_at_wave - world.lives
        self.lives_at_wave = world.lives
        self.wave = world.wave
        self.picture.fade(FADE)
        self.view = None

    def _reread(self, world: World) -> None:
        """Blend the picture with the guess from the map and the roster, and with the monsters of this wave (on the
        map and still to come, each walking the rest of its kind's usual trail); then price everything anew."""
        study, picture = self.study, self.picture
        bins = study.bins
        coming: dict[str, list[float]] = {}
        for m in world.monsters:
            coming.setdefault(m.kind.key, [0.0] * bins)[study.bin(m.s)] += 1.0
        for _, key in world.schedule:
            coming.setdefault(key, [0.0] * bins)[0] += 1.0
        seconds = [0.0] * bins
        worth = {e: [0.0] * bins for e in ELEMENTS}
        venom = [0.0] * bins
        pull = [0.0] * bins          # seconds × life³ of poisonable monsters: who a totem aims at
        poisonable = [0.0] * bins
        for key in study.roster:
            kind = MONSTERS[key]
            came = picture.came.get(key, 0.0)
            seen = picture.seconds.get(key)
            usual = [t / came for t in seen] if seen is not None and came >= 1.0 else study.guess[key]
            past = 0.0 if self.endgame else 1.0   # in the last stretch only the monsters left matter
            here = [past * study.guess[key][b] * GUESS for b in range(bins)]
            if seen is not None:
                here = [h + past * t for h, t in zip(here, seen)]
            starts = coming.get(key)
            if starts is not None:
                walking = 0.0
                for b in range(bins):
                    walking += starts[b]
                    here[b] += NOW * walking * usual[b]
            leaked = picture.leaked.get(key, 0.0) / came if came > 0 else 0.0
            value = (1.0 + LEAKY * leaked) * (LEADER if kind.leader is not None else 1.0)
            size = kind.hp ** 3
            poison = _taken(kind, Element.POISON)
            for b in range(bins):
                t = here[b]
                if t <= 0:
                    continue
                seconds[b] += t
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
        self.view = View(seconds, near, around, worth, venom, poisonable, room)
        self.density = {}
        for kind in world.location.arsenal.towers:
            for level, stats in enumerate(world.tower_levels[kind]):
                self.density[(kind, level)] = [self._urgency(b) * self._density(world, kind, stats, b) if seconds[b] > 0
                                               else 0.0 for b in range(bins)]
        self._price(world)

    # -- Prices --------------------------------------------------------------------------------------

    def _urgency(self, b: int) -> float:
        return 1.0 + (URGENCY + 0.1 * self.lost_last) * b / self.study.bins

    def _density(self, world: World, kind: str, stats: TowerLevel, b: int) -> float:
        """Worth of the damage a tower of this kind and rank deals per wave from one bin of path it reaches."""
        view = self.view
        attack = TOWERS[kind].attack
        dps = stats.damage * stats.rate
        around = view.around[b]
        if attack == "nova":
            return NOVA_TRUST * dps * view.worth[Element.COLD][b]
        if attack == "venom":
            stacks = min(4.0, stats.poison_time * stats.rate)
            crowd = max(1.0, around * view.poisonable[b] / view.seconds[b])
            return VENOM_TRUST * (dps + stats.poison * stacks) * view.venom[b] / crowd
        busy = view.worth[TOWERS[kind].element][b] / around
        if attack == "chain":
            reached = min(1.0 + stats.chains, around)
            keeps = world.perks.leap_keeps
            return STORM_TRUST * dps * busy * sum(keeps ** i * min(1.0, reached - i) for i in range(math.ceil(reached)))
        if stats.splash > 0:
            return FIRE_TRUST * dps * busy * (1.0 + SPLASH_HIT * min(3.0, (view.near[b] - 1.0) * min(1.0, stats.splash / 1.2)))
        return FIRE_TRUST * dps * busy

    def worth(self, kind: str, level: int, stats: TowerLevel, tile: tuple[int, int], chilled: list[float],
              darts: list[float]) -> float:
        """Worth of the damage per wave a tower of this kind and rank would deal on this tile, from the picture;
        a frost shrine adds what its chill lets the others deal where nothing chills yet, and a plague totem counts
        only the venom that finds room: four stacks on a monster at most, and every totem aims at the strongest."""
        density = self.density[(kind, level)]
        value = 0.0
        cover = self.study.cover(tile, stats.range)
        if stats.chill > 0:
            gain = _slowed(stats.chill)
            for b, share in cover:
                value += share * (density[b] + max(0.0, gain - _slowed(chilled[b])) * self.firepower[b])
            return value
        if stats.poison > 0:
            room = self.view.room
            for b, share in cover:
                value += share * density[b] * min(1.0, max(0.1, (room[b] - darts[b]) / stats.rate))
            return value
        for b, share in cover:
            value += share * density[b]
        return value

    def _price(self, world: World) -> None:
        """Price every tower that could stand and every upgrade: worth per gold."""
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
            if cost is not None:
                better = self.worth(t.kind.key, t.level + 1, t.levels[t.level + 1], t.tile, chilled, darts)
                prices[("upgrade", t.id)] = (better - self.tower_worth[t.id]) * (1.0 - self._curse_share(t)) / cost
        standing = {t.tile for t in world.towers.values()}
        for kind in world.location.arsenal.towers:
            stats = world.tower_levels[kind][0]
            for tile in study.tiles:
                if tile not in standing:
                    worth = self.worth(kind, 0, stats, tile, self.chilled, self.darts)
                    prices[("build", kind, tile)] = worth / stats.cost
        self.prices = prices
        self.cheapest = min((self._cost(world, k) for k in prices), default=0)

    def _chilled_but(self, tower: Tower, frosts: list[Tower]) -> list[float]:
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
        bins = study.bins
        hurt = {e: [0.0] * bins for e in ELEMENTS}
        for t in world.towers.values():
            stats = t.stats
            dps = stats.damage * stats.rate
            if t.kind.attack == "venom":
                dps += stats.poison * min(4.0, stats.poison_time * stats.rate)
            for b, share in study.cover(t.tile, stats.range):
                hurt[t.kind.element][b] += share * dps
        gates = [d for d in world.doors if d.built]
        self.ahead = {}
        for key in study.roster:
            kind = MONSTERS[key]
            taken = {e: _taken(kind, e) for e in ELEMENTS}
            dwell = [1.0 / kind.speed] * bins
            if not kind.flying:
                for d in gates:
                    dwell[study.queue_bins[d.index]] += QUEUE_WAIT
            total = 0.0
            ahead = [0.0] * bins
            for b in range(bins - 1, -1, -1):
                total += dwell[b] * sum(hurt[e][b] * taken[e] for e in ELEMENTS) / view.around[b] ** 0.5
                ahead[b] = total
            self.ahead[key] = ahead

    def threat(self, m: Monster) -> float:
        """Life a monster is likely to carry into the sanctuary; zero or less if the towers ahead should kill it."""
        return m.hp - self.ahead[m.kind.key][self.study.bin(m.s)]

    def pressing(self, m: Monster) -> bool:
        """A monster that would get through and has already walked past most of the towers' fire (a person trusts
        the towers with a monster at the portal), or one that costs many lives."""
        ahead = self.ahead[m.kind.key]
        passed = ahead[self.study.bin(m.s)] <= PASSED * ahead[0]
        return self.threat(m) > 0 and (passed or m.kind.lives >= BOSS)

    # -- Gold ----------------------------------------------------------------------------------------

    def _spend(self, world: World) -> None:
        """Buy the best-priced build or upgrade; when it is out of reach, one nearly as good that is not, else save."""
        while self.prices:
            spare = world.gold - self._keep(world)
            if spare < self.cheapest:
                return
            prices = self.prices
            top = max(prices, key=prices.get)
            best = prices[top]
            if best <= 0:
                return
            choice = top if self._cost(world, top) <= spare else None
            if choice is None:
                near = [k for k, v in prices.items() if v >= best * SETTLE and self._cost(world, k) <= spare]
                if not near:
                    return
                choice = max(near, key=prices.get)
            if choice[0] == "build":
                world.build(choice[1], choice[2])
            else:
                world.upgrade(choice[1])
            self._price(world)

    def _sell(self, world: World) -> None:
        """Between waves, sell one tower that no longer sees monsters when its gold would buy far more elsewhere."""
        if world.monsters or world.schedule or self.sold == world.wave or not self.prices:
            return
        best = max(self.prices.values())
        idle = [t for t in world.towers.values() if self.tower_worth[t.id] * IDLE < best * t.spent * SELL_REFUND]
        if idle:
            world.sell(min(idle, key=lambda t: self.tower_worth[t.id] / t.spent).id)
            self.sold = world.wave
            self._price(world)

    def _salvage(self, world: World) -> None:
        """In the last wave, once every monster has come, sell the towers all of them have walked past: those will
        never fire again, and their gold can still stand where the monsters are going."""
        if not self.endgame or not world.monsters:
            return
        rear = min(m.s for m in world.monsters)
        behind = [t for t in world.towers.values()
                  if max(b for b, _ in self.study.cover(t.tile, t.stats.range)) + 1 < rear]
        for t in behind:
            world.sell(t.id)
        if behind:
            self._price(world)

    def _cost(self, world: World, choice: tuple) -> int:
        if choice[0] == "build":
            return world.cost(choice[1])
        return world.upgrade_cost(world.towers[choice[1]])

    def _keep(self, world: World) -> int:
        """Gold held back for a gate that is down or failing, where towers watch its queue."""
        for d in world.doors:
            if self._guarded(d.index) and (not d.built or d.hp < world.gate_life * 0.35):
                return DOOR.cost
        return 0

    def _guarded(self, index: int) -> bool:
        return bool(self.firepower) and self.firepower[self.study.queue_bins[index]] > 0

    def _gates(self, world: World) -> None:
        if not world.location.arsenal.gates or world.gold < DOOR.cost:
            return
        for d in world.doors:
            if not d.built and self._guarded(d.index) and world.gold >= DOOR.cost:
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
        if "cleanse" in world.location.arsenal.spells:
            self._cleanse(hands)
        if world.time - self.aimed_at < AIM_GAP - 1e-9 or not world.monsters:
            return
        if self._answer(hands) or self._strike(hands):
            self.aimed_at = world.time

    def _reserve(self, world: World) -> float:
        """Mana kept for Smite while a leader walks or is still to come in this wave."""
        if "smite" not in world.location.arsenal.spells:
            return 0.0
        coming = any(MONSTERS[key].leader is not None for _, key in world.schedule)
        walking = any(m.kind.leader is not None for m in world.monsters)
        return world.spell_cost("smite") if coming or walking else 0.0

    def _share(self, tower_id: int) -> float:
        total = sum(self.tower_worth.values()) or 1.0
        return self.tower_worth.get(tower_id, 0.0) / total

    def _can(self, world: World, spell: str) -> bool:
        return spell in world.location.arsenal.spells and world.mana >= world.spell_cost(spell)

    def _answer(self, hands: Hands) -> bool:
        """The leaders first: a Frozen Orb on two chants at once, a Smite on a chant at a tower that matters, a Smite
        that finishes a leader, and a Smite that stops a monster getting through."""
        world = hands.world
        chants = [(sign, world.monster(sign.leader)) for sign in hands.threats() if sign.kind == "chant"]
        chants = [(sign, m) for sign, m in chants if m is not None]
        if len(chants) >= 2 and self._can(world, "orb"):
            radius = SPELLS["orb"].radius
            for _, m in chants:
                at = world.position(m)
                if sum(1 for _, o in chants if _dist(world.position(o), at) <= radius) >= 2:
                    hands.orb(*at)
                    return True
        if not self._can(world, "smite"):
            return False
        full = world.mana >= world.mana_max - 5
        for sign, m in chants:
            if self._share(sign.tower) * SEVERITY[sign.curse] >= SMITE_SHARE or full:
                hands.smite(m.id)
                return True
        blow = SPELLS["smite"].damage * world.power()
        for m in world.leaders():
            if m.hp <= blow:
                hands.smite(m.id)
                return True
        rescue = [m for m in world.monsters if 0 < self.threat(m) <= blow and m.s > self.study.length * 0.5]
        if rescue:
            hands.smite(max(rescue, key=lambda m: (m.kind.lives, m.s)).id)
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

        options = []
        if self._can(world, "smite") and (spare >= world.spell_cost("smite") or full):
            blow = SPELLS["smite"].damage * power
            m = max(world.monsters, key=lambda m: (min(blow, m.hp) * weight(m), m.s))
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
            if at is not None and self.firepower[self.study.bin(self._s_at(at))] <= 0:
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
            hands.smite(target)
        elif spell == "meteor":
            hands.meteor(*target)
        else:
            hands.orb(*target)
        return True

    def _crowd(self, world: World, radius: float, delay: float, blow: float, element: Element, weight) -> tuple:
        """Where a spell falling ``delay`` from now does the most weighted damage: (where, weighted damage, damage)."""
        ahead = [(m, world.level.point(_landing(m, delay))) for m in world.monsters]
        best, best_raw, best_at = 0.0, 0.0, None
        for _, at in ahead:
            got = raw = 0.0
            for m, where in ahead:
                if _dist(where, at) <= radius:
                    hurt = min(m.hp, blow * max(0.0, m.kind.taken(element)))
                    raw += hurt
                    got += hurt * weight(m)
            if got > best:
                best, best_raw, best_at = got, raw, at
        return best_at, best, best_raw

    def _s_at(self, at: tuple[float, float]) -> float:
        """The path's nearest point to a spot on the floor, as ``s``."""
        level = self.study.level
        return min((level.s_of(tile) for tile in level.path_tiles),
                   key=lambda s: (level.point(s)[0] - at[0]) ** 2 + (level.point(s)[1] - at[1]) ** 2)

    def _failing_gate(self, world: World) -> tuple[float, float] | None:
        """The queue at a gate that will break within two seconds, when enough monsters batter it."""
        for d in world.doors:
            if not d.built:
                continue
            queue = [m for m in world.monsters if m.door == d.index]
            if len(queue) < ORB_CROWD:
                continue
            blows = sum(m.kind.door_dps * (1.0 - m.chill if m.chill_left > 0 else 1.0) for m in queue)
            if d.hp < blows * 2.0:
                return world.level.point(d.s - DOOR_STOP - JOSTLE / 2)
        return None

    def _cleanse(self, hands: Hands) -> None:
        world = hands.world
        cost = world.spell_cost("cleanse")
        if world.mana < cost:
            return
        best, best_harm = None, 0.0
        for t in world.towers.values():
            if not t.curses:
                continue
            left = max(t.curses.values())
            if left < 2.5:
                continue
            harm = self._share(t.id) * max(SEVERITY[c] for c in t.curses) * left / 8.0
            if harm > best_harm and any(world.in_reach(t, m.s) for m in world.monsters):
                best, best_harm = t, harm
        spare = world.mana - cost - self._reserve(world) * 0.5
        if best is not None and (best_harm >= CLEANSE_SHARE and spare >= 0 or world.mana >= world.mana_max - 5):
            hands.cleanse(best.id)


def _taken(kind: MonsterKind, element: Element) -> float:
    return max(0.0, kind.taken(element))


def _slowed(chill: float) -> float:
    """How much longer a monster stays under the towers when chilled this deep."""
    return chill / (1.0 - chill)


def _landing(m: Monster, delay: float) -> float:
    if m.door >= 0 or m.frozen >= delay:
        return m.s
    return m.s + m.speed * delay


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Study:
    """The map as a person reads it before the first wave: the bins, the tiles, what each tile's reach covers,
    and a first guess at where each kind of the roster will spend its time."""

    def __init__(self, world: World) -> None:
        level = world.level
        self.level = level
        self.length = level.length
        self.bins = math.ceil(level.length) + 1
        self.tiles = [(x, y) for y in range(level.height) for x in range(level.width) if level.buildable(x, y)]
        self.queue_bins = [self.bin(d.s - DOOR_STOP - JOSTLE / 2) for d in world.doors]
        self._cover: dict[tuple, tuple[tuple[int, float], ...]] = {}
        self.roster = world.location.monsters
        gates = world.location.arsenal.gates
        self.guess: dict[str, list[float]] = {}
        for key in self.roster:
            kind = MONSTERS[key]
            seconds = [1.0 / kind.speed] * self.bins
            if gates and not kind.flying:
                for b in self.queue_bins:
                    seconds[b] += QUEUE_GUESS
            self.guess[key] = seconds
        self.guess_seconds = [sum(self.guess[k][b] for k in self.roster) for b in range(self.bins)]
        queues = set(self.queue_bins) if gates else set()
        self.guess_near = [4.0 if b in queues else 1.5 for b in range(self.bins)]
        self.guess_around = [5.0 if b in queues else 3.0 for b in range(self.bins)]

    def bin(self, s: float) -> int:
        return min(self.bins - 1, max(0, int(s)))

    def cover(self, tile: tuple[int, int], reach: float) -> tuple[tuple[int, float], ...]:
        """The bins a tile's reach covers, each with the length of path in it that is covered."""
        key = (tile, round(reach, 3))
        found = self._cover.get(key)
        if found is None:
            shares: dict[int, float] = {}
            for a, b in self.level.coverage(tile, reach):
                k = int(a)
                while k < b:
                    shares[k] = shares.get(k, 0.0) + min(b, k + 1) - max(a, k)
                    k += 1
            found = self._cover[key] = tuple((self.bin(k), v) for k, v in sorted(shares.items()))
        return found
