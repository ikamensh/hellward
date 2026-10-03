"""The planned player: a person who has replayed each location many times and knows its build by heart.

Its build for a location is a :class:`Plan`, found offline by ``tools/plan_player.py`` (which
plays whole defences on the training seeds 0-99 and keeps what held best) and stored as JSON in ``plans/``: the
skills to learn first, which towers to raise on which tiles and in what order, when to ward the arches and which
towers to raise in rank, and how full the mana orb should be before each wave is called. The player follows it
step by step as the gold comes in.

The spells it casts as it sees the fight, since no plan knows where a leader will chant or a queue will stand:
Smite on a chanting leader it kills when the chant is aimed at a tower worth saving, Frozen Orb on a gate about to
break, Meteor on a crowd, Smite on a monster about to reach the sanctuary, and Battle Hymn on the dearest tower
that has work to do while a Smite stays in hand. How much a spell must be worth before it is cast is part of the
plan, found by the same search.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from hellward.sim.campaign import ORDER, Location
from hellward.sim.content import CURSES, SELL_REFUND, SPELLS, TOWERS, Curse, Element, felt_hit
from hellward.sim.model import DOOR, DOOR_STOP, JOSTLE, Monster, Tower, World
from hellward.sim.players.hands import AIM_GAP, Hands, REACT, attune_spare, ready
from hellward.sim.players.tree import adjust as read_plan
from hellward.sim.players.tree import chartered, extras, learn_ordered, missing_unlocks, read, unswap
from hellward.sim.skills import UNLOCK, unlock_skills

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
    """One location's build. Tiles are tuples here and lists in the JSON."""

    skills: list[str]          # learned in this order while the sigils last (a skill waits for the one above it)
    steps: list[tuple]         # ("build", kind, tile), ("rank", tile) or ("gate", door index), done in order
    calls: list[float]         # per wave: the mana the orb should hold before the wave is called
    rebuild: str = "now"       # a broken gate is warded again "now", in the "break" after its wave, or "never"
    smite_worth: float = 40.0      # the least a chant must threaten (gold in the tower times its loss) to smite it
    meteor_worth: float = 3.0      # the least life a meteor must strike, in its own damage
    orb_worth: float = 3.0         # the same, for a Frozen Orb on a crowd
    reserve: float = 30.0          # mana kept for a Smite while a leader walks
    trained: dict = field(default_factory=dict)   # how the search found it, for the record
    map: str = ""                # the fingerprint of the map, waves and prices it was searched on

    def to_json(self) -> dict:
        data = asdict(self)
        data["steps"] = [list(step) for step in self.steps]
        return data

    @classmethod
    def from_json(cls, data: dict) -> Plan:
        data = dict(data)
        data["steps"] = [_step(step) for step in data["steps"]]
        return cls(**data)

    def learn(self, sigils: int, stage: int) -> frozenset[str]:
        """The skills of the plan's list that fit in ``sigils``, each as soon as the one above it is learned."""
        return learn_ordered(self.skills, sigils, stage)


def _step(step: list) -> tuple:
    if step[0] == "build":
        return "build", step[1], tuple(step[2])
    if step[0] == "rank":
        return "rank", tuple(step[1])
    return "gate", step[1]


def plan_path(location: str) -> Path:
    return PLANS / f"{location}.json"


def load(location: str) -> Plan:
    return Plan.from_json(json.loads(plan_path(location).read_text()))


def fingerprint(location: Location, unlocks: frozenset[str]) -> str:
    """The map, waves, prices and unlock set a plan was searched on: a stored plan for a location that has
    changed since is not played."""
    prices = tuple((kind, tuple(level.cost for level in TOWERS[kind].levels)) for kind in sorted(TOWERS))
    level, arsenal = location.level, location.arsenal
    text = repr((level.width, level.height, level.waypoints, level.extra_routes, level.doors,
                 sorted(level.walkable_tiles), sorted(level.obstacles), sorted(level.pools),
                 sorted(level.boulders), arsenal.towers, arsenal.gates, arsenal.spells,
                 location.waves, location.start_gold, prices, DOOR.cost, sorted(unlocks)))
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def needs(plan: Plan, relics: tuple[str, ...] = ()) -> frozenset[str]:
    """The unlock skills the plan's steps need: their tower kinds', but never a chartered kind's."""
    free = chartered(relics)
    return frozenset(u for step in plan.steps if step[0] == "build" and step[1] not in free
                     for u in [UNLOCK[step[1]]] if u is not None)


def adjust_plan(plan: Plan, relics: tuple[str, ...], location: Location, sigils: int, stage: int) -> Plan:
    """The stored plan read for its relics: the tree's engines seeded, its unlocks learned, the payoffs'
    extra towers and ranks appended. An engine the sigils cannot fund is unswapped again, so the plan always
    raises; with no relics it stands exactly as searched."""
    if not relics:
        return plan
    builds = [(step[1], step[2]) for step in plan.steps if step[0] == "build"]
    skills, seeded, swaps = read_plan(plan.skills, builds, relics, location)
    learned = learn_ordered(skills, sigils, stage)
    missing = missing_unlocks(seeded, learned, relics)
    while missing:
        unlock = sorted(missing)[0]
        skills, seeded, swaps, changed = unswap(skills, seeded, swaps, unlock)
        if not changed:
            raise ValueError(f"the {location.key} plan needs {sorted(missing)} to raise its steps")
        learned = learn_ordered(skills, sigils, stage)
        missing = missing_unlocks(seeded, learned, relics)
    extra, ranks = extras(seeded, builds, read(relics), location)
    by_tile = {tile: kind for kind, tile in seeded}
    steps = [(("build", by_tile[step[2]], step[2]) if step[0] == "build" else step)
             for step in plan.steps]
    steps += [("build", kind, tile) for kind, tile in extra]
    steps += [("rank", tile) for tile in ranks]
    return replace(plan, skills=skills, steps=steps)


def check(location: Location, learned: frozenset[str] | None = None) -> Plan:
    """The stored plan for a location, refused when it is missing, was searched on something else, or needs
    unlocks the learned skills lack: a plan is played only where a Kit holds its unlock set."""
    path = plan_path(location.key)
    if not path.exists():
        raise ValueError(f"no plan searched for {location.key} yet")
    plan = Plan.from_json(json.loads(path.read_text()))
    if plan.map != fingerprint(location, unlock_skills(plan.skills)):
        raise ValueError(f"the {location.key} plan was searched on another map, waves, prices or unlocks")
    if learned is not None:
        missing = needs(plan) - unlock_skills(learned)
        if missing:
            raise ValueError(f"the {location.key} plan needs {sorted(missing)} to raise its steps")
    return plan


@dataclass
class Planned:
    name: str = "planned"
    reaction: tuple[float, float] = REACT
    aim_gap: float = AIM_GAP
    plan: Plan | None = None   # given, or loaded for the location when the defence begins
    stored: Plan | None = None   # the searched plan, never adjusted: every read starts from it
    next: int = 0              # the plan's next step
    gates: set[int] = field(default_factory=set)   # arches the plan has warded, to ward again when broken
    relocated: set[tuple[int, int]] = field(default_factory=set)   # planned towers sold to follow the final boss
    skipped: set[tuple[int, int]] = field(default_factory=set)   # planned towers never built: their cell was taken
    clock: float = 0.0
    look: float = 0.0
    last_aim: float = -1e9

    def draft(self, location: Location, sigils: int, relics: tuple[str, ...] = ()) -> frozenset[str]:
        if self.stored is None:
            self.stored = self.plan if self.plan is not None else check(location)
        self.plan = adjust_plan(self.stored, relics, location, sigils, ORDER.index(location.key))
        learned = self.plan.learn(sigils, ORDER.index(location.key))
        missing = needs(self.plan, relics) - unlock_skills(learned)
        if missing:
            raise ValueError(f"the {location.key} plan needs {sorted(missing)} to raise its steps")
        return learned

    def act(self, hands: Hands) -> None:
        world = hands.world
        if self.plan is None:
            self.plan = check(world.location)
            kinds = {step[1] for step in self.plan.steps if step[0] == "build"}
            kinds -= chartered(world.relics)
            if kinds & world.perks.locked:
                raise ValueError(f"the {world.location.key} plan's steps are locked in this defence")
        self._answer(hands)
        if world.time >= self.look:
            self.look = world.time + LOOK
            self._hymn(hands)
            self._strike(hands)
        if world.time >= self.clock:
            self.clock = world.time + THINK
            self._build(world)
            self._call(world)

    # -- The build -----------------------------------------------------------------------------------

    def _build(self, world: World) -> None:
        assert self.plan is not None
        plan = self.plan
        if self._follow_boss(world):
            return
        if plan.rebuild == "now" or (plan.rebuild == "break" and world.break_left is not None):
            for index in sorted(self.gates):
                door = world.doors[index]
                if not door.built and not door.rubble and world.gold >= world.door_cost and _arch_clear(world, index):
                    world.build_door(index)
        steps = plan.steps
        while self.next < len(steps):
            step = steps[self.next]
            if step[0] == "build":
                if world.tower_at(step[2]) is None:
                    if step[2] in world.blighted:   # taken ground: the step is skipped, never waited on
                        self.skipped.add(step[2])
                        self.next += 1
                        continue
                    if world.gold < world.cost(step[1]):
                        return
                    world.build(step[1], step[2])
            elif step[0] == "rank":
                tower = world.tower_at(step[1])
                if tower is None:
                    assert step[1] in self.relocated or step[1] in self.skipped
                    self.next += 1
                    continue
                price = world.upgrade_cost(tower)
                if price is not None:
                    if world.rank_needs(tower) is not None:
                        self.next += 1
                        continue
                    if world.gold < price:
                        return
                    world.upgrade(tower.id)
            else:
                door = world.doors[step[1]]
                if not door.built and not door.rubble:   # a rubbled arch waits for the wave's end
                    if world.gold < world.door_cost or not _arch_clear(world, step[1]):
                        return
                    world.build_door(step[1])
                self.gates.add(step[1])
            self.next += 1
        self._spare(world)

    def _follow_boss(self, world: World) -> bool:
        """In the last stretch, move spent towers ahead of a boss that would cost many lives to leak."""
        if world.wave != len(world.waves) - 1 or world.schedule or not world.monsters:
            return False
        boss = max((m for m in world.monsters if m.kind.boss), key=lambda m: m.hp, default=None)
        if boss is None:
            return False
        route = world.level.route(boss.route)
        reach = world.tower_levels["arrow"][0].range
        best: tuple[int, int] | None = None
        most = 0.0
        for y in range(world.level.height):
            for x in range(world.level.width):
                tile = x, y
                if (not world.level.buildable(x, y) or world.tower_at(tile) is not None
                        or tile in world.blighted):
                    continue
                covered = 0.0
                for start, end in route.coverage(tile, reach):
                    left = max(start, boss.s)
                    if end > left:
                        covered += (end - left) / (1.0 + max(0.0, start - boss.s) / 4.0)
                if covered > most:
                    best, most = tile, covered
        if best is None:
            return True
        price = world.cost("arrow")
        if world.gold >= price:
            world.build("arrow", best)
            return True
        spent = [t for t in world.towers.values() if not t.curses and world.gold + int(t.spent * SELL_REFUND) >= price
                 and all(all(end <= m.s for _, end in world.level.route(m.route).coverage(t.tile, t.stats.range))
                         for m in world.monsters)]
        if spent:
            tower = max(spent, key=lambda t: (int(t.spent * SELL_REFUND), -t.id))
            world.sell(tower.id)
            self.relocated.add(tower.tile)
        return True

    def _spare(self, world: World) -> None:
        """Gold the plan did not foresee (it is all done): ranks for the towers, the lowest first, then
        attunement for the highest-ranked striker."""
        self._ranks(world)
        while attune_spare(world):
            pass

    def _ranks(self, world: World) -> None:
        while True:
            ranked = [t for t in world.towers.values()
                      if world.upgrade_cost(t) is not None and world.rank_needs(t) is None]
            if not ranked:
                return
            tower = min(ranked, key=lambda t: (t.level, -t.spent, t.id))
            cost = world.upgrade_cost(tower)
            if cost is None or world.gold < cost:
                return
            world.upgrade(tower.id)

    def _call(self, world: World) -> None:
        assert self.plan is not None
        if world.break_left is None or not world.can_call_wave:
            return
        want = self.plan.calls[world.wave + 1]
        if world.mana >= min(want, world.mana_max) - 1e-6:
            world.call_wave()

    # -- Spells ----------------------------------------------------------------------------------------

    def _aim_ready(self, world: World) -> bool:
        return world.time - self.last_aim >= self.aim_gap - 1e-9

    def _can(self, world: World, spell: str, spare: float = 0.0) -> bool:
        return ready(world, spell, spare)

    def _answer(self, hands: Hands) -> None:
        """A chant seen at a tower worth saving: smite its leader if one Smite kills it, and the curse dies with it."""
        assert self.plan is not None
        world = hands.world
        if not self._aim_ready(world) or not self._can(world, "smite"):
            return
        blow = _smite_damage(world)
        best, best_loss = None, 0.0
        for sign in hands.threats():
            leader = world.monster(sign.leader)
            if sign.kind != "chant" or leader is None or sign.curse is None:
                continue
            if leader.hp > felt_hit(blow, None, leader.kind):
                continue
            loss = sum(curse_loss(world, t, sign.curse) for t in world.caught(sign.spot, sign.radius))
            if loss > best_loss:
                best, best_loss = leader, loss
        if best is None or best_loss < self.plan.smite_worth:
            return
        hands.smite(best.id)
        self.last_aim = world.time

    def _hymn(self, hands: Hands) -> None:
        """The dearest tower with monsters about it, while a Smite stays in hand for a leader."""
        assert self.plan is not None
        world = hands.world
        keep = self.plan.reserve if "smite" in world.arsenal.spells and world.leaders() else 0.0
        if not self._can(world, "hymn", keep):
            return
        busy = [t for t in world.towers.values()
                if t.kind.attack not in ("aura", "amplify") and not t.silenced and _busy(world, t)]
        if busy:
            hands.hymn(max(busy, key=lambda t: (t.spent, -t.id)).id)

    def _strike(self, hands: Hands) -> None:
        """Meteor, Frozen Orb and Smite as weapons: a gate about to break, a leak, a crowd, or a full orb."""
        assert self.plan is not None
        world = hands.world
        if not world.monsters or not self._aim_ready(world):
            return
        plan = self.plan
        spare = plan.reserve if "smite" in world.arsenal.spells and world.leaders() else 0.0
        full = world.mana >= world.mana_max - 2.0
        if self._can(world, "orb", spare) and self._save_gate(hands):
            return
        if self._can(world, "smite") and self._stop_leak(hands):
            return
        if self._can(world, "smite"):
            boss = max((m for m in world.monsters if m.kind.boss), key=lambda m: m.hp, default=None)
            if boss is not None:
                hands.smite(boss.id)
                self.last_aim = world.time
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
                x, y = world.position(batterers[0])
                hands.orb(x, y)
                self.last_aim = world.time
                return True
        return False

    def _stop_leak(self, hands: Hands) -> bool:
        """A walker about to reach the sanctuary that a Smite would kill: the lives it would take are saved."""
        world = hands.world
        smite = _smite_damage(world)
        leaking = [m for m in world.monsters
                   if m.hp <= smite and world.remaining(m) <= LEAK_SOON * max(m.kind.speed, 0.3)]
        if not leaking:
            return False
        target = max(leaking, key=lambda m: (m.kind.lives, -world.remaining(m)))
        hands.smite(target.id)
        self.last_aim = world.time
        return True


# -- A person's reckoning --------------------------------------------------------------------------


def curse_loss(world: World, tower: Tower | None, curse: Curse) -> float:
    """What a curse landing on a tower would cost, in the gold of the tower's work it takes away."""
    if tower is None:
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
    for m in world.monsters:
        spans = world.level.route(m.route).coverage(tower.tile, tower.stats.range + 1.5)
        if any(a <= m.s <= b for a, b in spans):
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
        for index, crossing in world.level.crossings(m.route):
            if world.doors[index].built and crossing > m.s:
                s = min(s, max(m.s, crossing - DOOR_STOP - JOSTLE / 2))
                break
    return s


def _positions(world: World, t: float) -> list[tuple[Monster, float, float]]:
    return [(m, *world.level.route(m.route).point(_ahead(world, m, t))) for m in world.monsters]


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
            value += min(m.hp, felt_hit(dmg, Element.FIRE, m.kind) + (burn * world.taken(m, Element.FIRE)
                                                                       if m.door >= 0 else 0.0))
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
    return sum(min(m.hp, felt_hit(dmg, Element.COLD, m.kind) * 1.5) for m in _struck(now, cx, cy, spec.radius ** 2))


def _smite_damage(world: World) -> float:
    return SPELLS["smite"].damage * world.power()


def _arch_clear(world: World, index: int) -> bool:
    x, y = world.level.doors[index]
    cx, cy = x + 0.5, y + 0.5
    return not any(not m.kind.flying and (world.position(m)[0] - cx) ** 2
                   + (world.position(m)[1] - cy) ** 2 < ARCH_CLEAR ** 2 for m in world.monsters)
