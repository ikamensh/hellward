"""The adaptive defender: it reads the fight as it goes instead of following a recipe.

It keeps a picture of the path, cut into one-tile bins, learned from the monsters it watches: how long a
monster spends in each bin (a queue at a gate holds it for seconds, a frost shrine slows it), how crowded
the bin is (a fireball or a leap of lightning is worth more in a crowd), and how much of each element the
monsters there shrug off, weighted by their life. A monster's trail joins the picture when it dies or leaks,
so the picture shows where monsters really get to under the towers already standing. Before the first
monster it is a guess from the map and the location's roster, as a person has it from the intro.

From that picture every build and upgrade is priced as damage per monster per gold, and the best is bought
(or saved for). Gates go into arches the towers cover, and back up as soon as the arch is clear. Mana is kept
for Smite while leaders walk: a chant at a tower that matters is broken, a leader Smite can finish is
finished, Frozen Orb breaks two chants at once or holds a queue at a breaking gate, Meteor falls on the
thickest crowd, and Cleanse lifts the curse costing the most. A quiet break is cut short for its gold.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from hellward.sim.campaign import Difficulty, Location
from hellward.sim.content import CURSES, DOOR, MONSTERS, SPELLS, TOWERS, Curse, Element, MonsterKind, TowerLevel
from hellward.sim.model import DOOR_STOP, JOSTLE, Monster, Refused, Tower, World
from hellward.sim.players.hands import AIM_GAP, Hands
from hellward.sim.skills import SKILLS, can_learn

SAMPLE = 0.25          # seconds between two looks at where the monsters are
THINK = 0.25           # seconds between two decisions about gold
REFRESH = 4.0          # seconds between two re-readings of the picture while a wave runs
PRIOR = 12.0           # monsters' worth of weight the first guess keeps against what is seen
FADE = 0.75            # what an older wave's monsters still weigh when a new wave starts
QUEUE_GUESS = 4.0      # seconds a monster is guessed to wait at a standing gate, before any is seen
URGENCY = 0.4          # how much more a bin near the sanctuary is worth than one at the portal
SPLASH_HIT = 0.6       # a fireball's share on the monsters around its target (the rules' number)
ELEMENTS = tuple(Element)
SEVERITY = {Curse.WEAKEN: 1.0 - CURSES[Curse.WEAKEN].damage, Curse.DECREPIFY: 1.0 - CURSES[Curse.DECREPIFY].rate,
            Curse.DIM_VISION: 0.5, Curse.BONE_PRISON: 1.0}
SMITE_SHARE = 0.12     # a chant at a tower doing this share of the damage is worth a Smite
CLEANSE_SHARE = 0.15   # a curse on a tower doing this share of the damage is worth a Cleanse
METEOR_WORTH = 3.0     # a Meteor falls where it would take at least this many times its damage off the pack
ORB_CROWD = 4          # monsters at a gate about to break that are worth a Frozen Orb


@dataclass
class Trail:
    """Where one monster has been: per bin, seconds spent (discounted as it weakens) and the crowd around it."""

    kind: MonsterKind
    seconds: dict[int, float] = field(default_factory=dict)
    near: dict[int, float] = field(default_factory=dict)    # seconds × monsters within a bin
    around: dict[int, float] = field(default_factory=dict)  # seconds × monsters within three bins
    s: float = 0.0


class Picture:
    """What the monsters do on this path, per bin: sums over every monster watched, and the guess before them."""

    def __init__(self, bins: int) -> None:
        self.bins = bins
        self.seconds = [0.0] * bins
        self.near = [0.0] * bins
        self.around = [0.0] * bins
        self.heft = [0.0] * bins                      # seconds × the monster's life, for the elements' shares
        self.taken = {e: [0.0] * bins for e in ELEMENTS}
        self.monsters = 0.0

    def fold(self, trail: Trail) -> None:
        kind = trail.kind
        for b, t in trail.seconds.items():
            self.seconds[b] += t
            self.near[b] += trail.near[b]
            self.around[b] += trail.around[b]
            self.heft[b] += t * kind.hp
            for e in ELEMENTS:
                self.taken[e][b] += t * kind.hp * _taken(kind, e)
        self.monsters += 1

    def fade(self, share: float) -> None:
        for values in (self.seconds, self.near, self.around, self.heft, *self.taken.values()):
            for b in range(self.bins):
                values[b] *= share
        self.monsters *= share


def _taken(kind: MonsterKind, element: Element) -> float:
    if element is Element.POISON and kind.taken(element) <= 0:
        return 0.0
    return kind.taken(element)


@dataclass
class View:
    """The picture blended with the guess, per monster: what the prices are read from."""

    seconds: list[float]
    near: list[float]      # monsters within a bin of a monster here
    around: list[float]    # monsters within three bins
    taken: dict[Element, list[float]]


class Adaptive:
    name = "adaptive"

    def __init__(self) -> None:
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
        self.tower_worth: dict[int, float] = {}
        self.aimed_at = -1e9

    # -- Skills --------------------------------------------------------------------------------------

    def skills(self, location: Location, difficulty: Difficulty, sigils: int) -> frozenset[str]:
        arsenal = location.arsenal
        roster = [MONSTERS[k] for k in location.monsters]
        walkers = [m for m in roster if not m.flying and m.leader is None]
        leaders = [m for m in roster if m.leader is not None]
        wanted: list[str] = []
        if arsenal.gates and walkers:
            wanted.append("holy_shield")
        if "pyre" in arsenal.towers:
            wanted.append("fire_mastery")
        if "smite" in arsenal.spells and leaders:
            wanted.append("warmth")
        if "frost" in arsenal.towers:
            wanted.append("cold_mastery")
        if "pyre" in arsenal.towers:
            wanted.append("fire_ball")
        if "storm" in arsenal.towers:
            wanted += ["lightning_mastery", "chain_lightning"]
        if leaders:
            wanted.append("salvation")
        if "plague" in arsenal.towers:
            wanted.append("poison_mastery")
        if "frost" in arsenal.towers:
            wanted.append("glacial_spike")
        if "smite" in arsenal.spells and leaders:
            wanted.append("soul_harvest")
        if arsenal.gates and walkers:
            wanted.append("thorns")
        if len(arsenal.spells) > 2:
            wanted.append("spell_mastery")
        wanted += ["static_field", "shatter", "blaze", "contagion", "lower_resist"]
        learned: frozenset[str] = frozenset()
        for key in wanted:
            if can_learn(learned, key, sigils):
                learned |= {key}
        for key in SKILLS:   # whatever is left over buys the rest, in the tree's order
            if can_learn(learned, key, sigils):
                learned |= {key}
        return learned

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
        if self.view is None or world.time >= self.refresh_at:
            self.refresh_at = world.time + REFRESH
            self._reread(world)
        self._spells(hands)
        self._gates(world)
        if world.time >= self.think_at - 1e-9:
            self.think_at = world.time + THINK
            self._spend(world)
            self._call(world)

    # -- Watching ------------------------------------------------------------------------------------

    def _watch(self, world: World) -> None:
        """Note where every monster stands and how crowded it is there; fold the trails of those gone."""
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
        for key in [k for k in self.trails if k not in alive]:
            self.picture.fold(self.trails.pop(key))

    def _new_wave(self, world: World) -> None:
        self.lost_last = self.lives_at_wave - world.lives
        self.lives_at_wave = world.lives
        self.wave = world.wave
        self.picture.fade(FADE)
        self.view = None

    def _reread(self, world: World) -> None:
        """Blend the picture with the guess from the map and the roster, per monster; then price everything anew."""
        study, picture = self.study, self.picture
        guess = study.guess
        weight = PRIOR
        total = weight + picture.monsters
        seconds, near, around = [], [], []
        taken = {e: [] for e in ELEMENTS}
        for b in range(study.bins):
            g = guess.seconds[b] * weight
            t = g + picture.seconds[b]
            seconds.append(t / total)
            if t <= 0:
                near.append(1.0)
                around.append(1.0)
                for e in ELEMENTS:
                    taken[e].append(guess.taken[e][b])
                continue
            near.append((guess.near[b] * g + picture.near[b]) / t)
            around.append((guess.around[b] * g + picture.around[b]) / t)
            heft = study.mean_hp * g + picture.heft[b]
            for e in ELEMENTS:
                taken[e].append((guess.taken[e][b] * study.mean_hp * g + picture.taken[e][b]) / heft)
        self.view = View(seconds, near, around, taken)
        self._price(world)

    # -- Prices --------------------------------------------------------------------------------------

    def _urgency(self, b: int) -> float:
        return 1.0 + (URGENCY + 0.1 * self.lost_last) * b / self.study.bins

    def worth(self, world: World, kind: str, stats: TowerLevel, tile: tuple[int, int]) -> float:
        """Damage per monster that passes, for a tower of this kind and rank on this tile, from the picture."""
        view = self.view
        cover = self.study.cover(tile, stats.range)
        seconds = near = around = taken = chilled = 0.0
        element = TOWERS[kind].element
        for b, share in cover:
            t = view.seconds[b] * share * self._urgency(b)
            seconds += t
            near += t * view.near[b]
            around += t * view.around[b]
            taken += t * view.taken[element][b]
            if stats.chill > 0:
                chilled += t * self.study.firepower[b]
        if seconds <= 0:
            return 0.0
        near, around, taken = near / seconds, around / seconds, taken / seconds
        dps = stats.damage * stats.rate
        attack = TOWERS[kind].attack
        busy = seconds / max(1.0, around)
        if attack == "nova":
            return dps * seconds * taken + chilled * stats.chill / (1.0 - stats.chill)
        if attack == "chain":
            reached = min(1.0 + stats.chains, max(1.0, around))
            keeps = world.perks.leap_keeps
            hits = sum(keeps ** i * min(1.0, reached - i) for i in range(math.ceil(reached)))
            return dps * busy * taken * hits
        if attack == "venom":
            stacks = min(4.0, stats.poison_time * stats.rate)
            return (dps + stats.poison * stacks) * busy * taken
        hits = 1.0 + SPLASH_HIT * min(3.0, (near - 1.0) * min(1.0, stats.splash / 1.2)) if stats.splash > 0 else 1.0
        return dps * busy * taken * hits

    def _price(self, world: World) -> None:
        """Price every tower that could stand and every upgrade: damage per monster bought per gold."""
        study = self.study
        study.firepower = [0.0] * study.bins
        self.tower_worth = {}
        for t in world.towers.values():
            value = self.worth(world, t.kind.key, t.stats, t.tile)
            self.tower_worth[t.id] = value
            if t.kind.attack != "nova":
                cover = study.cover(t.tile, t.stats.range)
                span = sum(share * self.view.seconds[b] for b, share in cover) or 1.0
                for b, share in cover:
                    study.firepower[b] += value * share / span
        prices: dict[tuple, float] = {}
        taken = {t.tile for t in world.towers.values()}
        for kind in world.location.arsenal.towers:
            stats = world.tower_levels[kind][0]
            for tile in study.tiles:
                if tile not in taken:
                    prices[("build", kind, tile)] = self.worth(world, kind, stats, tile) / stats.cost
        for t in world.towers.values():
            cost = world.upgrade_cost(t)
            if cost is not None:
                better = self.worth(world, t.kind.key, t.levels[t.level + 1], t.tile)
                prices[("upgrade", t.id)] = (better - self.tower_worth[t.id]) / cost
        self.prices = prices

    # -- Gold ----------------------------------------------------------------------------------------

    def _spend(self, world: World) -> None:
        while self.prices:
            choice = max(self.prices, key=lambda k: (self.prices[k], k[0] == "upgrade"))
            if choice[0] == "build":
                _, kind, tile = choice
                if world.gold < world.cost(kind) + self._keep(world):
                    return
                world.build(kind, tile)
            else:
                tower = world.towers[choice[1]]
                if world.gold < world.upgrade_cost(tower) + self._keep(world):
                    return
                world.upgrade(tower.id)
            self._price(world)

    def _keep(self, world: World) -> int:
        """Gold held back for a gate that is down or failing, where towers watch its queue."""
        for d in world.doors:
            if self._guarded(d.index) and (not d.built or d.hp < world.gate_life * 0.35):
                return DOOR.cost
        return 0

    def _guarded(self, index: int) -> bool:
        return self.study.firepower[self.study.queue_bins[index]] > 0 if self.study.firepower else False

    def _gates(self, world: World) -> None:
        if not world.location.arsenal.gates or world.gold < DOOR.cost:
            return
        for d in world.doors:
            if not d.built and self._guarded(d.index) and world.gold >= DOOR.cost:
                try:
                    world.build_door(d.index)
                except Refused:
                    continue
                self.view = None

    def _call(self, world: World) -> None:
        """Cut a break short for its gold when the last wave cost nothing and the mana is in hand."""
        if not world.can_call_wave or world.break_left is None or world.wave < 0 or world.monsters:
            return
        if world.lives == self.lives_at_wave and world.mana >= world.mana_max - 10:
            world.call_wave()

    # -- Spells --------------------------------------------------------------------------------------

    def _spells(self, hands: Hands) -> None:
        world = hands.world
        spells = world.location.arsenal.spells
        if "cleanse" in spells:
            self._cleanse(hands)
        if world.time - self.aimed_at < AIM_GAP - 1e-9:
            return
        for spell, cast in (("smite", self._smite), ("orb", self._orb), ("meteor", self._meteor)):
            if spell in spells and cast(hands):
                self.aimed_at = world.time
                return

    def _reserve(self, world: World) -> float:
        """Mana kept for Smite while a leader walks or is still to come in this wave."""
        if "smite" not in world.location.arsenal.spells:
            return 0.0
        coming = any(MONSTERS[key].leader is not None for _, key in world.schedule)
        walking = any(m.kind.leader is not None for m in world.monsters)
        return world.spell_cost("smite") if coming or walking else 0.0

    def _share(self, world: World, tower_id: int) -> float:
        total = sum(self.tower_worth.values()) or 1.0
        return self.tower_worth.get(tower_id, 0.0) / total

    def _smite(self, hands: Hands) -> bool:
        world = hands.world
        cost = world.spell_cost("smite")
        if world.mana < cost:
            return False
        blow = SPELLS["smite"].damage * world.power()
        for sign in hands.threats():
            if sign.kind != "chant" or world.monster(sign.leader) is None:
                continue
            harm = self._share(world, sign.tower) * SEVERITY[sign.curse]
            if harm >= SMITE_SHARE or world.mana >= world.mana_max - 5:
                hands.smite(sign.leader)
                return True
        spare = world.mana - cost
        for m in world.leaders():
            if m.hp <= blow and spare >= 0:
                hands.smite(m.id)
                return True
        end = self.study.length
        for m in world.monsters:
            if end - m.s < 1.5 * m.kind.speed and m.hp <= blow and spare >= self._reserve(world) - cost:
                hands.smite(m.id)
                return True
        return False

    def _orb(self, hands: Hands) -> bool:
        world = hands.world
        cost = world.spell_cost("orb")
        if world.mana < cost:
            return False
        radius = SPELLS["orb"].radius
        chants = [world.monster(s.leader) for s in hands.threats() if s.kind == "chant"]
        chants = [m for m in chants if m is not None]
        if len(chants) >= 2:
            for m in chants:
                x, y = world.position(m)
                caught = [o for o in chants if _dist(world.position(o), (x, y)) <= radius]
                if len(caught) >= 2:
                    hands.orb(x, y)
                    return True
        if world.mana - cost < self._reserve(world):
            return False
        for d in world.doors:
            if not d.built:
                continue
            queue = [m for m in world.monsters if m.door == d.index]
            if len(queue) < ORB_CROWD:
                continue
            blows = sum(m.kind.door_dps * (1.0 - m.chill if m.chill_left > 0 else 1.0) for m in queue)
            if d.hp < blows * 2.0:
                x, y = world.level.point(d.s - DOOR_STOP - JOSTLE / 2)
                hands.orb(x, y)
                return True
        return False

    def _meteor(self, hands: Hands) -> bool:
        world = hands.world
        cost = world.spell_cost("meteor")
        if world.mana - cost < self._reserve(world):
            return False
        spec = SPELLS["meteor"]
        blow = spec.damage * world.power()
        ahead = [(m, world.level.point(_landing(m, spec.delay))) for m in world.monsters]
        best, best_at = 0.0, None
        for _, at in ahead:
            got = sum(min(m.hp, blow * m.kind.taken(Element.FIRE)) for m, where in ahead
                      if _dist(where, at) <= spec.radius * 0.85)
            if got > best:
                best, best_at = got, at
        if best_at is not None and best >= METEOR_WORTH * blow * (0.6 if world.mana >= world.mana_max - 5 else 1.0):
            hands.meteor(*best_at)
            return True
        return False

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
            harm = self._share(world, t.id) * max(SEVERITY[c] for c in t.curses) * left / 8.0
            if harm > best_harm and any(world.in_reach(t, m.s) for m in world.monsters):
                best, best_harm = t, harm
        spare = world.mana - cost - self._reserve(world) * 0.5
        if best is not None and (best_harm >= CLEANSE_SHARE and spare >= 0 or world.mana >= world.mana_max - 5):
            hands.cleanse(best.id)


def _landing(m: Monster, delay: float) -> float:
    if m.door >= 0 or m.frozen >= delay:
        return m.s
    return m.s + m.speed * delay


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Study:
    """The map as a person reads it before the first wave: the bins, the tiles, what each tile's reach covers,
    and a first guess at where the monsters will spend their time."""

    def __init__(self, world: World) -> None:
        level = world.level
        self.level = level
        self.length = level.length
        self.bins = math.ceil(level.length) + 1
        self.tiles = [(x, y) for y in range(level.height) for x in range(level.width) if level.buildable(x, y)]
        self.queue_bins = [self.bin(d.s - DOOR_STOP - JOSTLE / 2) for d in world.doors]
        self.firepower: list[float] = []
        self._cover: dict[tuple, tuple[tuple[int, float], ...]] = {}
        roster = [MONSTERS[k] for k in world.location.monsters]
        self.mean_hp = sum(k.hp for k in roster) / len(roster)
        self.guess = self._guess(world, roster)

    def bin(self, s: float) -> int:
        return min(self.bins - 1, max(0, int(s)))

    def cover(self, tile: tuple[int, int], reach: float) -> tuple[tuple[int, float], ...]:
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

    def _guess(self, world: World, roster: list[MonsterKind]) -> View:
        """Every monster of the roster walks the whole path at its pace and waits a while at every arch."""
        walkers = [k for k in roster if not k.flying]
        seconds = [sum(1.0 / k.speed for k in roster) / len(roster)] * self.bins
        near = [1.5] * self.bins
        around = [3.0] * self.bins
        if world.location.arsenal.gates and walkers:
            for b in self.queue_bins:
                seconds[b] += QUEUE_GUESS * len(walkers) / len(roster)
                near[b] = 4.0
                around[b] = 5.0
        heft = sum(k.hp for k in roster)
        taken = {e: [sum(k.hp * _taken(k, e) for k in roster) / heft] * self.bins for e in ELEMENTS}
        return View(seconds, near, around, taken)
