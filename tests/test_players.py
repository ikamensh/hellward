"""Whole defences, played by the scripted players through a person's hands."""

import random
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from hellward.sim import planner
from hellward.sim.campaign import DIFFICULTIES, LOCATIONS, NORMAL, g
from hellward.sim.content import Wave
from hellward.sim.model import SIM_DT, World
from hellward.sim.players import PLAYERS
from hellward.sim.players.adaptive import ORDERS, Adaptive
from hellward.sim.players.hands import Hands, defend
from hellward.sim.players.planned import PLANS, load
from hellward.sim.players.warden import fingerprint, load_plans
from hellward.sim.skills import SKILLS, can_learn, check, cost

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import plan_player  # noqa: E402


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_the_ordinary_player_defends_every_location_to_its_end_against_smart_leaders(key):
    location = LOCATIONS[key]
    world, record = defend(location, NORMAL, PLAYERS["ordinary"](1), seed=1, sigils=0, planner=planner.smart)
    assert world.outcome in ("victory", "defeat")
    assert world.outcome == "defeat" or world.wave == len(location.waves) - 1
    assert world.kills > 30
    assert record.chants >= record.landed > 0


def test_the_warden_holds_tristram_with_every_life():
    world, record = defend(LOCATIONS["tristram"], NORMAL, PLAYERS["warden"](1), seed=1, sigils=0, planner=planner.smart)
    assert world.outcome == "victory"
    assert world.lives == 20
    assert record.landed > 0


def test_every_stored_warden_plan_is_for_todays_map_and_its_sigils():
    """A plan searched on a map that has changed since is not played: search it again (tools/warden_plans.py)."""
    for key, plan in load_plans().items():
        name, _, sigils = key.split("/")
        location = LOCATIONS[name]
        assert plan.map == fingerprint(location), key
        assert cost(plan.skills) <= int(sigils), key
        assert all(s.kind in location.arsenal.towers for s in plan.steps if s.what == "build"), key


def test_a_leaders_sign_reaches_a_player_only_a_persons_reaction_later():
    pack = Wave((g("skeleton", 4), g("priest", 2, 4.0, start=1.0)), 10)
    world = World(replace(LOCATIONS["graveyard"], waves=(pack,), wave_names=("pack",)), seed=3, planner=planner.smart)
    hands = Hands(world, react=0.6)
    world.gold = 1000
    world.build("pyre", (7, 4))
    world.call_wave()
    seen_at = {}
    signed_at = {}
    stood = {}
    while world.outcome is None and world.time < 60 and len(seen_at) < 3:
        world.step(SIM_DT)
        for e in world.events:
            if e[0] in ("ponder", "chant"):
                signed_at.setdefault((e[1], e[0]), world.time)
                stood[(e[1], e[0])] = world.position(world.monster(e[1]))
        hands.observe(world.events)
        world.events.clear()
        for sign in hands.threats():
            seen_at.setdefault((sign.leader, sign.kind), world.time)
            assert sign.at == stood[(sign.leader, sign.kind)]   # aimed where it stood, not where it walks now
    assert seen_at
    for key, seen in seen_at.items():
        assert seen >= signed_at[key] + 0.6 - 1e-6


def test_the_record_tells_a_broken_chant_from_a_broken_pondering():
    """Chants broken are counted among the chants begun: a pondering a spell breaks never became one."""
    pack = Wave((g("priest", 2, 3.0),), 10)
    world = World(replace(LOCATIONS["catacombs"], waves=(pack,), wave_names=("pack",)), seed=3, planner=planner.smart)
    hands = Hands(world, react=0.6)
    world.gold = 1000
    world.build("pyre", (5, 5))
    world.call_wave()
    smitten: dict[str, int] = {}
    while len(smitten) < 2:
        world.step(SIM_DT)
        signs = [(e[0], e[1]) for e in world.events if e[0] in ("ponder", "chant")]
        hands.observe(world.events)
        world.events.clear()
        for kind, leader in signs:
            if kind not in smitten and leader not in smitten.values():
                world.mana = 100
                world.smite(leader)
                smitten[kind] = leader
        assert world.time < 60
    world.step(SIM_DT)
    hands.observe(world.events)
    assert hands.record.broken == 2
    assert hands.record.broken_chants == 1 <= hands.record.chants


def test_a_defence_still_undecided_at_the_limit_is_an_error():
    with pytest.raises(RuntimeError, match="undecided"):
        defend(LOCATIONS["tristram"], NORMAL, PLAYERS["ordinary"](1), seed=1, sigils=0, planner=None, limit=5.0)


FORBIDDEN = (".asking", ".ask_left", ".chant_", ".cooldown", "planner", ".clone(", ".forced", ".rng", "decide(", "rollout(")


@pytest.mark.parametrize("path", sorted((Path(__file__).parent.parent / "hellward/sim/players").glob("*.py")),
                         ids=lambda p: p.name)
def test_a_player_reads_no_leaders_mind_and_no_future(path):
    """A person sees the dots and the beam, not a leader's planner, cooldown or chant clock, and cannot copy the world."""
    if path.name == "hands.py":
        return   # the harness itself reads the events a person would see
    source = path.read_text()
    assert not [word for word in FORBIDDEN if word in source]


def test_the_planned_player_holds_tristram_with_its_searched_build():
    world, _ = defend(LOCATIONS["tristram"], NORMAL, PLAYERS["planned"](1), seed=1, sigils=0, planner=planner.smart)
    assert world.outcome == "victory"
    assert world.lives >= 18


def test_the_adaptive_player_holds_tristram():
    world, record = defend(LOCATIONS["tristram"], NORMAL, PLAYERS["adaptive"](1), seed=1, sigils=0, planner=planner.smart)
    assert world.outcome == "victory"
    assert world.lives >= 18


def test_the_apprentice_holds_tristram():
    world, _ = defend(LOCATIONS["tristram"], NORMAL, PLAYERS["apprentice"](1), seed=1, sigils=0, planner=planner.smart)
    assert world.outcome == "victory"


def assert_fits(plan, location):
    assert set(plan.skills) <= set(SKILLS)
    assert len(plan.calls) == len(location.waves)
    built = set()
    ranks = {}
    for step in plan.steps:
        if step[0] == "build":
            assert step[1] in location.arsenal.towers
            assert location.level.buildable(*step[2]) and step[2] not in built
            built.add(step[2])
        elif step[0] == "rank":
            assert step[1] in built
            ranks[step[1]] = ranks.get(step[1], 0) + 1
            assert ranks[step[1]] <= 2
        else:
            assert location.arsenal.gates and 0 <= step[1] < len(location.level.doors)


@pytest.mark.parametrize("path", sorted(PLANS.glob("*-*.json")), ids=lambda p: p.stem)   # the planned player's own
def test_every_stored_plan_fits_its_location(path):
    """A plan found for an older map or arsenal would build nowhere; the player would stand idle."""
    key, difficulty = path.stem.split("-")
    assert difficulty in DIFFICULTIES
    assert_fits(load(key, difficulty), LOCATIONS[key])


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_the_plan_search_only_ever_makes_plans_that_fit(key):
    location = LOCATIONS[key]
    rng = random.Random(key)
    tiles = plan_player.ranked_tiles(location, 3.0, 3.0)[:plan_player.TOP_TILES]
    for plan in plan_player.first_plans(location):
        for _ in range(60):
            plan = plan_player.mutate(plan, location, rng, tiles)
            assert_fits(plan, location)


@pytest.mark.parametrize("order", ["", *ORDERS])
def test_the_adaptive_player_learns_within_its_sigils_and_the_tree(order):
    """Every themed order, and the planned one (empty), buys a set the tree allows, and leaves no sigil it could
    still spend, at every budget and place."""
    for location in LOCATIONS.values():
        for difficulty in DIFFICULTIES.values():
            for sigils in range(0, 37):
                learned = Adaptive(order).skills(location, difficulty, sigils)
                check(learned)
                assert cost(learned) <= sigils
                assert not [key for key in SKILLS if can_learn(learned, key, sigils)]   # nothing left it could buy
