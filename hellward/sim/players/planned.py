"""The planned player: a person who has replayed each location many times and knows its build by heart.

Its build for a location and difficulty is a :class:`Plan`, found offline by ``tools/plan_player.py`` (which
plays whole defences on the training seeds 0-99 and keeps what held best) and stored as JSON in ``plans/``: the
skills to learn first, which towers to raise on which tiles and in what order, when to ward the arches and which
towers to raise in rank, and how full the mana orb should be before each wave is called. The player follows it
step by step as the gold comes in. A difficulty with no plan of its own is played with the location's Normal
plan.

The spells it casts as it sees the fight, since no plan knows where a leader will chant or a queue will stand:
Smite on a chant aimed at a tower worth saving (Frozen Orb when the chanting leader stands in a crowd), Frozen
Orb on a gate about to break, Meteor on a crowd, Smite on a monster about to reach the sanctuary, and Cleanse on
the dearest cursed tower that has work to do. How much a spell must be worth before it is cast is part of the
plan, found by the same search.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

from hellward.sim.campaign import Difficulty, Location
from hellward.sim.content import CURSES, DOOR, SPELLS, Curse, Element
from hellward.sim.model import DOOR_STOP, JOSTLE, Monster, Tower, World
from hellward.sim.players.hands import AIM_GAP, Hands
from hellward.sim.skills import can_learn

PLANS = Path(__file__).parent / "plans"
THINK = 0.25          # seconds between two looks at the build and the next wave
LOOK = 0.2            # seconds between two looks for a spell worth casting
ARCH_CLEAR = 0.6      # a gate cannot be warded while a walker stands this close to its arch
LEAK_SOON = 2.0       # seconds from the sanctuary at which a walker is about to take lives

# The share of a tower's work a curse takes away while it lasts, as a person would reckon it: Bone Prison
# silences wholly but for half as long, and a Weakened frost shrine still chills.
LOSS = {Curse.WEAKEN: 0.65, Curse.DECREPIFY: 0.6, Curse.DIM_VISION: 0.45, Curse.BONE_PRISON: 0.56}
FROST_WEAKENED = 0.2


@dataclass
class Plan:
    """One location's build on one difficulty. Tiles are tuples here and lists in the JSON."""

    skills: list[str]          # learned in this order while the sigils last (a skill waits for the one above it)
    steps: list[tuple]         # ("build", kind, tile), ("rank", tile) or ("gate", door index), done in order
    calls: list[float]         # per wave: the mana the orb should hold before the wave is called
    rebuild: str = "now"       # a broken gate is warded again "now", in the "break" after its wave, or "never"
    smite_worth: float = 40.0      # the least a chant must threaten (gold in the tower times its loss) to smite it
    cleanse_worth: float = 60.0    # the same, for burning the curses off a tower
    meteor_worth: float = 3.0      # the least life a meteor must strike, in its own damage
    orb_worth: float = 3.0         # the same, for a Frozen Orb on a crowd
    reserve: float = 30.0          # mana kept for a Smite while a leader walks
    trained: dict = field(default_factory=dict)   # how the search found it, for the record

    def to_json(self) -> dict:
        data = {f.name: getattr(self, f.name) for f in fields(self)}
        data["steps"] = [list(step) for step in self.steps]
        return data

    @classmethod
    def from_json(cls, data: dict) -> Plan:
        data = dict(data)
        data["steps"] = [_step(step) for step in data["steps"]]
        return cls(**data)

    def learn(self, sigils: int) -> frozenset[str]:
        """The skills of the plan's list that fit in ``sigils``, each as soon as the one above it is learned."""
        learned: frozenset[str] = frozenset()
        grew = True
        while grew:
            grew = False
            for key in self.skills:
                if can_learn(learned, key, sigils):
                    learned, grew = learned | {key}, True
        return learned


def _step(step: list) -> tuple:
    if step[0] == "build":
        return "build", step[1], tuple(step[2])
    if step[0] == "rank":
        return "rank", tuple(step[1])
    return "gate", step[1]


def plan_path(location: str, difficulty: str) -> Path:
    return PLANS / f"{location}-{difficulty}.json"


def load(location: str, difficulty: str) -> Plan:
    path = plan_path(location, difficulty)
    if not path.exists():
        path = plan_path(location, "normal")
    return Plan.from_json(json.loads(path.read_text()))


@dataclass
class Planned:
    name: str = "planned"
    plan: Plan | None = None   # given, or loaded for the location when the defence begins
    next: int = 0              # the plan's next step
    gates: set[int] = field(default_factory=set)   # arches the plan has warded, to ward again when broken
    clock: float = 0.0
    look: float = 0.0
    last_aim: float = -1e9

    def skills(self, location: Location, difficulty: Difficulty, sigils: int) -> frozenset[str]:
        if self.plan is None:
            self.plan = load(location.key, difficulty.key)
        return self.plan.learn(sigils)

    def act(self, hands: Hands) -> None:
        world = hands.world
        if self.plan is None:
            self.plan = load(world.location.key, world.difficulty.key)
        self._answer(hands)
        if world.time >= self.look:
            self.look = world.time + LOOK
            self._cleanse(hands)
            self._strike(hands)
        if world.time >= self.clock:
            self.clock = world.time + THINK
            self._build(world)
            self._call(world)

    # -- The build -----------------------------------------------------------------------------------

    def _build(self, world: World) -> None:
        plan = self.plan
        if plan.rebuild == "now" or (plan.rebuild == "break" and world.break_left is not None):
            for index in sorted(self.gates):
                door = world.doors[index]
                if not door.built and world.gold >= DOOR.cost and _arch_clear(world, index):
                    world.build_door(index)
        steps = plan.steps
        while self.next < len(steps):
            step = steps[self.next]
            if step[0] == "build":
                if world.tower_at(step[2]) is None:
                    if world.gold < world.cost(step[1]):
                        return
                    world.build(step[1], step[2])
            elif step[0] == "rank":
                tower = world.tower_at(step[1])
                price = world.upgrade_cost(tower) if tower is not None else None
                if price is not None:
                    if world.gold < price:
                        return
                    world.upgrade(tower.id)
            else:
                door = world.doors[step[1]]
                if not door.built:
                    if world.gold < DOOR.cost or not _arch_clear(world, step[1]):
                        return
                    world.build_door(step[1])
                self.gates.add(step[1])
            self.next += 1
        self._spare(world)

    def _spare(self, world: World) -> None:
        """Gold the plan did not foresee (it is all done): ranks for the towers, the lowest first."""
        while True:
            ranked = [t for t in world.towers.values() if world.upgrade_cost(t) is not None]
            if not ranked:
                return
            tower = min(ranked, key=lambda t: (t.level, -t.spent, t.id))
            if world.gold < world.upgrade_cost(tower):
                return
            world.upgrade(tower.id)

    def _call(self, world: World) -> None:
        if world.break_left is None or not world.can_call_wave:
            return
        want = self.plan.calls[world.wave + 1]
        if world.mana >= min(want, world.mana_max) - 1e-6:
            world.call_wave()

    # -- Spells ----------------------------------------------------------------------------------------

    def _aim_ready(self, world: World) -> bool:
        return world.time - self.last_aim >= AIM_GAP - 1e-9

    def _can(self, world: World, spell: str, spare: float = 0.0) -> bool:
        return spell in world.location.arsenal.spells and world.mana - spare >= world.spell_cost(spell)

    def _answer(self, hands: Hands) -> None:
        """A chant seen: smite its leader when the tower it aims at is worth it, or freeze it with its crowd."""
        world = hands.world
        if not self._aim_ready(world) or not self._can(world, "smite"):
            return
        best, best_loss = None, 0.0
        for sign in hands.threats():
            if sign.kind != "chant" or world.monster(sign.leader) is None:
                continue
            loss = curse_loss(world, world.towers.get(sign.tower), sign.curse)
            if loss > best_loss:
                best, best_loss = sign, loss
        if best is None or best_loss < self.plan.smite_worth:
            return
        leader = world.monster(best.leader)
        if self._can(world, "orb"):
            x, y = world.level.point(leader.s)
            crowd = _orb_value(world, x, y, _positions(world, 0.0))
            if crowd >= self.plan.orb_worth * _orb_damage(world) * 0.5:
                hands.orb(x, y)
                self.last_aim = world.time
                return
        hands.smite(leader.id)
        self.last_aim = world.time

    def _cleanse(self, hands: Hands) -> None:
        world = hands.world
        if not self._can(world, "cleanse"):
            return
        best, best_loss = None, 0.0
        for t in world.towers.values():
            if not t.curses or not _busy(world, t):
                continue
            loss = sum(t.spent * _share(t, c) * left / CURSES[c].duration for c, left in t.curses.items())
            if loss > best_loss:
                best, best_loss = t, loss
        if best is not None and best_loss >= self.plan.cleanse_worth:
            hands.cleanse(best.id)

    def _strike(self, hands: Hands) -> None:
        """Meteor, Frozen Orb and Smite as weapons: a gate about to break, a leak, a crowd, or a full orb."""
        world = hands.world
        if not world.monsters or not self._aim_ready(world):
            return
        plan = self.plan
        spare = plan.reserve if "smite" in world.location.arsenal.spells and world.leaders() else 0.0
        full = world.mana >= world.mana_max - 2.0
        if self._can(world, "orb", spare) and self._save_gate(hands):
            return
        if self._can(world, "smite") and self._stop_leak(hands):
            return
        if self._can(world, "meteor", spare):
            x, y, value = _best_meteor(world)
            if value >= (1.5 if full else plan.meteor_worth) * SPELLS["meteor"].damage * world.power():
                hands.meteor(x, y)
                self.last_aim = world.time
                return
        if self._can(world, "orb", spare):
            x, y, value = _best_orb(world)
            if value >= (1.5 if full else plan.orb_worth) * _orb_damage(world):
                hands.orb(x, y)
                self.last_aim = world.time
                return
        if full and self._can(world, "smite"):
            leaders = world.leaders()
            target = min(leaders, key=lambda m: m.hp) if leaders else world.monsters[0]
            hands.smite(target.id)
            self.last_aim = world.time

    def _save_gate(self, hands: Hands) -> bool:
        """A standing gate that its queue will break within two seconds: freeze the queue."""
        world = hands.world
        for door in world.doors:
            if not door.built:
                continue
            batterers = [m for m in world.monsters if m.door == door.index]
            if len(batterers) < 3:
                continue
            blows = sum(m.kind.door_dps * (1.0 - m.chill if m.chill_left > 0 else 1.0) for m in batterers)
            if door.hp < blows * 2.0:
                x, y = world.level.point(door.s - DOOR_STOP - JOSTLE / 2)
                hands.orb(x, y)
                self.last_aim = world.time
                return True
        return False

    def _stop_leak(self, hands: Hands) -> bool:
        """A walker about to reach the sanctuary that a Smite would kill: the lives it would take are saved."""
        world = hands.world
        end = world.level.length
        smite = _smite_damage(world)
        leaking = [m for m in world.monsters
                   if m.hp <= smite and end - m.s <= LEAK_SOON * max(m.kind.speed, 0.3)]
        if not leaking:
            return False
        target = max(leaking, key=lambda m: (m.kind.lives, m.s))
        hands.smite(target.id)
        self.last_aim = world.time
        return True


# -- A person's reckoning --------------------------------------------------------------------------


def curse_loss(world: World, tower: Tower | None, curse: Curse) -> float:
    """What a curse landing on a tower would cost, in the gold of the tower's work it takes away."""
    if tower is None or tower.ward > 0:
        return 0.0
    fresh = 1.0 - tower.curses.get(curse, 0.0) / CURSES[curse].duration
    busy = 1.0 if _busy(world, tower) else 0.4
    return tower.spent * _share(tower, curse) * fresh * busy


def _share(tower: Tower, curse: Curse) -> float:
    if curse is Curse.WEAKEN and tower.kind.key == "frost":
        return FROST_WEAKENED
    return LOSS[curse]


def _busy(world: World, tower: Tower) -> bool:
    """Whether monsters walk in the tower's reach or a step outside it."""
    spans = world.level.coverage(tower.tile, tower.stats.range + 1.5)
    for m in world.monsters:
        for a, b in spans:
            if a <= m.s <= b:
                return True
    return False


def _ahead(world: World, m: Monster, t: float) -> float:
    """Where a monster will stand ``t`` seconds from now at its present pace, queueing at a standing gate."""
    if m.door >= 0:
        return m.s
    moving = t - m.frozen if m.frozen > 0 else t
    if moving <= 0:
        return m.s
    speed = m.kind.speed * (1.0 - m.chill) if m.chill_left > 0 else m.kind.speed
    s = m.s + speed * moving
    if not m.kind.flying:
        for d in world.doors:
            if d.built and d.s > m.s:
                s = min(s, max(m.s, d.s - DOOR_STOP - JOSTLE / 2))
                break
    return s


def _positions(world: World, t: float) -> list[tuple[Monster, float, float]]:
    point = world.level.point
    return [(m, *point(_ahead(world, m, t))) for m in world.monsters]


def _struck(near: list[tuple[Monster, float, float]], cx: float, cy: float, r2: float) -> list[Monster]:
    return [m for m, x, y in near if (x - cx) ** 2 + (y - cy) ** 2 <= r2]


def _best_meteor(world: World) -> tuple[float, float, float]:
    """The point where a meteor cast now strikes the most life when it lands, and that life."""
    spec = SPELLS["meteor"]
    power = world.power()
    dmg, burn = spec.damage * power, spec.burn * power * spec.lasting
    r2 = spec.radius * spec.radius
    ahead = _positions(world, spec.delay)
    best = (0.0, 0.0, 0.0)
    for _, cx, cy in ahead:
        value = 0.0
        for m in _struck(ahead, cx, cy, r2):
            taken = world.taken(m, Element.FIRE)
            value += min(m.hp, (dmg + (burn if m.door >= 0 else 0.0)) * taken)
        if value > best[2]:
            best = (cx, cy, value)
    return best


def _orb_damage(world: World) -> float:
    return SPELLS["orb"].damage * world.power()


def _best_orb(world: World) -> tuple[float, float, float]:
    """The point where a Frozen Orb strikes the most life, and that life."""
    now = _positions(world, 0.0)
    best = (0.0, 0.0, 0.0)
    for _, cx, cy in now:
        value = _orb_value(world, cx, cy, now)
        if value > best[2]:
            best = (cx, cy, value)
    return best


def _orb_value(world: World, cx: float, cy: float, now: list[tuple[Monster, float, float]]) -> float:
    """The life a Frozen Orb at a point strikes, and half again for the time its frozen monsters stand still."""
    spec = SPELLS["orb"]
    dmg = spec.damage * world.power()
    return sum(min(m.hp, dmg * world.taken(m, Element.COLD) * 1.5) for m in _struck(now, cx, cy, spec.radius ** 2))


def _smite_damage(world: World) -> float:
    return SPELLS["smite"].damage * world.power()


def _arch_clear(world: World, index: int) -> bool:
    s = world.doors[index].s
    return not any(not m.kind.flying and abs(m.s - s) < ARCH_CLEAR for m in world.monsters)
