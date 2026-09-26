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
from hellward.sim.players.hands import Hands, defend
from hellward.sim.players.planned import PLANS, load
from hellward.sim.skills import SKILLS

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


def test_a_leaders_sign_reaches_a_player_only_a_persons_reaction_later():
    pack = Wave((g("skeleton", 4), g("priest", 2, 4.0, start=1.0)), 10)
    world = World(replace(LOCATIONS["graveyard"], waves=(pack,), wave_names=("pack",)), seed=3, planner=planner.smart)
    hands = Hands(world, react=0.6)
    world.gold = 1000
    world.build("pyre", (7, 4))
    world.call_wave()
    seen_at = {}
    signed_at = {}
    while world.outcome is None and world.time < 60 and len(seen_at) < 3:
        world.step(SIM_DT)
        for e in world.events:
            if e[0] in ("ponder", "chant"):
                signed_at.setdefault((e[1], e[0]), world.time)
        hands.observe(world.events)
        world.events.clear()
        for sign in hands.threats():
            seen_at.setdefault((sign.leader, sign.kind), world.time)
    assert seen_at
    for key, seen in seen_at.items():
        assert seen >= signed_at[key] + 0.6 - 1e-6


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


def assert_fits(plan, location):
    assert set(plan.skills) <= set(SKILLS)
    assert len(plan.calls) == len(location.waves)
    built = set()
    for step in plan.steps:
        if step[0] == "build":
            assert step[1] in location.arsenal.towers
            assert location.level.buildable(*step[2]) and step[2] not in built
            built.add(step[2])
        elif step[0] == "rank":
            assert step[1] in built
        else:
            assert location.arsenal.gates and 0 <= step[1] < len(location.level.doors)


@pytest.mark.parametrize("path", sorted(PLANS.glob("*.json")), ids=lambda p: p.stem)
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
