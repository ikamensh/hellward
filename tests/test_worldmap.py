"""The world map: the lantern's trails between the places, and the size of the picture."""

from hellward.art import worldmap
from hellward.art.rig import DENSITY
from hellward.sim.campaign import ACTS

ORDER = ACTS[1]   # the painted map is Act I's; Act II's map is to come


def test_every_trail_runs_from_its_place_to_the_next_and_back_again():
    """Property: each trail starts and ends at its anchors, and reads the same backwards."""
    for a, b in zip(ORDER, ORDER[1:]):
        forth, back = worldmap.trail(a, b, act=1), worldmap.trail(b, a, act=1)
        assert forth[0] == worldmap.ANCHORS[1][a]
        assert forth[-1] == worldmap.ANCHORS[1][b]
        assert back == tuple(reversed(forth))


def test_every_place_and_every_trail_bend_stays_on_the_map_above_the_button_bar():
    """Property: no anchor or trail point hides under the buttons or off the screen."""
    points = list(worldmap.ANCHORS[1].values())
    for a, b in zip(ORDER, ORDER[1:]):
        points.extend(worldmap.trail(a, b, act=1))
    assert points
    for x, y in points:
        assert 0 <= x <= worldmap.WIDTH
        assert 0 <= y < 740


def test_the_stand_in_covers_the_whole_screen_at_the_art_density():
    assert worldmap.stand_in(act=1).size == (worldmap.WIDTH * DENSITY, worldmap.HEIGHT * DENSITY)
