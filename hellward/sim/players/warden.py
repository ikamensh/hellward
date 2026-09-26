"""The warden: a veteran's defence, played the way a person who has held each location many times plays it.

It reads the location's intro first: which monsters come, what they resist, which of them fly, and what the
location offers. From that it learns its skills and drafts a build: gates in every arch, fire and frost on the
queues behind them, lightning where the flyers pass and venom for the biggest walkers, each element weighed by
how much of the host's life it can hurt. A location it has replayed has its build and skills as data
(``plans/warden.json``, searched by ``tools/warden_plans.py`` on training seeds); elsewhere the draft is the build.

The build is a list of steps (a gate, a tower, a rank) taken in order as the gold comes. A gate that breaks is
set again as soon as the arch is clear. With the list done, the gold goes to the tower that has had the most
to shoot at.

In the fight it watches the leaders: a chant against a tower that matters is smitten, or frozen with the crowd
around it; a curse that lands on a busy tower is cleansed; a gate about to break under a crowd gets a Frozen
Orb; a dense queue gets a Meteor; a monster about to reach the sanctuary with little life left is smitten, and
one worth many lives there (Azazel) draws every Smite a chant can spare. Mana is never left to sit at the top
of the orb: a full orb goes on a lesser crowd or the monster a Smite hurts most.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from hellward.sim.campaign import Location
from hellward.sim.content import CURSES, DOOR, MONSTERS, SPELLS, TOWERS, WAVE_BREAK, Curse, Element
from hellward.sim.model import DOOR_STOP, JOSTLE, Monster, Tower, World
from hellward.sim.players.hands import AIM_GAP, Hands, ready
from hellward.sim.skills import SKILLS, can_learn, perks, tower_levels

PLANS = Path(__file__).parent / "plans" / "warden.json"
THINK = 0.25          # seconds between two looks at the gold
ARRIVING = 3.0        # tiles of path before a tower's reach whose monsters count as its work to come
SEVERITY = {Curse.WEAKEN: 0.65, Curse.DECREPIFY: 0.6, Curse.DIM_VISION: 0.5, Curse.BONE_PRISON: 1.0}
CLEANSE_BAR = 500.0   # damage a cleanse must win back with the orb empty (nothing when it is full)
METEOR_BITE = 3.0     # a Meteor must take this many of its blows' worth of life
ORB_CROWD = 400.0     # life (at a wave's life of one) an orb on a chanting leader must also catch
GATE_CROWD = 600.0    # life a queue must hold for an orb to keep its breaking gate standing
LEAK_SMITE = 2.5      # seconds from the sanctuary a monster one Smite kills is smitten
BOSS = 5              # lives a monster costs at the sanctuary for every spare Smite to go to it (Azazel)
FULL = 8.0            # mana short of the orb's top at which it is spent on lesser targets rather than wasted
FULL_BITE = 1.5       # the Meteor's bar then
QUEUE_FALLOFF = 0.5   # each arch further along the path counts this much less: the first queue fights most


# -- The build as data ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    what: str                          # "gate", "build" or "up"
    kind: str = ""                     # a build's tower kind
    tile: tuple[int, int] = (-1, -1)   # a build's or a rank's tile
    door: int = -1                     # a gate's arch

    def row(self) -> list:
        if self.what == "gate":
            return ["gate", self.door]
        if self.what == "build":
            return ["build", self.kind, *self.tile]
        return ["up", *self.tile]

    @staticmethod
    def of(row: list) -> Step:
        if row[0] == "gate":
            return Step("gate", door=row[1])
        if row[0] == "build":
            return Step("build", row[1], (row[2], row[3]))
        return Step("up", tile=(row[1], row[2]))


@dataclass(frozen=True)
class Plan:
    skills: frozenset[str]
    steps: tuple[Step, ...]
    early: float = 0.9     # call the next wave early once the mana orb is this full (a share of its top)
    map: str = ""          # the fingerprint of the map it was searched on

    def row(self) -> dict:
        return {"map": self.map, "skills": sorted(self.skills), "early": self.early, "steps": [s.row() for s in self.steps]}

    @staticmethod
    def of(row: dict) -> Plan:
        return Plan(frozenset(row["skills"]), tuple(Step.of(r) for r in row["steps"]), row["early"], row["map"])


def plan_key(location: Location, sigils: int) -> str:
    return f"{location.key}/{sigils}"


def fingerprint(location: Location) -> str:
    """The map and arsenal a plan was searched on: a stored plan for a map that has changed since is not played."""
    level, arsenal = location.level, location.arsenal
    text = repr((level.width, level.height, level.waypoints, level.doors, sorted(level.obstacles), sorted(level.pools),
                 arsenal.towers, arsenal.gates, arsenal.spells))
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def load_plans() -> dict[str, Plan]:
    if not PLANS.exists():
        return {}
    return {key: Plan.of(row) for key, row in json.loads(PLANS.read_text()).items()}


# -- Reading the intro ----------------------------------------------------------------------------


def host(location: Location) -> dict[str, float]:
    """Each monster kind's share of all the life that comes, as the intro's cards and wave list tell it."""
    life: dict[str, float] = {}
    for wave in location.waves:
        for group in wave.groups:
            life[group.kind] = life.get(group.kind, 0.0) + group.count * MONSTERS[group.kind].hp * wave.hp
    total = sum(life.values())
    return {kind: value / total for kind, value in life.items()}


def worth(location: Location, kind: str) -> float:
    """How much of the host's life a tower kind can hurt, resistances and immunities weighed."""
    element = TOWERS[kind].element
    return sum(share * max(0.0, MONSTERS[key].taken(element)) for key, share in host(location).items())


def flyers(location: Location) -> float:
    return sum(share for key, share in host(location).items() if MONSTERS[key].flying)


def draft_skills(location: Location, sigils: int) -> frozenset[str]:
    """Skills bought in a veteran's order from the columns the location has use for, then the rest of the tree."""
    arsenal = location.arsenal
    wanted: list[str] = []
    if "pyre" in arsenal.towers:
        wanted += ["adept_fire", "fire_ball"]
    if arsenal.gates:
        wanted += ["holy_shield"]
    if "smite" in arsenal.spells:
        wanted += ["warmth"]
    if "storm" in arsenal.towers and flyers(location) > 0.1:
        wanted += ["adept_lightning", "chain_lightning"]
    if "cleanse" in arsenal.spells and arsenal.gates:
        wanted += ["salvation"]
    if "frost" in arsenal.towers:
        wanted += ["adept_cold"]
    if "pyre" in arsenal.towers:
        wanted += ["master_fire", "blaze"]
    if "smite" in arsenal.spells:
        wanted += ["soul_harvest"]
    if arsenal.gates:
        wanted += ["thorns"]
    if "storm" in arsenal.towers:
        wanted += ["adept_lightning", "chain_lightning", "master_lightning", "static_field"]
    if "plague" in arsenal.towers:
        wanted += ["adept_poison", "contagion", "master_poison", "lower_resist"]
    if "frost" in arsenal.towers:
        wanted += ["glacial_spike", "master_cold", "shatter"]
    if len(arsenal.spells) > 2:
        wanted += ["spell_mastery"]
    learned: frozenset[str] = frozenset()
    for key in [*wanted, *SKILLS]:
        if can_learn(learned, key, sigils):
            learned |= {key}
    return learned


def queue_points(location: Location) -> list[float]:
    """Where on the path the queue behind each arch stands."""
    return [s - DOOR_STOP - JOSTLE / 2 for s in location.level.door_s]


def _inside(s: float, spans: tuple[tuple[float, float], ...]) -> bool:
    for a, b in spans:
        if a <= s <= b:
            return True
    return False


def tile_value(location: Location, kind: str, tile: tuple[int, int], reach: float) -> float:
    """A tower's use on a tile: the path it watches, and the queues it watches most of all."""
    spans = location.level.coverage(tile, reach)
    length = sum(b - a for a, b in spans)
    queues = sum(QUEUE_FALLOFF ** i for i, q in enumerate(sorted(queue_points(location))) if _inside(q, spans))
    if kind == "frost":
        return 10.0 * queues + (0.6 if not location.level.doors else 0.2) * length
    if kind == "plague":
        return length + 3.0 * queues
    return length + 6.0 * queues


def draft_build(location: Location, learned: frozenset[str], towers: int = 14) -> tuple[Step, ...]:
    """The build a veteran lays out from the intro: gates, towers on the best tiles by element, then ranks."""
    level = location.level
    p = perks(learned)
    kinds = list(location.arsenal.towers)
    worths = {k: worth(location, k) for k in kinds}
    share = dict(worths)
    if "frost" in share:
        share["frost"] = 0.35 * max(worths.values())
    if "plague" in share:
        share["plague"] *= 0.6
    if "storm" in share:
        share["storm"] *= 0.7 + flyers(location)
    total = sum(share.values())
    tiles = [(x, y) for y in range(level.height) for x in range(level.width) if level.buildable(x, y)]
    chosen: list[tuple[str, tuple[int, int]]] = []
    counts = {k: 0 for k in kinds}
    for _ in range(towers):
        # the kind furthest behind its share of the towers, on its best free tile
        kind = min(kinds, key=lambda k: (counts[k] + 1) / (share[k] / total + 1e-9))
        reach = tower_levels(kind, p)[1].range
        free = [t for t in tiles if t not in {tile for _, tile in chosen}]
        tile = max(free, key=lambda t: (tile_value(location, kind, t, reach), -t[1], -t[0]))
        chosen.append((kind, tile))
        counts[kind] += 1
    order = sorted(range(len(level.doors)), key=lambda i: level.door_s[i])
    gates = [Step("gate", door=i) for i in order] if location.arsenal.gates else []
    steps: list[Step] = gates[:1]
    gates = gates[1:]
    for i, (kind, tile) in enumerate(chosen):
        steps.append(Step("build", kind, tile))
        if i % 2 == 1 and gates:
            steps.append(gates.pop(0))
        if i >= 3:
            steps.append(Step("up", tile=chosen[i - 3][1]))
        if i >= 7:
            steps.append(Step("up", tile=chosen[i - 7][1]))
    steps += gates
    steps += [Step("up", tile=tile) for _, tile in chosen[-3:]]
    return tuple(steps)


# -- The player -----------------------------------------------------------------------------------


@dataclass
class Warden:
    name: str = "warden"
    plans: dict[str, Plan] = field(default_factory=load_plans)
    plan: Plan | None = None                  # a plan to play instead of the stored one (the search's candidates)
    chosen: Plan | None = None                # the plan of this defence, fixed when the skills are learned
    done: int = 0                             # steps of the plan taken
    clock: float = 0.0
    last_aim: float = -1e9
    work: dict[int, float] = field(default_factory=dict)   # per tower: what it has had in reach, summed over time

    def choose(self, location: Location, sigils: int) -> Plan:
        if self.plan is not None:
            return self.plan
        stored = self.plans.get(plan_key(location, sigils))
        if stored is not None and stored.map == fingerprint(location):
            return stored
        learned = draft_skills(location, sigils)
        return Plan(learned, draft_build(location, learned))

    def skills(self, location: Location, sigils: int) -> frozenset[str]:
        self.chosen = self.choose(location, sigils)
        return self.chosen.skills

    def act(self, hands: Hands) -> None:
        world = hands.world
        self._spells(hands)
        if world.time < self.clock:
            return
        self.clock = world.time + THINK
        self._watch(world)
        self._gates(world)
        self._spend(world)
        self._call(world)

    # -- Gold ---------------------------------------------------------------------------------

    def _watch(self, world: World) -> None:
        """What each tower has had to shoot at: the monsters in its reach, as a person watching would count."""
        for t in world.towers.values():
            spans = world.level.coverage(t.tile, t.stats.range)
            element = t.kind.element
            busy = 0.0
            for m in world.monsters:
                if _inside(m.s, spans):
                    busy += max(0.0, m.kind.taken(element))
            self.work[t.id] = self.work.get(t.id, 0.0) + busy * THINK

    def _gates(self, world: World) -> None:
        """Set a broken gate again once no walker stands in its arch, if the build has set it before."""
        steps = self.chosen.steps
        for door in world.doors:
            if door.built or door.rubble or world.gold < DOOR.cost or Step("gate", door=door.index) not in steps[:self.done]:
                continue
            if _clear(world, door.s):
                world.build_door(door.index)

    def _spend(self, world: World) -> None:
        steps = self.chosen.steps
        while self.done < len(steps):
            step = steps[self.done]
            if step.what == "gate":
                door = world.doors[step.door]
                if not door.built and not door.rubble:   # a rubbled arch waits for the wave's end (_gates)
                    if world.gold < DOOR.cost or not _clear(world, door.s):
                        return
                    world.build_door(step.door)
            elif step.what == "build":
                if world.tower_at(step.tile) is None:
                    if world.gold < world.cost(step.kind):
                        return
                    world.build(step.kind, step.tile)
            else:
                tower = world.tower_at(step.tile)
                cost = world.upgrade_cost(tower) if tower is not None else None
                if cost is not None:
                    if world.rank_needs(tower) is not None:
                        self.done += 1
                        continue
                    if world.gold < cost:
                        return
                    world.upgrade(tower.id)
            self.done += 1
        self._more(world)

    def _more(self, world: World) -> None:
        """With the build done: a rank for the tower that has worked hardest, or a new tower on the best tile left."""
        while True:
            ranked = [t for t in world.towers.values()
                      if world.upgrade_cost(t) is not None and world.rank_needs(t) is None]
            if ranked:
                tower = max(ranked, key=lambda t: (self.work.get(t.id, 0.0) / t.spent, -t.id))
                if world.gold < world.upgrade_cost(tower):
                    return
                world.upgrade(tower.id)
                continue
            location = world.location
            kind = max(location.arsenal.towers, key=lambda k: worth(location, k))
            if world.gold < world.cost(kind):
                return
            reach = world.tower_levels[kind][1].range
            free = [(x, y) for y in range(world.level.height) for x in range(world.level.width)
                    if world.level.buildable(x, y) and world.tower_at((x, y)) is None]
            if not free:
                return
            world.build(kind, max(free, key=lambda t: (tile_value(location, kind, t, reach), -t[1], -t[0])))

    def _call(self, world: World) -> None:
        """Call the next wave early for its gold, a second into the break, once the mana orb is full enough."""
        if not world.can_call_wave or world.break_left is None or world.wave < 0:
            return
        if world.break_left > WAVE_BREAK - 1.0:
            return   # the gold of the last clearing is spent first
        if world.mana >= world.mana_max * self.chosen.early:
            world.call_wave()

    # -- Spells -------------------------------------------------------------------------------

    def _spells(self, hands: Hands) -> None:
        world = hands.world
        if not world.monsters:
            return
        spells = world.location.arsenal.spells
        if "cleanse" in spells:
            self._cleanse(hands)
        if world.time - self.last_aim < AIM_GAP - 1e-9:
            return
        if "smite" in spells and self._smite_leaker(hands):
            return
        if ("smite" in spells or "orb" in spells) and self._break_chant(hands):
            return
        if "smite" in spells and self._smite_boss(hands):
            return
        if "orb" in spells and self._hold_gate(hands):
            return
        if "meteor" in spells and self._meteor(hands, METEOR_BITE):
            return
        if world.mana >= world.mana_max - FULL:
            self._spill(hands)

    def _spill(self, hands: Hands) -> None:
        """The orb is full: a Meteor on a lesser crowd, or a Smite on a leader or the monster it hurts most."""
        world = hands.world
        spells = world.location.arsenal.spells
        if "meteor" in spells and self._meteor(hands, FULL_BITE):
            return
        if not ready(world, "smite"):
            return
        damage = SPELLS["smite"].damage * world.power()
        target = max(world.monsters, key=lambda m: (m.kind.leader is not None, min(m.hp, damage), m.s))
        hands.smite(target.id)
        self.last_aim = world.time

    def _cleanse(self, hands: Hands) -> None:
        world = hands.world
        if world.mana < world.spell_cost("cleanse"):
            return
        best, best_value = None, 0.0
        for t in world.towers.values():
            if not t.curses:
                continue
            left = max(t.curses.values())
            if left < 2.0:
                continue
            value = _tower_value(world, t) * left * max(SEVERITY[c] for c in t.curses)
            if value > best_value:
                best, best_value = t, value
        full = world.mana / world.mana_max
        if best is not None and best_value >= CLEANSE_BAR * (1.0 - full) + 20.0:
            hands.cleanse(best.id)

    def _break_chant(self, hands: Hands) -> bool:
        """Smite the leader whose chant would cost the most, or freeze it when other chants or a crowd stand by."""
        world = hands.world
        chanting: list[Monster] = []
        best, best_value, seen = None, 0.0, (0.0, 0.0)
        for sign in hands.threats():
            leader = world.monster(sign.leader)
            if leader is None:
                continue
            chanting.append(leader)
            if sign.kind == "chant":
                tower = world.towers.get(sign.tower)
                if tower is None or tower.ward > 0:
                    continue
                value = _tower_value(world, tower) * CURSES[sign.curse].duration * SEVERITY[sign.curse]
            else:
                value = max((_tower_value(world, t) for t in world.towers.values()), default=0.0) * 4.0
            if value > best_value:
                best, best_value, seen = leader, value, sign.at
        if best is None:
            return False
        if ready(world, "orb"):
            x, y = seen   # where the leader stood when its sign appeared: a person aims where they saw it
            caught = _near(world, x, y, SPELLS["orb"].radius)
            if sum(1 for m in caught if m in chanting) >= 2 or sum(m.hp for m in caught) >= ORB_CROWD * world.power():
                hands.orb(x, y)
                self.last_aim = world.time
                return True
        if ready(world, "smite"):
            hands.smite(best.id)
            self.last_aim = world.time
            return True
        return False

    def _smite_leaker(self, hands: Hands) -> bool:
        """A monster a step or two from the sanctuary that one Smite would kill."""
        world = hands.world
        if not ready(world, "smite"):
            return False
        damage = SPELLS["smite"].damage * world.power()
        end = world.level.length
        for m in world.monsters:   # furthest along first
            if m.s < end - LEAK_SMITE * m.kind.speed:
                break
            if m.hp <= damage:
                hands.smite(m.id)
                self.last_aim = world.time
                return True
        return False

    def _smite_boss(self, hands: Hands) -> bool:
        """A monster that would cost many lives at the sanctuary: every Smite not kept for a chant goes to it."""
        world = hands.world
        if not ready(world, "smite", spare=world.spell_cost("smite")):
            return False
        bosses = [m for m in world.monsters if m.kind.lives >= BOSS]
        if not bosses:
            return False
        hands.smite(max(bosses, key=lambda m: m.s).id)
        self.last_aim = world.time
        return True

    def _hold_gate(self, hands: Hands) -> bool:
        """A Frozen Orb on the queue at a gate about to break, when the queue is worth holding."""
        world = hands.world
        if not ready(world, "orb"):
            return False
        for door in world.doors:
            if not door.built:
                continue
            batterers = [m for m in world.monsters if m.door == door.index]
            if not batterers:
                continue
            blows = sum(m.kind.door_dps * ((1.0 - m.chill) if m.chill_left > 0 else 1.0) for m in batterers)
            if door.hp > blows * 1.5:
                continue
            queue = [m for m in world.monsters if not m.kind.flying and door.s - 2.5 < m.s < door.s]
            if sum(m.hp for m in queue) < GATE_CROWD * world.power():
                continue
            x, y = world.level.point(door.s - DOOR_STOP - JOSTLE / 2)
            hands.orb(x, y)
            self.last_aim = world.time
            return True
        return False

    def _meteor(self, hands: Hands, bite: float) -> bool:
        """A Meteor where the monsters will stand when it lands, if it would take ``bite`` blows' worth of life."""
        world = hands.world
        cost = world.spell_cost("meteor")
        reserve = world.spell_cost("smite") if "smite" in world.location.arsenal.spells else 0.0
        if not ready(world, "meteor") or (world.mana < cost + reserve and world.mana < world.mana_max - FULL):
            return False
        spec = SPELLS["meteor"]
        damage = spec.damage * world.power()
        points = [(m, _ahead(world, m, spec.delay)) for m in world.monsters]
        best, best_value = None, 0.0
        r2 = spec.radius * spec.radius
        for _, (cx, cy) in points:
            value = 0.0
            for m, (mx, my) in points:
                if (mx - cx) ** 2 + (my - cy) ** 2 <= r2:
                    value += min(m.hp, damage * max(0.0, m.kind.taken(Element.FIRE)))
            if value > best_value:
                best, best_value = (cx, cy), value
        if best is None or best_value < bite * damage:
            return False
        hands.meteor(*best)
        self.last_aim = world.time
        return True


def _tower_value(world: World, tower: Tower) -> float:
    """How much a tower is about to do: its strength times the monsters in or coming into its reach."""
    stats = tower.stats
    spans = world.level.coverage(tower.tile, stats.range)
    widened = tuple((a - ARRIVING, b) for a, b in spans)
    element = tower.kind.element
    load = 0.0
    for m in world.monsters:
        if _inside(m.s, widened):
            load += max(0.0, m.kind.taken(element))
    attack = tower.kind.attack
    if attack == "nova":
        cap = 8.0
    elif attack == "chain":
        cap = 1.0 + stats.chains
    elif attack == "bolt":
        cap = 3.0 if stats.splash > 0 else 1.0
    else:
        cap = 1.5
    return stats.damage * stats.rate * min(load, cap)


def _clear(world: World, s: float) -> bool:
    """No walker stands in the arch at ``s``: a gate can be set there."""
    return not any(not m.kind.flying and abs(m.s - s) < 0.6 for m in world.monsters)


def _near(world: World, x: float, y: float, radius: float) -> list[Monster]:
    found = []
    for m in world.monsters:
        mx, my = world.level.point(m.s)
        if (mx - x) ** 2 + (my - y) ** 2 <= radius * radius:
            found.append(m)
    return found


def _ahead(world: World, m: Monster, seconds: float) -> tuple[float, float]:
    """Where a monster will stand in a moment: walking at its pace, held by a standing gate."""
    walking = max(0.0, seconds - max(0.0, m.frozen))
    s = m.s + (m.kind.speed * (1.0 - m.chill) if m.chill_left > 0 else m.kind.speed) * walking
    if not m.kind.flying:
        for d in world.doors:
            if d.built and d.s > m.s:   # a queue's depth is unseen until it forms: its middle
                s = min(s, max(m.s, d.s - DOOR_STOP - JOSTLE / 2))
                break
    return world.level.point(s)
