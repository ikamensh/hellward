"""Targeting strategies: each aim chooses its monster, taught in the forge, set per tower."""

from dataclasses import replace

import pytest

from hellward.server.battle import Battle
from hellward.server.campaign import Campaign, Refusal
from hellward.sim import campaign, planner
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import SPELLS, TOWERS, Group, Wave
from hellward.sim.level import Level
from hellward.sim.model import Refused, World
from hellward.sim.modes import MODES
from hellward.sim.players.adaptive import Adaptive
from hellward.sim.players.ghost import issue
from hellward.sim.players.hands import Hands


def campaign_at(data):
    return Campaign(data, planner=planner.smart, demo_player=Adaptive, seed=3)

ARENA = Level("Strategy field", 25, 14,
              ((0, 2), (9, 2), (9, 8), (19, 8), (19, 11), (24, 11)), ((9, 5),))


def arena() -> World:
    waves = (Wave((Group("fallen", 1, 0.1), Group("zombie", 1, 0.1), Group("drowned", 1, 0.1),
                   Group("skeleton", 1, 0.1), Group("bat", 1, 0.1)), 10),)
    arsenal = replace(campaign.CATHEDRAL.arsenal, towers=tuple(TOWERS), spells=tuple(SPELLS), gates=True)
    location = replace(campaign.CATHEDRAL, level=ARENA, arsenal=arsenal, waves=waves, wave_names=("pack",))
    world = World(location, seed=7)
    world.gold = 10000
    return world


def five_in_reach() -> tuple[World, int]:
    """One arrow with five monsters in its reach, each aim's winner a different one: the fallen
    foremost, the zombie rearmost, the drowned strongest, the skeleton weakest, the bat swiftest."""
    world = arena()
    tile = next((x, y) for y in range(14) for x in range(25)
                if world.buildable(x, y) and (x, y) != (11, 3))
    tower = world.build("arrow", tile)
    world.call_wave()
    while len(world.monsters) < 5:
        world.step()
        assert world.time < 60
    spans = world.level.coverage(tile, tower.stats.range)
    lo, hi = max(spans, key=lambda span: span[1] - span[0])
    by_kind = {m.kind.key: m for m in world.monsters}
    place = {"fallen": (0.95, 20.0), "zombie": (0.05, 15.0), "drowned": (0.6, 50.0),
             "skeleton": (0.4, 5.0), "bat": (0.75, 10.0)}
    for kind, (at, hp) in place.items():
        by_kind[kind].s = lo + (hi - lo) * at
        by_kind[kind].hp = hp
    assert all(world._tower_covers(tower, m, spans, tower.stats.range) for m in world.monsters)
    return world, tower.id


def fired_at(world: World, tower_id: int) -> int:
    """The monster one shot strikes: the cooldown spent, one step, the bolt's target."""
    world.towers[tower_id].cooldown = 0.0
    world.events.clear()
    world.step()
    bolts = [e for e in world.events if e[0] == "bolt"]
    assert len(bolts) == 1
    return bolts[0][1].target


def test_each_strategy_strikes_its_monster():
    world, tower_id = five_in_reach()
    by_kind = {m.kind.key: m.id for m in world.monsters}
    want = {"first": by_kind["fallen"], "strong": by_kind["drowned"], "weak": by_kind["skeleton"],
            "fast": by_kind["bat"], "last": by_kind["zombie"]}
    assert len(set(want.values())) == 5   # the field tells every aim apart
    for mode, target in want.items():
        twin = world.clone()
        twin.record = True   # a clone looks ahead silently: this one must show its shot
        twin.set_mode(tower_id, mode)
        assert fired_at(twin, tower_id) == target, mode


def test_an_unknown_strategy_is_refused_and_a_taught_one_announced():
    world = arena()
    tile = next((x, y) for y in range(14) for x in range(25) if world.buildable(x, y))
    tower = world.build("arrow", tile)
    assert tower.mode == "first"
    with pytest.raises(Refused, match="No strategy"):
        world.set_mode(tower.id, "cleverest")
    world.set_mode(tower.id, "strong")
    assert ("mode", tower.id, "strong") in world.events
    assert world.clone().towers[tower.id].mode == "strong"


def test_strategies_are_taught_for_salvage_and_kept(tmp_path):
    camp = campaign_at(tmp_path / "data")
    view = camp.forge_view()
    assert [s["key"] for s in view["strategies"]] == ["strong", "weak", "fast", "last", "attune"]
    assert all(s["label"] == "Need more salvage" for s in view["strategies"])
    with pytest.raises(Refusal, match="salvage"):
        camp.forge("strong")
    camp.progress.salvage = 10
    view = camp.forge("strong")
    assert "strong" in camp.progress.modes
    assert camp.progress.salvage == 10 - MODES["strong"].salvage_cost
    assert next(s for s in view["strategies"] if s["key"] == "strong")["owned"]
    with pytest.raises(Refusal, match="already taught"):
        camp.forge("strong")
    again = campaign_at(tmp_path / "data")
    assert "strong" in again.progress.modes   # the teaching survives a restart


def test_a_battle_teaches_only_what_the_profile_knows(tmp_path):
    camp = campaign_at(tmp_path / "data")
    camp.progress.salvage = 10
    camp.forge("weak")
    battle = Battle(LOCATIONS["tristram"], planner=None, modes=camp.progress.modes)
    assert [m["key"] for m in battle.start()["modes"]] == ["first", "weak"]
    battle.world.gold = 10000
    tile = next((x, y) for y in range(20) for x in range(30) if battle.world.buildable(x, y))
    battle.order("build", {"kind": "arrow", "tile": list(tile)})
    tower = battle.world.tower_at(tile).id
    why, _ = battle.order("set_mode", {"tower": tower, "mode": "strong"})
    assert why is not None and "not taught" in why
    why, frame = battle.order("set_mode", {"tower": tower, "mode": "weak"})
    assert why is None and frame is not None
    assert battle.world.towers[tower].mode == "weak"
    assert ["set_mode", [tile[0], tile[1]], "weak"] == battle.commands[-1][1:]


def test_a_taught_tower_replays_its_strategy():
    world = arena()
    tile = next((x, y) for y in range(14) for x in range(25) if world.buildable(x, y))
    world.build("arrow", tile)
    hands = Hands(world, 0.0)
    assert issue(world, hands, "set_mode", (list(tile), "fast"))
    assert world.tower_at(tile).mode == "fast"
    assert not issue(world, hands, "set_mode", ([0, 0], "fast"))   # no tower there yet: retried later
