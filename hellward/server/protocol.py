"""What the server says to the client: messages as plain JSON values.

Every message is one JSON object on one line with a type ``t``. A battle begins with :func:`battle_start` (the
level, its waves and the tables the panel shows, sent once) and then sends a :func:`frame` per step: that step's
events, the purse and clocks, and every monster, tower and gate as it stands. Events keep the simulation's own
shape (``[kind, ...]``) with every value made plain: enums by value, tuples as lists, a bolt or a leader's decision
as a small object. Monsters and towers carry their unchanging facts once, in the ``spawn`` and ``built`` events, and
then only what moves.

``docs/godot-client.md`` lists the messages; the Godot client's ``net.gd`` is the other half.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from hellward.sim.balance import BALANCE
from hellward.sim.campaign import Location
from hellward.sim.content import CURSES, MONSTERS, SELL_REFUND, SPELLS, TOWERS, MonsterKind, felt_hit
from hellward.sim.model import SIM_DT, Bolt, Monster, Tower, World
from hellward.sim import worth

# monster flags, one bit each
PONDERING, CHANTING, MARKING, AMPLIFIED = 1, 2, 4, 8
HITLESS = ("amplify", "aura")   # tower attacks that strike no blow of their own


def plain(value: Any) -> Any:
    """A simulation value as JSON: enums by value, tuples as lists, bolts and decisions as objects."""
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {str(plain(k)): plain(v) for k, v in value.items()}
    if isinstance(value, Bolt):
        return {"id": value.id, "tower": value.tower, "kind": value.kind, "target": value.target, "left": value.left,
                "element": value.element.value, "splash": value.splash, "origin": list(value.origin),
                "last": list(value.last)}
    if type(value).__name__ == "Decision":
        cast = None if value.cast is None else [value.cast.curse.value, list(value.cast.spot)]
        return {"cast": cast, "reason": value.reason, "rollouts": value.rollouts,
                "options": [[o.curse.value, list(o.spot), o.delay, round(o.gain, 2)] for o in value.options[:4]]}
    raise TypeError(f"no plain form for {type(value).__name__}: {value!r}")


def event(world: World, e: tuple) -> list:
    """One simulation event, with the unchanging facts of a newcomer added: a spawned monster's kind, route,
    lane and life, a built tower's kind and tile."""
    out = plain(e)
    if e[0] == "spawn":
        m = world.monster(e[1])
        out[2] = None if m is None else monster_facts(m)   # the facts stand where the sim's kind stood
    elif e[0] == "built":
        out[2] = tower_facts(world.towers[e[1]])
    elif e[0] == "upgraded":
        out.append(tower_facts(world.towers[e[1]]))
    return out


def monster_facts(m: Monster) -> dict:
    return {"kind": m.kind.key, "route": m.route, "lane": m.lane, "jostle": m.jostle, "max_hp": m.max_hp,
            "wave": m.wave, "elite": m.elite_name, "breach": m.breach, "salvage": m.salvage}


def tower_facts(t: Tower) -> dict:
    return {"kind": t.kind.key, "tile": list(t.tile), "level": t.level, "spent": t.spent}


def monsters(world: World) -> list[list]:
    """Every monster on the map: [id, s, hp, flags, chill, frozen, poison stacks, door, moved (the movers' bits)]."""
    out = []
    for m in world.monsters:
        flags = ((PONDERING if m.asking is not None else 0) | (CHANTING if m.chant_curse is not None else 0)
                 | (MARKING if m.marking else 0) | (AMPLIFIED if m.amplified > 0 else 0))
        out.append([m.id, round(m.s, 4), round(m.hp, 2), flags, round(m.chill if m.chill_left > 0 else 0.0, 3),
                    round(m.frozen, 2), len(m.poison), m.door, m.moved])
    return out


def towers(world: World) -> list[list]:
    """Every tower: [id, level, reach, curses {curse: seconds left}, Battle Hymn's seconds left, upgrade cost or None,
    what the next rank needs or None, refund]."""
    out = []
    for t in world.towers.values():
        out.append([t.id, t.level, round(t.reach, 3), {c.value: round(left, 2) for c, left in t.curses.items()},
                    round(t.hymn, 2), world.upgrade_cost(t), world.rank_needs(t), refund(t)])
    return out


def refund(t: Tower) -> int:
    return int(t.spent * SELL_REFUND)


def state(world: World) -> dict:
    """The purse, the clocks and what can be done now."""
    arsenal = world.arsenal
    breach = None
    if world.breach_spec is not None:
        breach = {"offered": world.breach_offered, "mode": world.breach_mode, "remaining": world.breach_remaining,
                  "failed": world.breach_failed, "cleared": world.breach_cleared}
    return {
        "gold": world.gold, "lives": world.lives, "mana": round(world.mana, 3), "mana_max": world.mana_max,
        "wave": world.wave, "waves": len(world.waves),
        "break_left": None if world.break_left is None else round(world.break_left, 3),
        "can_call": world.can_call_wave, "early_bonus": world.early_call_bonus,
        "recharge": {k: round(v, 2) for k, v in world.recharge.items()},
        "salvage": world.salvage_held, "breach": breach, "outcome": world.outcome,
        "cost": {kind: world.cost(kind) for kind in arsenal.towers if kind not in world.perks.locked},
        "door_cost": world.door_cost if arsenal.gates else None,
        "spell_cost": {key: world.spell_cost(key) for key in arsenal.spells if key not in world.perks.locked},
        "kills": world.kills,
    }


def doors(world: World) -> list[list]:
    return [[d.index, round(d.hp, 2), d.built, d.rubble] for d in world.doors]


def hazards(world: World) -> list[list]:
    return [[round(h.x, 3), round(h.y, 3), h.radius, round(h.left, 2)] for h in world.hazards]


def frame(world: World, step: int, events: list[tuple]) -> dict:
    return {"t": "frame", "step": step, "time": world.time, "events": [event(world, e) for e in events],
            "state": state(world), "monsters": monsters(world), "towers": towers(world), "doors": doors(world),
            "hazards": hazards(world)}


def location_facts(location: Location) -> dict:
    return {"key": location.key, "name": location.name, "called": location.called, "theme": location.theme,
            "act": location.act, "blurb": location.blurb, "lesson": location.lesson, "taunt": location.taunt}


def battle_start(world: World, *, demo: bool, breach_claim: str | None) -> dict:
    """Everything about a defence that never changes, sent once: the map, the waves, and the tables. ``demo``: it is
    watched and counts for nothing (the title's demo)."""
    location, level = world.location, world.level
    kinds = sorted({g.kind for wave in world.waves for g in wave.groups}
                   | {MONSTERS[k].leader.raises for k in location.monsters if MONSTERS[k].leader and MONSTERS[k].leader.raises})
    if world.breach_spec is not None:
        kinds = sorted(set(kinds) | {g.kind for g in world.breach_spec.groups})
    return {
        "t": "battle", "demo": demo, "sim_dt": SIM_DT, "location": location_facts(location),
        "width": level.width, "height": level.height,
        "grid": ["".join(level.tile(x, y).value for x in range(level.width)) for y in range(level.height)],
        "routes": [{"key": r.key, "points": [list(p) for p in r.waypoints], "length": r.length} for r in level.routes],
        "doors": [{"index": d.index, "tile": list(d.tile), "s": d.s} for d in world.doors],
        "waves": [{"name": name, "bonus": w.bonus,
                   "groups": [{"kind": g.kind, "count": g.count, "interval": g.interval, "start": g.start,
                               "route": g.route} for g in w.groups]}
                  for name, w in zip(location.wave_names, world.waves)],
        "arsenal": {"towers": [k for k in location.arsenal.towers if k not in world.perks.locked],
                    "gates": location.arsenal.gates,
                    "spells": [k for k in location.arsenal.spells if k not in world.perks.locked]},
        "towers": {kind: tower_table(world, kind) for kind in location.arsenal.towers
                   if kind not in world.perks.locked},
        "worth": {kind: worth_table(world, kind) for kind in location.arsenal.towers
                  if kind not in world.perks.locked},
        "boulders": [{"tile": list(tile), "worth": {kind: _worth(world, kind, tile)
                                                   for kind in location.arsenal.towers
                                                   if kind not in world.perks.locked}}
                     for tile in sorted(level.boulders)],
        "clear": [BALANCE.income_unit() * n for n in range(1, len(level.boulders) + 1)],
        "monsters": {kind: monster_table(world, kind) for kind in kinds},
        "curses": {c.value: {"name": s.name, "duration": s.duration, "radius": s.radius, "blurb": s.blurb}
                   for c, s in CURSES.items()},
        "spells": {key: {"name": s.name, "aim": s.aim, "blurb": s.blurb, "radius": s.radius, "delay": s.delay,
                         "lasting": s.lasting, "recharge": s.recharge}
                   for key, s in SPELLS.items()
                   if key in location.arsenal.spells and key not in world.perks.locked},
        "gate": {"life": world.gate_life, "blurb": "Bars an arch: walkers must break it; flyers pass over."}
        if location.arsenal.gates else None,
        "breach": None if world.breach_spec is None else breach_table(world, breach_claim),
        "loadout": list(world.loadout.equipped),
        "state": state(world),
    }


def tower_table(world: World, kind: str) -> dict:
    t = TOWERS[kind]
    return {"name": t.name, "element": t.element.value, "attack": t.attack, "blurb": t.blurb,
            "bolt_speed": t.bolt_speed,
            "levels": [{"cost": lv.cost, "damage": lv.damage, "rate": lv.rate, "range": lv.range,
                        "splash": lv.splash, "chains": lv.chains, "chill": lv.chill, "chill_time": lv.chill_time,
                        "poison": lv.poison, "poison_time": lv.poison_time}
                       for lv in world.tower_levels[kind]]}


def monster_table(world: World, kind: str) -> dict:
    m = MONSTERS[kind]
    leader = None
    if m.leader is not None:
        leader = {"curses": [c.value for c in m.leader.curses], "cast_range": m.leader.cast_range,
                  "channel": m.leader.channel, "mark": m.leader.mark, "raises": m.leader.raises,
                  "widen": m.leader.widen}
    return {"name": m.name, "hp": m.hp, "speed": m.speed, "bounty": m.bounty, "lives": m.lives, "size": m.size,
            "flying": m.flying, "movement": m.movement, "armor": m.armor,
            "protected": [e.value for e in m.protected], "vulnerable": [e.value for e in m.vulnerable],
            "boss": m.boss, "hits": hits(world, m), "leader": leader}


def worth_table(world: World, kind: str) -> dict:
    """Every buildable cell's worth to a tower kind, and every boulder's would-be worth: without gates, and
    with each gate (every map has at most one, so that covers every state of the gates)."""
    bare = worth.worth_map(world.level, world.waves, kind)
    return {"reach": TOWERS[kind].levels[0].range, "bare": _cells(bare),
            "gates": [{"door": i, "cells": _cells(worth.worth_map(world.level, world.waves, kind, built=frozenset({i})))}
                      for i in range(len(world.level.doors))]}


def _cells(found: dict[tuple[int, int], float]) -> dict[str, float]:
    return {f"{x},{y}": round(v, 2) for (x, y), v in sorted(found.items())}


def _worth(world: World, kind: str, tile: tuple[int, int]) -> float:
    return round(worth.worth_map(world.level, world.waves, kind).get(tile, 0.0), 2)


def hits(world: World, kind: MonsterKind) -> dict[str, list[int]]:
    """The hit each rank of every tower offered here that strikes blows deals this kind, as the monster feels it
    (its armor and tags, no other factor): the hover's table, by the simulation's own reckoning."""
    out = {}
    for key in world.arsenal.towers:
        if key in world.perks.locked:
            continue
        tower = TOWERS[key]
        if tower.attack not in HITLESS:
            out[key] = [felt_hit(lv.damage, tower.element, kind) for lv in world.tower_levels[key]]
    return out


def breach_table(world: World, claim: str | None) -> dict:
    spec = world.breach_spec
    assert spec is not None
    return {"name": spec.name, "after_wave": spec.after_wave, "elite_name": spec.elite_name,
            "elite": {"kind": spec.elite.kind, "count": spec.elite.count},
            "pack": [{"kind": g.kind, "count": g.count} for g in spec.pack], "claimed": claim, "blurb": spec.blurb}
