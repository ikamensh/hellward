"""Whole defences, played by the scripted defender."""

import pytest

from hellward.sim import planner
from hellward.sim.autoplay import play
from hellward.sim.campaign import LOCATIONS
from hellward.sim.model import World


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_a_scripted_defence_against_smart_leaders_plays_every_location_to_its_end(key):
    location = LOCATIONS[key]
    world = play(World(location, seed=1, planner=planner.smart))
    assert world.outcome in ("victory", "defeat")
    assert world.outcome == "defeat" or world.wave == len(location.waves) - 1
    assert world.kills > 30
