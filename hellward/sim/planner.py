"""How a leader chooses its curse: shortlist by a quick estimate, then look ahead by simulation.

When a leader's curse is ready it considers every tower it could reach and every curse it knows. A cheap
estimate (:func:`candidates`) says how much damage the curse would stop that tower dealing while it lasts,
from where each monster will walk and how each hit is felt there (the rules' own :func:`~hellward.sim.content.felt_hit`:
protections, armor, auras, a knife at a gate), a hook's pulls priced by the time they give the other towers, and a
hymned tower at its hymned rate. A curse falls on a spot, so each candidate is a
(curse, spot) pair priced by every tower its circle catches. The best few go to **rollouts**: the world is cloned
and played forward a little past the curse's end at the game's step, once with nothing cast and once per
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

from hellward.sim import tuning
from hellward.sim.content import (
    CURSES, MAX_POISON_STACKS, Curse, CurseSpec, LeaderSpec, felt_hit, felt_over_time,
)
from hellward.sim.model import (
    CAST_SLACK, DECIDE_DELAY, DOOR_STOP, HOLD_RETRY, HOOK, HOOK_PAST, HOOK_PULL, KNIFE_STANDING, SIM_DT, SPLASH_SHARE,
    ForcedCurse, Monster, Tower, World, curse_radius,
)
from hellward.sim.sums import add, float_sum, int_sum, settle

ROLLOUT_DT: Final = SIM_DT
HORIZON_PAD: Final = tuning.number("planner.horizon_pad")
SHORTLIST: Final = tuning.integer("planner.shortlist")
DELAYS: Final = tuning.numbers("planner.delays")
LATER_TRIED: Final = tuning.integer("planner.later_tried")
LATER_MARGIN: Final = tuning.number("planner.later_margin")
MIN_GAIN: Final = tuning.number("planner.min_gain")
QUIET_RETRY: Final = tuning.number("planner.quiet_retry")
SAMPLE: Final = tuning.number("planner.sample")
LASTING: Final = tuning.number("planner.lasting")


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


def _voiced(spec: LeaderSpec) -> float:
    """Seconds between the choice and the curse landing: the chant, or the mark's burning for a leader that marks."""
    return spec.mark if spec.mark > 0 else spec.channel


def _spec(leader: Monster) -> LeaderSpec:
    spec = leader.kind.leader
    if spec is None:
        raise ValueError(f"a {leader.kind.name} is no leader: it has no curse to choose")
    return spec


# -- Candidates and the estimate --------------------------------------------------------------


def reachable(world: World, leader: Monster, delay: float = 0.0) -> list[Tower]:
    """Towers the leader will still reach when its chant ends, assuming it keeps walking."""
    spec = _spec(leader)
    lands = DECIDE_DELAY + _voiced(spec) + delay
    s = leader.s + leader.speed * lands
    x, y = world.level.route(leader.route).point(s)
    limit = spec.cast_range + CAST_SLACK * 0.5
    found = []
    for t in world.towers.values():
        cx, cy = t.centre
        if (cx - x) ** 2 + (cy - y) ** 2 <= limit * limit:
            found.append(t)
    return found


def _trajectory(world: World, m: Monster, times: list[float]) -> tuple[list[float], list[bool]]:
    """Where a monster will be at each time, walking at its current pace and stopping at standing doors, and whether
    it stands still there (frozen, or queued at a door)."""
    stop = None
    if not m.kind.flying:
        for door_index, s in world.level.crossings(m.route):
            if world.doors[door_index].built and s > m.s:
                stop = s - DOOR_STOP - m.jostle
                break
    speed = m.kind.speed * (1.0 - m.chill) if m.chill_left > 0 else m.kind.speed
    where: list[float] = []
    standing: list[bool] = []
    for t in times:
        walked = t - m.frozen
        s = m.s + speed * max(0.0, walked)
        held = walked <= 0
        if stop is not None and s > stop:
            s = max(stop, m.s)
            held = True
        where.append(s)
        standing.append(held)
    return where, standing


def _spans(world: World, tower: Tower, reach: float) -> dict[str, tuple[tuple[float, float], ...]]:
    return {route.key: (world.level.coverage(tower.tile, reach) if route.key == "main" else route.coverage(tower.tile, reach))
            for route in world.level.routes}


def _damage_in(tower: Tower, reach: float, world: World, tracks: list[tuple[Monster, list[float], list[bool]]],
               index: int, allowed: dict[str, tuple[tuple[float, float], ...]] | None = None, share: float = 1.0,
               rate: float = 1.0) -> float:
    """Damage per second a tower would deal, at one sample, to the monsters within ``reach``: each hit felt as the
    rules feel it (:func:`~hellward.sim.content.felt_hit`: protections, armor, the aura, a knife on a standing
    monster), at ``share`` of its hit and ``rate`` times its attacks (a curse's, a hymn's); with ``allowed``, only to
    those also on those stretches of the path (an altar's reach, whose amplification it lends to). A hook's is its hit
    and its pull: the damage the other towers deal the monster in the time it gives them back."""
    spans = _spans(world, tower, reach)
    in_reach: list[tuple[Monster, float, bool]] = []   # nearest the sanctuary first, as the world keeps them
    for m, track, standing in tracks:
        s = track[index]
        if allowed is not None and not any(a <= s <= b for a, b in allowed[m.route]):
            continue
        for a, b in spans[m.route]:
            if a <= s <= b:
                in_reach.append((m, s, standing[index]))
                break
    if not in_reach:
        return 0.0
    stats = tower.stats
    attack = tower.kind.attack
    element = tower.kind.element
    hit = stats.damage * share
    aura = world.aura_mult(tower)
    per_second = stats.rate * rate
    if attack == "hook":
        return per_second * _hooked(tower, world, in_reach, hit, aura, share)
    if attack == "venom":   # the strongest in reach
        strongest = in_reach[0][0]
        for m, _, _ in in_reach:
            if m.hp > strongest.hp:
                strongest = m
        stacks = min(float(MAX_POISON_STACKS), stats.poison_time * per_second)
        return (per_second * felt_hit(hit, element, strongest.kind, aura)
                + felt_over_time(stats.poison * aura * stacks, element, strongest.kind))
    if attack == "nova":
        return per_second * int_sum(felt_hit(hit, element, m.kind, aura) for m, _, _ in in_reach)
    if tower.kind.key == "knife":
        for m, _, held in in_reach:
            if held and m.kind.small:
                return per_second * felt_hit(hit, element, m.kind, aura * KNIFE_STANDING)
    ordered = sorted(in_reach, key=lambda e: -felt_hit(hit, element, e[0].kind, aura))   # the hardest-hit first
    if attack == "chain":
        keeps = world.perks.leap_keeps
        return per_second * int_sum(felt_hit(hit, element, ordered[i][0].kind, aura * keeps ** i)
                                    for i in range(min(len(ordered), 1 + stats.chains)))
    total = felt_hit(hit, element, ordered[0][0].kind, aura)
    if stats.splash > 0:   # a fireball's lesser blows on up to three around its target
        total += int_sum(felt_hit(hit, element, ordered[i][0].kind, aura * SPLASH_SHARE)
                         for i in range(1, min(len(ordered), 4)))
    return per_second * total


def _hooked(tower: Tower, world: World, in_reach: list[tuple[Monster, float, bool]], hit: float, aura: float,
            share: float) -> float:
    """What one hook is worth at a sample: its hit on the monster it would hook (the foremost small one past its spot,
    never hooked, not standing), and the damage the other towers covering the dragged stretch deal that monster in
    the seconds the pull gives them (HOOK_PULL tiles, times Weaken's share, at its pace)."""
    level = world.level
    for m, s, held in in_reach:
        if held or not m.kind.small or m.moved & HOOK:
            continue
        spot = level.nearest(m.route, tower.tile)
        if s < spot + HOOK_PAST:
            continue
        pull = min(HOOK_PULL * share, s - spot)
        middle = s - pull * 0.5
        route = level.route(m.route)
        others = 0.0
        for u in world.towers.values():
            if u is tower or u.silenced or u.kind.attack in ("aura", "amplify", "hook"):
                continue
            covered = level.coverage(u.tile, u.reach) if m.route == "main" else route.coverage(u.tile, u.reach)
            if any(a <= middle <= b for a, b in covered):
                others += (felt_hit(u.stats.damage * u.damage_mult(), u.kind.element, m.kind, world.aura_mult(u))
                           * u.stats.rate * u.rate_mult())
        return felt_hit(hit, tower.kind.element, m.kind, aura) + others * pull / m.kind.speed
    return 0.0


def _priced(tower: Tower, curse: Curse, world: World, start: float, times: list[float],
            tracks: list[tuple[Monster, list[float], list[bool]]]) -> float:
    """Damage the curse would stop one tower dealing, over the shared tracks at ``times``."""
    spec = CURSES[curse]
    left = tower.curses.get(curse, 0.0)
    if left >= spec.duration * 0.5:
        return 0.0   # it is already carrying this curse; recasting would buy little
    if tower.kind.key in ("grove", "altar"):
        return _lent(tower, curse, world, start, left, times, tracks)
    begin, end = start + left, start + spec.duration
    full = tower.stats.range * tower.range_mult()
    share, rate = tower.damage_mult(), tower.rate_mult()   # a hymn is in the rate: the leaders see the boost
    total, error = 0.0, 0.0
    for i in range(len(times)):
        moment = times[i]
        if moment < begin or moment >= end:
            continue
        before = _damage_in(tower, full, world, tracks, i, share=share, rate=rate)
        if before <= 0:
            continue
        if spec.silenced or tower.silenced:
            after = 0.0
        elif spec.damage == 1.0 and spec.range == 1.0:
            after = before * spec.rate   # fewer attacks deal proportionally less
        else:
            after = _damage_in(tower, full * spec.range, world, tracks, i, share=share * spec.damage,
                               rate=rate * spec.rate)
        total, error = add(total, error, (before - after) * SAMPLE)
    return settle(total, error)


def _lent(tower: Tower, curse: Curse, world: World, start: float, left: float, times: list[float],
          tracks: list[tuple[Monster, list[float], list[bool]]]) -> float:
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
                tracks: list[tuple[Monster, list[float], list[bool]]]) -> float:
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
            dealt = _damage_in(u, full, world, tracks, i, share=u.damage_mult(), rate=u.rate_mult())
            if dealt > 0:
                total, error = add(total, error, dealt * SAMPLE)
    dealt_total = settle(total, error)
    return dealt_total * bonus * (1.0 - after_share)


def _lent_altar(tower: Tower, spec: CurseSpec, world: World, start: float, left: float, times: list[float],
                tracks: list[tuple[Monster, list[float], list[bool]]]) -> float:
    stats = tower.stats
    full = stats.range * tower.range_mult()
    before = stats.damage * tower.damage_mult()
    if spec.silenced:   # caged: it lends none of its amplification while the curse lasts
        return _altar_damage(tower, world, times, tracks, start, left, spec, full, full, before, 0.0, True)
    after_reach = full * spec.range if spec.range != 1.0 else full
    after = before * spec.damage if spec.damage != 1.0 else before
    if spec.rate != 1.0:
        after *= spec.rate   # a slower pulse lays its knot less often
    return _altar_damage(tower, world, times, tracks, start, left, spec, full, after_reach, before, after, False)


def _altar_damage(tower: Tower, world: World, times: list[float], tracks: list[tuple[Monster, list[float], list[bool]]],
                  start: float, left: float, spec: CurseSpec, full: float, after_reach: float,
                  before: float, after: float, silenced: bool) -> float:
    others = _helpers(world)
    if not others:
        return 0.0
    begin, end = start + left, start + spec.duration
    near_spans = _spans(world, tower, full)
    far_spans = _spans(world, tower, after_reach) if after_reach != full else near_spans
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
            share, rate = u.damage_mult(), u.rate_mult()
            dealt = _damage_in(u, reach, world, tracks, i, near_spans, share, rate)
            if dealt > 0:
                lent, lent_error = add(lent, lent_error, dealt * SAMPLE * before)
            if not silenced and after > 0:
                dealt = _damage_in(u, reach, world, tracks, i, far_spans, share, rate)
                if dealt > 0:
                    kept, kept_error = add(kept, kept_error, dealt * SAMPLE * after)
    return settle(lent, lent_error) - settle(kept, kept_error)


def candidates(world: World, leader: Monster, delay: float = 0.0) -> list[Option]:
    """One (curse, spot) pair per tower in reach: the tower's tile, priced by the towers the circle catches. Spots
    catching the same towers with the same curse are one candidate."""
    towers = reachable(world, leader, delay)
    if not towers:
        return []
    spec = _spec(leader)
    start = DECIDE_DELAY + _voiced(spec) + delay
    curses = spec.curses
    longest = max(CURSES[c].duration for c in curses)
    times = []
    t = start
    while t < start + longest:
        times.append(t)
        t += SAMPLE
    if not times:
        return []
    tracks: list[tuple[Monster, list[float], list[bool]]] = []
    for m in world.monsters:
        where, standing = _trajectory(world, m, times)
        tracks.append((m, where, standing))
    loss: dict[tuple[int, Curse], float] = {}
    for tower in world.towers.values():
        for curse in curses:
            loss[(tower.id, curse)] = _priced(tower, curse, world, start, times, tracks)
    out = []
    seen: set[tuple[Curse, tuple[int, ...]]] = set()
    for spot in sorted({t.tile for t in towers}):
        for curse in curses:
            caught = tuple(t.id for t in world.caught(spot, curse_radius(curse, leader.kind, world.curse_scale)))
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
        at = world.time + DECIDE_DELAY + _voiced(_spec(_leader(world, leader_id))) + option.delay
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
    x, y = world.position(leader)
    tower = min(towers, key=lambda t: ((t.centre[0] - x) ** 2 + (t.centre[1] - y) ** 2, t.id))
    return Inline(Decision(leader_id, Option(_spec(leader).curses[0], tower.tile), reason="nearest"))
