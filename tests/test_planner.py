"""The leaders' choice of curse: it reads resistances, stays in reach and beats the naive policies."""

import statistics
from dataclasses import replace

from hellward.sim import campaign, planner
from hellward.sim.players.hands import Hands
from hellward.sim.players.ordinary import Ordinary
from hellward.sim.content import Group, Wave
from hellward.sim.level import Level
from hellward.sim.model import SIM_DT, World
from tools.curse_quality import moments


def skeleton_pack() -> World:
    """A focused curse arena with an immune pack passing a plague totem and a Pyre."""
    pack = Wave((Group("skeleton", 6, 0.6), Group("shaman", 1, 1, start=3.0)), 10)
    level = Level("curse arena", 25, 14,
                  ((0, 2), (8, 2), (8, 6), (3, 6), (3, 11), (12, 11), (12, 4), (18, 4), (18, 10), (24, 10)),
                  ((3, 9), (12, 7), (18, 8)),
                  frozenset({(15, 1), (21, 2), (22, 6), (1, 12), (21, 12), (10, 1)}))
    arsenal = replace(campaign.CATHEDRAL.arsenal, towers=("arrow", "pyre", "storm", "plague"))
    world = World(replace(campaign.CATHEDRAL, level=level, arsenal=arsenal, waves=(pack,),
                          wave_names=("pack",), life=1.0), hardness=10.0)
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
    plague = next(t.tile for t in world.towers.values() if t.kind.key == "plague")
    pyre = next(t.tile for t in world.towers.values() if t.kind.key == "pyre")
    assert planner.nearest(world, shaman(world)).result().cast.spot == plague   # the naive choice
    decision = planner.decide(world, shaman(world), timing=False)
    assert decision.cast.spot == pyre
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
    tiles = {t.tile for t in planner.reachable(world, leader)}
    far = {t.tile for t in world.towers.values() if t.tile in ((12, 2), (20, 6), (22, 11), (10, 9))}
    assert tiles and not tiles & far
    assert all(o.spot in tiles for o in planner.decide(world, leader.id).options)


def test_smart_curses_are_close_to_the_best_and_beat_the_naive_ones():
    """Property: at real decision moments, the live planner's preferred target keeps most of the best gain.

    The truth here is every option played out at the game's own step. The live planner also judges
    whether waiting is better, so a decision to wait still exposes its best immediate target.
    """
    found: list[tuple[World, int]] = []

    def recorder(world: World, leader_id: int) -> planner.Inline:
        if len(found) < 6 and len(planner.candidates(world, world.monster(leader_id))) >= 3:
            found.append((world.clone(), leader_id))
        return planner.smart(world, leader_id)

    world = World(seed=2, planner=recorder)
    world.lives = 10_000
    defender, hands = Ordinary(), Hands(world, react=0.6)
    while len(found) < 6 and world.time < 1500:
        defender.act(hands)
        world.step(SIM_DT)
        hands.observe(world.events)
        world.events.clear()
    assert len(found) == 6
    shares = {"smart": [], "nearest": []}
    for moment, leader_id in found:
        options = planner.candidates(moment, moment.monster(leader_id))
        base = planner.rollout(moment, leader_id, None, 14.0, SIM_DT)
        truth = {(o.curse, o.spot): planner.rollout(moment, leader_id, o, 14.0, SIM_DT) - base for o in options}
        best = max(truth.values())
        if best <= 1:
            continue
        smart = planner.smart(moment, leader_id).result()
        pick = smart.cast or smart.options[0]
        shares["smart"].append(max(0.0, truth[(pick.curse, pick.spot)]) / best)
        naive = planner.nearest(moment, leader_id).result().cast
        # the naive spot may be one the candidates folded away (same towers, same curse): play it out
        naive_gain = planner.rollout(moment, leader_id, naive, 14.0, SIM_DT) - base if naive is not None else 0.0
        shares["nearest"].append(max(0.0, naive_gain) / best)
    assert shares["smart"]
    assert statistics.mean(shares["smart"]) >= 0.85
    assert statistics.mean(shares["smart"]) > statistics.mean(shares["nearest"])


def test_smart_tristram_curses_keep_most_of_the_best_gain():
    """Across real Arrow defences, the chosen curses retain the campaign quality target."""
    shares = []
    for moment, leader_id in moments(8, 3, "tristram"):
        options = planner.candidates(moment, moment.monster(leader_id))
        base = planner.rollout(moment, leader_id, None, 16.0, SIM_DT)
        gains = {(option.curse, option.spot): planner.rollout(moment, leader_id, option, 16.0, SIM_DT) - base
                 for option in options}
        best = max(gains.values())
        if best <= 1.0:
            continue
        choice = planner.smart(moment, leader_id).result()
        picked = choice.cast or choice.options[0]
        shares.append(max(0.0, gains[picked.curse, picked.spot]) / best)
    assert shares
    assert statistics.mean(shares) >= 0.85
