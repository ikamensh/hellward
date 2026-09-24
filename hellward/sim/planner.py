"""How a leader chooses its curse: shortlist by a quick estimate, then look ahead by simulation.

When a leader's curse is ready it considers every tower it could reach and every curse it knows. A cheap
estimate (:func:`estimate`) says how much damage the curse would stop that tower dealing while it lasts,
from where each monster will walk and what it resists. The best few go to **rollouts**: the world is cloned
and played forward a little past the curse's end at a coarse step, once with nothing cast and once per
option, and each option's *gain* is how much more life the pack keeps (the life of the monsters still
standing, monsters that reached the sanctuary at twice their life, and the life knocked off doors).

A rollout knows everything the estimate misses: the fireball that would have hit the whole queue at a
door, the frost that stops the door breaking, the shaman's own life, the other curses already landing,
the wave still spawning. Timing is judged the same way: the best targets are also tried two and four
seconds later, and a leader holds its curse while waiting is clearly worth more.

:func:`decide` is a pure function of the world; the game runs it in a worker process
(:mod:`hellward.ui.thinking`), tests and tools inline.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from hellward.sim.content import CURSES, Curse
from hellward.sim.model import CAST_SLACK, DECIDE_DELAY, DOOR_STOP, HOLD_RETRY, ForcedCurse, Monster, Tower, World

ROLLOUT_DT = 0.1
HORIZON_PAD = 3.0      # seconds a rollout runs past the curse's end, to see what it changed
SHORTLIST = 10         # (curse, tower) pairs that get a rollout
DELAYS = (2.0, 4.0)    # later moments tried for the best targets
LATER_TRIED = 3
LATER_MARGIN = 1.2     # waiting must beat casting now by this factor ...
MIN_GAIN = 15.0        # ... and by this much life; a curse worth less than this is not cast
QUIET_RETRY = 1.5      # when nothing is worth cursing
SAMPLE = 0.5           # the estimate's time step


@dataclass(frozen=True)
class Option:
    curse: Curse
    tower: int
    delay: float = 0.0     # seconds after now that the leader would start
    estimate: float = 0.0  # the quick estimate of damage prevented
    gain: float = 0.0      # life the pack keeps over holding, by rollout


@dataclass(frozen=True)
class Decision:
    leader: int
    cast: Option | None
    options: tuple[Option, ...] = ()   # every option that was rolled out, best first
    later: Option | None = None        # the delayed option that made the leader hold
    retry: float = HOLD_RETRY
    rollouts: int = 0
    considered: int = 0                # (curse, tower) pairs the estimate looked at
    reason: str = ""


@dataclass
class Inline:
    decision: Decision

    def result(self) -> Decision:
        return self.decision


def smart(world: World, leader_id: int) -> Inline:
    return Inline(decide(world, leader_id))


# -- Candidates and the estimate --------------------------------------------------------------


def reachable(world: World, leader: Monster, delay: float = 0.0) -> list[Tower]:
    """Towers the leader will still reach when its chant ends, assuming it keeps walking."""
    spec = leader.kind.leader
    s = leader.s + leader.speed * (DECIDE_DELAY + spec.channel + delay)
    x, y = world.level.point(s)
    limit = spec.cast_range + CAST_SLACK * 0.5
    found = []
    for t in world.towers.values():
        cx, cy = t.centre
        if (cx - x) ** 2 + (cy - y) ** 2 <= limit * limit:
            found.append(t)
    return found


def _trajectory(world: World, m: Monster, times: list[float]) -> list[float]:
    """Where a monster will be at each time, walking at its current pace and stopping at standing doors."""
    stop = None
    if not m.kind.flying:
        for d in world.doors:
            if d.built and d.s > m.s:
                stop = d.s - DOOR_STOP - m.jostle
                break
    speed = m.speed
    out = []
    for t in times:
        s = m.s + speed * t
        if stop is not None and s > stop:
            s = max(stop, m.s)
        out.append(s)
    return out


def _damage_in(tower: Tower, reach: float, world: World, tracks: list[tuple[Monster, list[float]]], index: int) -> float:
    """Damage per second a tower would deal, at one sample, to the monsters within ``reach``."""
    spans = world.level.coverage(tower.tile, reach)
    element = tower.kind.element
    taken = []
    for m, track in tracks:
        s = track[index]
        for a, b in spans:
            if a <= s <= b:
                taken.append(m.kind.taken(element))
                break
    if not taken:
        return 0.0
    stats = tower.stats
    dps = stats.damage * stats.rate
    attack = tower.kind.attack
    if attack == "nova":
        return dps * sum(taken)
    taken.sort(reverse=True)
    if attack == "chain":
        return dps * sum(v * 0.85 ** i for i, v in enumerate(taken[: 1 + stats.chains]))
    if attack == "venom":
        return (dps + stats.poison * min(4, stats.poison_time * stats.rate)) * taken[0]
    splash = 1.0 + 0.6 * min(3, len(taken) - 1) if stats.splash > 0 else 1.0
    return dps * taken[0] * splash


def estimate(world: World, leader: Monster, tower: Tower, curse: Curse, delay: float = 0.0) -> float:
    """Damage the curse would stop the tower dealing while it lasts, from each monster's projected walk."""
    spec = CURSES[curse]
    start = DECIDE_DELAY + leader.kind.leader.channel + delay
    left = tower.curses.get(curse, 0.0)
    if left >= spec.duration * 0.5:
        return 0.0   # it is already carrying this curse; recasting would buy little
    begin = start + left
    times = []
    t = begin
    while t < start + spec.duration:
        times.append(t)
        t += SAMPLE
    if not times:
        return 0.0
    tracks = [(m, _trajectory(world, m, times)) for m in world.monsters]
    full = tower.stats.range * tower.multiplier("range")
    total = 0.0
    for i in range(len(times)):
        before = _damage_in(tower, full, world, tracks, i) * tower.multiplier("damage") * tower.multiplier("rate")
        if before <= 0:
            continue
        if spec.silenced or tower.silenced:
            after = 0.0
        elif spec.range != 1.0:
            after = _damage_in(tower, full * spec.range, world, tracks, i) * tower.multiplier("damage") * tower.multiplier("rate")
        else:
            after = before * spec.damage * spec.rate
        total += (before - after) * SAMPLE
    return total


def candidates(world: World, leader: Monster, delay: float = 0.0) -> list[Option]:
    out = []
    for tower in reachable(world, leader, delay):
        for curse in leader.kind.leader.curses:
            out.append(Option(curse, tower.id, delay, estimate(world, leader, tower, curse, delay)))
    out.sort(key=lambda o: (-o.estimate, o.tower, o.curse.value))
    return out


# -- Rollouts ---------------------------------------------------------------------------------


def horizon(leader: Monster) -> float:
    return max(CURSES[c].duration for c in leader.kind.leader.curses) + HORIZON_PAD


def utility(after: World, before: World) -> float:
    """What the pack has left: standing life, sanctuary life (weighted), and life knocked off doors."""
    life = sum(m.hp for m in after.monsters) + after.leaked_life - before.leaked_life
    for d0, d1 in zip(before.doors, after.doors):
        if d0.built:
            life += d0.hp - (d1.hp if d1.built else 0.0)
    return life


def rollout(world: World, leader_id: int, option: Option | None, seconds: float, dt: float = ROLLOUT_DT) -> float:
    w = world.clone()
    if option is not None:
        leader = world.monster(leader_id)
        at = world.time + DECIDE_DELAY + leader.kind.leader.channel + option.delay
        w.forced.append(ForcedCurse(at, leader_id, option.curse, option.tower))
    end = world.time + seconds - 1e-9
    while w.time < end and w.outcome is None:
        w.step(dt)
    return utility(w, world)


def decide(world: World, leader_id: int, *, dt: float = ROLLOUT_DT, shortlist: int = SHORTLIST,
           timing: bool = True) -> Decision:
    leader = world.monster(leader_id)
    options = candidates(world, leader)
    considered = len(options)
    useful = options[:shortlist]   # an estimate of zero can still be wrong: a chill that holds a door is not damage
    if not any(o.estimate > 0 for o in useful):
        return Decision(leader_id, None, retry=QUIET_RETRY, considered=considered, reason="nothing in reach is hurting the pack")
    seconds = horizon(leader) + (max(DELAYS) if timing else 0.0)
    base = rollout(world, leader_id, None, seconds, dt)
    rolled = [Option(o.curse, o.tower, 0.0, o.estimate, rollout(world, leader_id, o, seconds, dt) - base) for o in useful]
    rolled.sort(key=lambda o: (-o.gain, o.tower, o.curse.value))
    count = 1 + len(rolled)
    best = rolled[0]
    later = None
    if timing:
        for o in rolled[:LATER_TRIED]:
            for delay in DELAYS:
                gain = rollout(world, leader_id, Option(o.curse, o.tower, delay), seconds, dt) - base
                count += 1
                if later is None or gain > later.gain:
                    later = Option(o.curse, o.tower, delay, o.estimate, gain)
    if later is not None and later.gain > best.gain * LATER_MARGIN + MIN_GAIN:
        return Decision(leader_id, None, tuple(rolled), later, HOLD_RETRY, count, considered, "waiting is worth more")
    if best.gain < MIN_GAIN:
        return Decision(leader_id, None, tuple(rolled), later, QUIET_RETRY, count, considered, "no curse is worth casting")
    return Decision(leader_id, best, tuple(rolled), later, HOLD_RETRY, count, considered, "")


# -- Baselines, for the quality tool and the tests --------------------------------------------


@dataclass
class RandomLeaders:
    """Curses a random tower in reach with a random curse, as soon as it can."""

    seed: int = 0
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    def __call__(self, world: World, leader_id: int) -> Inline:
        leader = world.monster(leader_id)
        towers = reachable(world, leader)
        if not towers:
            return Inline(Decision(leader_id, None, retry=QUIET_RETRY, reason="random: nothing in reach"))
        tower = self.rng.choice(sorted(towers, key=lambda t: t.id))
        curse = self.rng.choice(leader.kind.leader.curses)
        return Inline(Decision(leader_id, Option(curse, tower.id), reason="random"))


def greedy(world: World, leader_id: int) -> Inline:
    """The estimate alone, cast at once: the heuristic without the look-ahead."""
    leader = world.monster(leader_id)
    options = [o for o in candidates(world, leader) if o.estimate > 0]
    if not options:
        return Inline(Decision(leader_id, None, retry=QUIET_RETRY, reason="greedy: nothing in reach"))
    return Inline(Decision(leader_id, options[0], considered=len(options), reason="greedy"))


def nearest(world: World, leader_id: int) -> Inline:
    """Curses the closest tower with its first curse: what a naive leader does."""
    leader = world.monster(leader_id)
    towers = reachable(world, leader)
    if not towers:
        return Inline(Decision(leader_id, None, retry=QUIET_RETRY, reason="nearest: nothing in reach"))
    x, y = world.level.point(leader.s)
    tower = min(towers, key=lambda t: ((t.centre[0] - x) ** 2 + (t.centre[1] - y) ** 2, t.id))
    return Inline(Decision(leader_id, Option(leader.kind.leader.curses[0], tower.id), reason="nearest"))
