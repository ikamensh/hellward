"""Whole defences, played by the scripted defender."""

from hellward.sim import planner
from hellward.sim.autoplay import play
from hellward.sim.content import WAVES
from hellward.sim.model import World


def test_a_scripted_defence_against_smart_leaders_plays_to_its_end():
    world = play(World(seed=1, planner=planner.smart))
    assert world.outcome in ("victory", "defeat")
    assert world.outcome == "defeat" or world.wave == len(WAVES) - 1
    assert world.kills > 150
