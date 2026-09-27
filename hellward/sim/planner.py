"""How a leader chooses its curse: shortlist by a quick estimate, then look ahead by simulation.

When a leader's curse is ready it considers every tower it could reach and every curse it knows. A cheap
estimate (:func:`candidates`) says how much damage the curse would stop that tower dealing while it lasts,
from where each monster will walk and what it resists. A curse falls on a spot, so each candidate is a
(curse, spot) pair priced by every unwarded tower its circle catches. The best few go to **rollouts**: the world is cloned
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
from typing import Final

from hellward.sim.content import CURSES, Curse, CurseSpec, LeaderSpec
from hellward.sim.model import (
    CAST_SLACK, DECIDE_DELAY, DOOR_STOP, HOLD_RETRY, ForcedCurse, Monster, Tower, World, curse_radius,
)
from hellward.sim.sums import add, float_sum, settle

ROLLOUT_DT: Final = 0.1
HORIZON_PAD: Final = 3.0      # seconds a rollout runs past the curse's end, to see what it changed
SHORTLIST: Final = 10         # (curse, spot) pairs that get a rollout
DELAYS: Final = (2.0, 4.0)    # later moments tried for the best targets
LATER_TRIED: Final = 3
LATER_MARGIN: Final = 1.2     # waiting must beat casting now by this factor ...
MIN_GAIN: Final = 5.0         # ... and by this much life; a curse is free but for its cooldown, so only noise is not cast
QUIET_RETRY: Final = 1.5      # when nothing is worth cursing
SAMPLE: Final = 0.5           # the estimate's time step
LASTING: Final = 0.5          # the weight of the pack's average life over the look-ahead in a rollout's score


@dataclass(frozen=True)
class Option:
    curse: Curse
    spot: tuple[int, int]
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
    considered: int = 0                # (curse, spot) pairs the estimate looked at
    reason: str = ""


@dataclass
class Inline:
    decision: Decision

    def result(self) -> Decision:
        return self.decision


def smart(world: World, leader_id: int) -> Inline:
    return Inline(decide(world, leader_id))


def _leader(world: World, leader_id: int) -> Monster:
    """The leader that asks: it is on the map, since it asks at a step boundary and rollouts start from one."""
    leader = world.monster(leader_id)
    if leader is None:
        raise LookupError(f"no monster {leader_id} is on the map")
    return leader


def _spec(leader: Monster) -> LeaderSpec:
    spec = leader.kind.leader
    if spec is None:
        raise ValueError(f"a {leader.kind.name} is no leader: it has no curse to choose")
    return spec


# -- Candidates and the estimate --------------------------------------------------------------


def reachable(world: World, leader: Monster, delay: float = 0.0) -> list[Tower]:
    """Towers the leader will still reach when its chant ends, assuming it keeps walking, and that no ward will
    protect then."""
    spec = _spec(leader)
    lands = DECIDE_DELAY + spec.channel + delay
    s = leader.s + leader.speed * lands
    x, y = world.level.point(s)
    limit = spec.cast_range + CAST_SLACK * 0.5
    found = []
    for t in world.towers.values():
        if t.ward > lands:
            continue   # warded until after the curse would land
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
    speed = m.kind.speed * (1.0 - m.chill) if m.chill_left > 0 else m.kind.speed
    out = []
    for t in times:
        s = m.s + speed * max(0.0, t - m.frozen)
        if stop is not None and s > stop:
            s = max(stop, m.s)
        out.append(s)
    return out


def _damage_in(tower: Tower, reach: float, world: World, tracks: list[tuple[Monster, list[float]]], index: int,
               allowed: tuple[tuple[float, float], ...] | None = None) -> float:
    """Damage per second a tower would deal, at one sample, to the monsters within ``reach``; with ``allowed``, only
    to those also on those stretches of the path (an altar's reach, whose amplification it lends to)."""
    spans = world.level.coverage(tower.tile, reach)
    element = tower.kind.element
    taken = []
    for m, track in tracks:
        s = track[index]
        if allowed is not None and not any(a <= s <= b for a, b in allowed):
            continue
        for a, b in spans:
            if a <= s <= b:
                if tower.kind.attack != "venom" or m.kind.taken(element) > 0:   # venom seeks only what it can poison
                    taken.append(m.kind.taken(element))
                break
    if not taken:
        return 0.0
    stats = tower.stats
    dps = stats.damage * stats.rate
    attack = tower.kind.attack
    if attack == "nova":
        return dps * float_sum(taken)
    taken.sort(reverse=True)
    if attack == "chain":
        keeps = world.perks.leap_keeps
        return dps * float_sum(v * keeps ** i for i, v in enumerate(taken[: 1 + stats.chains]))
    if attack == "venom":
        return (dps + stats.poison * min(4, stats.poison_time * stats.rate)) * taken[0]
    splash = 1.0 + 0.6 * min(3, len(taken) - 1) if stats.splash > 0 else 1.0
    return dps * taken[0] * splash


def _priced(tower: Tower, curse: Curse, world: World, start: float, times: list[float],
            tracks: list[tuple[Monster, list[float]]]) -> float:
    """Damage the curse would stop one tower dealing, over the shared tracks at ``times``."""
    spec = CURSES[curse]
    left = tower.curses.get(curse, 0.0)
    if left >= spec.duration * 0.5:
        return 0.0   # it is already carrying this curse; recasting would buy little
    if tower.kind.key in ("grove", "altar"):
        return _lent(tower, curse, world, start, left, times, tracks)
    begin, end = start + left, start + spec.duration
    full = tower.stats.range * tower.range_mult()
    now = tower.damage_mult() * tower.rate_mult()
    total, error = 0.0, 0.0
    for i in range(len(times)):
        moment = times[i]
        if moment < begin or moment >= end:
            continue
        before = _damage_in(tower, full, world, tracks, i) * now
        if before <= 0:
            continue
        if spec.silenced or tower.silenced:
            after = 0.0
        elif spec.range != 1.0:
            after = _damage_in(tower, full * spec.range, world, tracks, i) * now
        else:
            after = before * spec.damage * spec.rate
        total, error = add(total, error, (before - after) * SAMPLE)
    return settle(total, error)


def _lent(tower: Tower, curse: Curse, world: World, start: float, left: float, times: list[float],
          tracks: list[tuple[Monster, list[float]]]) -> float:
    """What a curse on a support tower stops it lending: a grove's bonus on the towers under its aura,
    or an altar's amplification on the damage the other towers deal to the monsters in its reach."""
    spec = CURSES[curse]
    if tower.silenced:
        return 0.0   # caged: it lends nothing already
    if tower.kind.key == "grove":
        return _lent_grove(tower, spec, world, start, left, times, tracks)
    return _lent_altar(tower, spec, world, start, left, times, tracks)


def _helpers(world: World) -> list[Tower]:
    """The towers a support tower lends to: every other non-support tower (altars and groves deal no damage)."""
    return [u for u in world.towers.values() if u.kind.attack not in ("aura", "amplify")]


def _lent_grove(tower: Tower, spec: CurseSpec, world: World, start: float, left: float, times: list[float],
                tracks: list[tuple[Monster, list[float]]]) -> float:
    stats = tower.stats
    if spec.silenced:
        after_share = 0.0
    elif spec.damage != 1.0:
        after_share = spec.damage
    else:
        return 0.0   # Decrepify slows no pulse here and Dim Vision shrinks no reach: an aura is neither
    covered = []
    for u in _helpers(world):
        dx, dy = u.tile[0] - tower.tile[0], u.tile[1] - tower.tile[1]
        if dx * dx + dy * dy <= stats.range * stats.range:
            covered.append(u)
    if not covered:
        return 0.0
    bonus = stats.damage * tower.damage_mult()
    begin, end = start + left, start + spec.duration
    total, error = 0.0, 0.0
    for i in range(len(times)):
        moment = times[i]
        if moment < begin or moment >= end:
            continue
        for u in covered:
            if u.silenced:
                continue
            full = u.stats.range * u.range_mult()
            now = u.damage_mult() * u.rate_mult()
            dealt = _damage_in(u, full, world, tracks, i) * now
            if dealt > 0:
                total, error = add(total, error, dealt * SAMPLE)
    dealt_total = settle(total, error)
    return dealt_total * bonus * (1.0 - after_share)


def _lent_altar(tower: Tower, spec: CurseSpec, world: World, start: float, left: float, times: list[float],
                tracks: list[tuple[Monster, list[float]]]) -> float:
    stats = tower.stats
    full = stats.range * tower.range_mult()
    if spec.silenced:
        return _altar_damage(tower, world, times, tracks, start, left, spec, full, full, 0.0, 0.0, True)
    after_reach = full * spec.range if spec.range != 1.0 else full
    before = stats.damage * tower.damage_mult()
    after = before * spec.damage if spec.damage != 1.0 else before
    if spec.rate != 1.0:
        after *= spec.rate   # a slower pulse lays its knot less often
    return _altar_damage(tower, world, times, tracks, start, left, spec, full, after_reach, before, after, False)


def _altar_damage(tower: Tower, world: World, times: list[float], tracks: list[tuple[Monster, list[float]]],
                  start: float, left: float, spec: CurseSpec, full: float, after_reach: float,
                  before: float, after: float, silenced: bool) -> float:
    others = _helpers(world)
    if not others:
        return 0.0
    begin, end = start + left, start + spec.duration
    near_spans = world.level.coverage(tower.tile, full)
    far_spans = world.level.coverage(tower.tile, after_reach) if after_reach != full else near_spans
    lent, lent_error = 0.0, 0.0
    kept, kept_error = 0.0, 0.0
    for i in range(len(times)):
        moment = times[i]
        if moment < begin or moment >= end:
            continue
        for u in others:
            if u.silenced:
                continue
            reach = u.stats.range * u.range_mult()
            now = u.damage_mult() * u.rate_mult()
            dealt = _damage_in(u, reach, world, tracks, i, near_spans) * now
            if dealt > 0:
                lent, lent_error = add(lent, lent_error, dealt * SAMPLE * before)
            if not silenced and after > 0:
                dealt = _damage_in(u, reach, world, tracks, i, far_spans) * now
                if dealt > 0:
                    kept, kept_error = add(kept, kept_error, dealt * SAMPLE * after)
    return settle(lent, lent_error) - settle(kept, kept_error)


def candidates(world: World, leader: Monster, delay: float = 0.0) -> list[Option]:
    """One (curse, spot) pair per tower in reach: the tower's tile, priced by the unwarded towers the circle
    catches. Spots catching the same towers with the same curse are one candidate."""
    towers = reachable(world, leader, delay)
    if not towers:
        return []
    spec = _spec(leader)
    start = DECIDE_DELAY + spec.channel + delay
    curses = spec.curses
    longest = max(CURSES[c].duration for c in curses)
    times = []
    t = start
    while t < start + longest:
        times.append(t)
        t += SAMPLE
    if not times:
        return []
    tracks = [(m, _trajectory(world, m, times)) for m in world.monsters]
    loss: dict[tuple[int, Curse], float] = {}
    for tower in world.towers.values():
        if tower.ward > start:
            continue   # warded until after the curse would land
        for curse in curses:
            loss[(tower.id, curse)] = _priced(tower, curse, world, start, times, tracks)
    out = []
    seen: set[tuple[Curse, tuple[int, ...]]] = set()
    for spot in sorted({t.tile for t in towers}):
        for curse in curses:
            caught = tuple(t.id for t in world.caught(spot, curse_radius(curse, leader.kind, world.curse_scale)) if t.ward <= start)
            key = (curse, caught)
            if key in seen:
                continue
            seen.add(key)
            out.append(Option(curse, spot, delay, float_sum(loss[(tid, curse)] for tid in caught)))
    out.sort(key=lambda o: (-o.estimate, o.spot, o.curse.value))
    return out


# -- Rollouts ---------------------------------------------------------------------------------


def horizon(leader: Monster) -> float:
    return max(CURSES[c].duration for c in _spec(leader).curses) + HORIZON_PAD


def utility(after: World, before: World, lasting: float = 0.0) -> float:
    """What the pack has left: standing life, sanctuary life (weighted), life knocked off doors, and
    *lasting*, its life averaged over the look-ahead: a monster that dies later has walked further and
    held the towers' fire longer, even when every one of them is dead by the end."""
    life = _life(after) + after.leaked_life - before.leaked_life + LASTING * lasting
    for d0, d1 in zip(before.doors, after.doors):
        if d0.built:
            life += d0.hp - (d1.hp if d1.built else 0.0)
    return life


def rollout(world: World, leader_id: int, option: Option | None, seconds: float, dt: float = ROLLOUT_DT) -> float:
    w = world.clone()
    if option is not None:
        at = world.time + DECIDE_DELAY + _spec(_leader(world, leader_id)).channel + option.delay
        w.forced.append(ForcedCurse(at, leader_id, option.curse, option.spot))
    end = world.time + seconds - 1e-9
    lasting = 0.0
    while w.time < end and w.outcome is None:
        w.step(dt)
        lasting += _life(w) * dt
    return utility(w, world, lasting / seconds)


def _life(world: World) -> float:
    """The life of the monsters on the map, added as the built-in sum adds it (:mod:`hellward.sim.sums`)."""
    total, error = 0.0, 0.0
    for m in world.monsters:
        total, error = add(total, error, m.hp)
    return settle(total, error)


def decide(world: World, leader_id: int, *, dt: float = ROLLOUT_DT, shortlist: int = SHORTLIST,
           timing: bool = True) -> Decision:
    leader = _leader(world, leader_id)
    options = candidates(world, leader)
    considered = len(options)
    useful = options[:shortlist]   # an estimate of zero can still be wrong: a chill that holds a door is not damage
    if not any(o.estimate > 0 for o in useful):
        return Decision(leader_id, None, retry=QUIET_RETRY, considered=considered, reason="nothing in reach is hurting the pack")
    seconds = horizon(leader) + (max(DELAYS) if timing else 0.0)
    base = rollout(world, leader_id, None, seconds, dt)
    rolled = [Option(o.curse, o.spot, 0.0, o.estimate, rollout(world, leader_id, o, seconds, dt) - base) for o in useful]
    rolled.sort(key=lambda o: (-o.gain, o.spot, o.curse.value))
    count = 1 + len(rolled)
    best = rolled[0]
    later = None
    if timing:
        for o in rolled[:LATER_TRIED]:
            for delay in DELAYS:
                gain = rollout(world, leader_id, Option(o.curse, o.spot, delay), seconds, dt) - base
                count += 1
                if later is None or gain > later.gain:
                    later = Option(o.curse, o.spot, delay, o.estimate, gain)
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
        leader = _leader(world, leader_id)
        towers = reachable(world, leader)
        if not towers:
            return Inline(Decision(leader_id, None, retry=QUIET_RETRY, reason="random: nothing in reach"))
        tower = self.rng.choice(sorted(towers, key=lambda t: t.id))
        curse = self.rng.choice(_spec(leader).curses)
        return Inline(Decision(leader_id, Option(curse, tower.tile), reason="random"))


def greedy(world: World, leader_id: int) -> Inline:
    """The estimate alone, cast at once: the heuristic without the look-ahead."""
    leader = _leader(world, leader_id)
    options = [o for o in candidates(world, leader) if o.estimate > 0]
    if not options:
        return Inline(Decision(leader_id, None, retry=QUIET_RETRY, reason="greedy: nothing in reach"))
    return Inline(Decision(leader_id, options[0], considered=len(options), reason="greedy"))


def nearest(world: World, leader_id: int) -> Inline:
    """Curses the closest tower with its first curse: what a naive leader does."""
    leader = _leader(world, leader_id)
    towers = reachable(world, leader)
    if not towers:
        return Inline(Decision(leader_id, None, retry=QUIET_RETRY, reason="nearest: nothing in reach"))
    x, y = world.level.point(leader.s)
    tower = min(towers, key=lambda t: ((t.centre[0] - x) ** 2 + (t.centre[1] - y) ** 2, t.id))
    return Inline(Decision(leader_id, Option(_spec(leader).curses[0], tower.tile), reason="nearest"))
