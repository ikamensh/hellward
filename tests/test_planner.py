"""The leaders' choice of curse: it reads resistances, stays in reach and beats the naive policies."""

import statistics

from hellward.sim import planner
from hellward.sim.autoplay import Defender
from hellward.sim.content import Group, Wave
from hellward.sim.model import SIM_DT, World


def skeleton_pack() -> World:
    """Skeletons walking the first corridor with a shaman behind them, past a plague totem and a pyre."""
    world = World(waves=(Wave((Group("skeleton", 6, 0.6), Group("shaman", 1, 1, start=3.0)), 10),))
    world.gold = 1000
    world.build("plague", (2, 3))   # right beside the shaman's path: the nearest tower
    world.build("pyre", (6, 1))     # further off, over the skeletons' heads
    world.call_wave()
    while world.time < 5.5:
        world.step()
    return world


def shaman(world: World) -> int:
    return next(m.id for m in world.monsters if m.kind.key == "shaman")


def test_a_leader_leaves_alone_a_tower_its_pack_is_immune_to():
    world = skeleton_pack()
    plague = next(t.id for t in world.towers.values() if t.kind.key == "plague")
    pyre = next(t.id for t in world.towers.values() if t.kind.key == "pyre")
    assert planner.nearest(world, shaman(world)).result().cast.tower == plague   # the naive choice
    decision = planner.decide(world, shaman(world), timing=False)
    assert decision.cast.tower == pyre
    assert decision.cast.gain > 0


def test_the_choice_is_a_pure_function_of_the_world():
    world = skeleton_pack()
    first = planner.decide(world, shaman(world))
    again = planner.decide(world.clone(), shaman(world))
    assert first == again


def test_every_considered_tower_is_within_reach_when_the_chant_ends():
    world = skeleton_pack()
    world.gold = 5000
    for tile in ((12, 2), (20, 6), (22, 11), (10, 9)):
        world.build("storm", tile)
    leader = world.monster(shaman(world))
    towers = {t.id for t in planner.reachable(world, leader)}
    far = {t.id for t in world.towers.values() if t.tile in ((12, 2), (20, 6), (22, 11), (10, 9))}
    assert towers and not towers & far
    assert all(o.tower in towers for o in planner.decide(world, leader.id).options)


def test_smart_curses_are_close_to_the_best_and_beat_the_naive_ones():
    """Property: at real decision moments, the rollout choice keeps most of the best possible gain.

    The truth here is every option played out at the game's own step for longer than the planner looks.
    """
    found: list[tuple[World, int]] = []

    def recorder(world: World, leader_id: int) -> planner.Inline:
        if len(found) < 6 and len(planner.candidates(world, world.monster(leader_id))) >= 3:
            found.append((world.clone(), leader_id))
        return planner.smart(world, leader_id)

    world = World(seed=2, planner=recorder)
    world.lives = 10_000
    defender = Defender()
    while len(found) < 6 and world.time < 1500:
        defender.act(world, SIM_DT)
        world.step(SIM_DT)
        world.events.clear()
    assert len(found) == 6
    shares = {"smart": [], "nearest": []}
    for moment, leader_id in found:
        options = planner.candidates(moment, moment.monster(leader_id))
        base = planner.rollout(moment, leader_id, None, 14.0, SIM_DT)
        truth = {(o.curse, o.tower): planner.rollout(moment, leader_id, o, 14.0, SIM_DT) - base for o in options}
        best = max(truth.values())
        if best <= 1:
            continue
        smart = planner.decide(moment, leader_id, timing=False)
        pick = smart.cast or smart.options[0]
        shares["smart"].append(max(0.0, truth[(pick.curse, pick.tower)]) / best)
        naive = planner.nearest(moment, leader_id).result().cast
        shares["nearest"].append(max(0.0, truth[(naive.curse, naive.tower)]) / best)
    assert shares["smart"]
    assert statistics.mean(shares["smart"]) >= 0.85
    assert statistics.mean(shares["smart"]) > statistics.mean(shares["nearest"])
