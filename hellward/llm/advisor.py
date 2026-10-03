"""Quick math for the LLM player: where to build, what a wave needs, rank or new tower.

Every answer is pure arithmetic over the authored waves and the map geometry — no
clones, no rollouts, milliseconds. Placement scores a tile by the path it sees times
the damage it deals the coming mix, less the curse-spacing penalty; the wave brief
ranks the offered towers by felt damage per gold against one wave.
"""

from __future__ import annotations

from dataclasses import dataclass

from hellward.sim.content import MONSTERS, TOWERS
from hellward.sim.model import World
from hellward.sim.players.spacing import score_with_spacing
from hellward.sim.sums import float_sum

from hellward.llm.view import monster_hp, tower_hits

SUPPORT = ("amplify", "aura", "hook")


@dataclass(frozen=True)
class Spot:
    tile: tuple[int, int]
    score: float
    cover: float      # tiles of path in reach, traffic-weighted
    dps: float        # felt damage per second against the coming mix
    note: str = ""


def upcoming(world: World) -> list[int]:
    """Waves still to come, including the one now fighting."""
    return list(range(max(world.wave, 0), len(world.waves)))


def mix(world: World, waves: list[int] | None = None) -> dict[str, float]:
    """Each kind's share of the coming life, as the wave list tells it."""
    life: dict[str, float] = {}
    for index in upcoming(world) if waves is None else waves:
        for group in world.waves[index].groups:
            life[group.kind] = life.get(group.kind, 0.0) + group.count * monster_hp(world, group.kind, index)
    total = float_sum(life.values())
    return {kind: value / total for kind, value in life.items()} if total > 0 else {}


def traffic(world: World, waves: list[int] | None = None) -> dict[str, float]:
    """Each route's share of the coming bodies, by the authored route (wanderers may stray)."""
    bodies: dict[str, float] = {}
    for index in upcoming(world) if waves is None else waves:
        for group in world.waves[index].groups:
            bodies[group.route] = bodies.get(group.route, 0.0) + group.count
    total = float_sum(bodies.values())
    return {key: value / total for key, value in bodies.items()} if total > 0 else {}


def dps_vs(world: World, tower_key: str, rank: int, kinds: dict[str, float]) -> float:
    """Felt damage per second of one rank against a life mix (no auras, no curses)."""
    tower = TOWERS[tower_key]
    if tower.attack in SUPPORT:
        return 0.0
    level = world.tower_levels[tower_key][rank]
    per_hit = float_sum(tower_hits(world, tower_key, rank, kind) * share for kind, share in kinds.items())
    return per_hit * level.rate


def _coverage(world: World, tile: tuple[int, int], reach: float, shares: dict[str, float]) -> float:
    total = 0.0
    for route in world.level.routes:
        share = shares.get(route.key, 0.0)
        if share <= 0:
            continue
        spans = world.level.route(route.key).coverage(tile, reach)
        total += share * float_sum(b - a for a, b in spans)
    return total


def placement(world: World, kind: str, *, top: int = 5) -> list[Spot]:
    """The best empty tiles for a tower kind, scored by path seen times felt damage."""
    tower = TOWERS[kind]
    reach = world.tower_levels[kind][0].range
    level = world.level
    kinds = mix(world)
    shares = traffic(world)
    small = {k: share for k, share in kinds.items() if MONSTERS[k].small}
    small_total = float_sum(small.values())
    small = {k: share / small_total for k, share in small.items()} if small_total > 0 else {}
    existing = [t.tile for t in world.towers.values()]
    spots = []
    for x in range(level.width):
        for y in range(level.height):
            if not level.buildable(x, y) or world.tower_at((x, y)) is not None:
                continue
            tile = (x, y)
            cover = _coverage(world, tile, reach, shares)
            if tower.attack == "hook":
                dps = dps_vs(world, "arrow", 0, small) if small else 0.0
                note = "hook: drags small foes back under the other towers"
            elif tower.key == "knife":
                near_gate = any((dx * dx + dy * dy) ** 0.5 <= reach + 0.5
                                for gx, gy in level.doors for dx, dy in [(gx - x, gy - y)])
                dps = dps_vs(world, kind, 0, small if small else kinds)
                cover = cover if not near_gate else cover + 4.0
                note = "knife: doubled knives at a gate queue" if near_gate else "knife: no gate in reach"
            elif tower.attack in ("amplify", "aura"):
                dps = 1.0
                note = f"{kind}: support, no damage of its own — cover is reach over the pack"
            else:
                dps = dps_vs(world, kind, 0, kinds)
                note = ""
            base = cover * max(dps, 0.01 if tower.attack in ("amplify", "aura") else 0.0)
            if base <= 0:
                continue
            scored = score_with_spacing(base, existing, tile, world.location)
            if scored < base - 1e-9:
                note = (note + "; " if note else "") + "spacing: shares a curse circle"
            spots.append(Spot(tile, scored, cover, dps, note))
    spots.sort(key=lambda s: (-s.score, s.tile[1], s.tile[0]))
    return spots[:top]


def wave_brief(world: World, wave: int) -> str:
    """One wave's totals, its tricks, and the offered towers ranked by damage per gold."""
    groups = world.waves[wave].groups
    bodies = sum(g.count for g in groups)
    life = float_sum(g.count * monster_hp(world, g.kind, wave) for g in groups)
    kinds = mix(world, [wave])
    flyers = sum(g.count for g in groups if MONSTERS[g.kind].flying)
    armor = max((MONSTERS[g.kind].armor for g in groups), default=0)
    leaders = sorted({g.kind for g in groups if MONSTERS[g.kind].leader is not None})
    tricks = []
    if flyers:
        tricks.append(f"{flyers} fly (ignore gates)")
    if armor:
        tricks.append(f"armor {armor} (heavy hits count)")
    if leaders:
        tricks.append("leaders: " + ",".join(leaders))
    ranked = []
    for key in world.arsenal.towers:
        if TOWERS[key].attack in SUPPORT:
            continue
        dealt = dps_vs(world, key, 0, kinds) / world.cost(key)
        ranked.append((dealt, key))
    ranked.sort(reverse=True)
    table = " ".join(f"{key} {dealt * 100:.1f}" for dealt, key in ranked)
    out = f"w{wave + 1}: {bodies} foes {life:.0f}hp"
    if tricks:
        out += " | " + "; ".join(tricks)
    return out + f" | felt dps per 100g: {table}"


def upgrade_value(world: World, tile: tuple[int, int]) -> str:
    """Rank this tower or build anew: marginal felt dps per gold either way."""
    tower = world.tower_at(tile)
    if tower is None:
        return f"no tower at {tile}"
    kinds = mix(world)
    cost = world.upgrade_cost(tower)
    if cost is None:
        return f"#{tower.id} {tower.kind.key} is at its top rank here ({world.rank_needs(tower)})"
    now = dps_vs(world, tower.kind.key, tower.level, kinds)
    nxt = dps_vs(world, tower.kind.key, tower.level + 1, kinds)
    options = [(100 * (nxt - now) / cost, f"rank {tower.kind.key} to {tower.level + 2}")]
    for key in world.arsenal.towers:
        if TOWERS[key].attack in SUPPORT:
            continue
        options.append((100 * dps_vs(world, key, 0, kinds) / world.cost(key), f"new {key}"))
    options.sort(reverse=True)
    return "felt dps per 100g: " + "; ".join(f"{what} {value:.1f}" for value, what in options)
