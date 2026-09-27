"""The world map: the lantern's trails between the places, and the size of the picture."""

from hellward.art import worldmap
from hellward.art.rig import DENSITY
from hellward.sim.campaign import ACTS


def test_every_trail_runs_from_its_place_to_the_next_and_back_again():
    """Property: each trail starts and ends at its anchors, and reads the same backwards."""
    for act in (1, 2):
        order = ACTS[act]
        for a, b in zip(order, order[1:]):
            forth, back = worldmap.trail(a, b, act=act), worldmap.trail(b, a, act=act)
            assert forth[0] == worldmap.ANCHORS[act][a]
            assert forth[-1] == worldmap.ANCHORS[act][b]
            assert back == tuple(reversed(forth))


def test_every_place_and_every_trail_bend_stays_on_the_map_above_the_button_bar():
    """Property: no anchor or trail point hides under the buttons or off the screen."""
    for act in (1, 2):
        order = ACTS[act]
        points = list(worldmap.ANCHORS[act].values())
        for a, b in zip(order, order[1:]):
            points.extend(worldmap.trail(a, b, act=act))
        assert points
        for x, y in points:
            assert 0 <= x <= worldmap.WIDTH
            assert 0 <= y < 740


def test_the_stand_in_covers_the_whole_screen_at_the_art_density():
    assert worldmap.stand_in(act=1).size == (worldmap.WIDTH * DENSITY, worldmap.HEIGHT * DENSITY)
    assert worldmap.stand_in(act=2).size == (worldmap.WIDTH * DENSITY, worldmap.HEIGHT * DENSITY)