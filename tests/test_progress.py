"""The campaign's progress: fresh lanterns, sigils from defences, learned skills, the way down, and saving."""

import pytest
from saga2d import Game

from hellward.sim import campaign
from hellward.sim.skills import SKILLS, can_learn
from hellward.ui.progress import Progress


@pytest.fixture
def game(tmp_path):
    g = Game("Hellward", backend="mock", resolution=(1280, 800), save_dir=tmp_path / "saves")
    yield g
    g.close()


def test_a_new_lantern_holds_nothing_learns_nothing_and_stands_at_the_top(game):
    progress = Progress.load(game)
    assert progress.sigils == 0
    assert progress.learned == frozenset()
    assert progress.at == campaign.ORDER[0]


def test_a_defence_earns_three_sigils_for_eighteen_lives_two_for_ten_one_below_and_none_for_a_fall(game):
    """Property: each life kept earns what the campaign's sigil ladder says, and a fall earns nothing."""
    progress = Progress.load(game)
    assert progress.record("tristram", "victory", 18) == 3
    assert progress.record("graveyard", "victory", 10) == 2
    assert progress.record("cathedral", "victory", 5) == 1
    assert progress.record("catacombs", "defeat", 20) == 0
    assert progress.best("catacombs") == 0


def test_a_worse_later_defence_adds_nothing_and_a_better_one_adds_only_the_difference(game):
    progress = Progress.load(game)
    assert progress.record("tristram", "victory", 18) == 3
    assert progress.record("tristram", "victory", 5) == 0
    assert progress.best("tristram") == 3
    assert progress.sigils == 3
    climbing = Progress(game=game)
    assert climbing.record("tristram", "victory", 5) == 1
    assert climbing.record("tristram", "victory", 18) == 2
    assert climbing.best("tristram") == 3
    assert climbing.sigils == 3


def test_sigils_learning_and_the_lantern_last_to_the_next_session(tmp_path):
    saves = tmp_path / "saves"
    first = Game("Hellward", backend="mock", resolution=(1280, 800), save_dir=saves)
    try:
        progress = Progress.load(first)
        assert progress.record("tristram", "victory", 18) == 3
        assert progress.learn("fire_mastery")
        progress.move("graveyard")
    finally:
        first.close()
    second = Game("Hellward", backend="mock", resolution=(1280, 800), save_dir=saves)
    try:
        again = Progress.load(second)
        assert again.won == progress.won
        assert again.learned == progress.learned
        assert again.at == progress.at
    finally:
        second.close()


def test_an_old_save_with_a_difficulty_loads_its_normal_sigils(game):
    game.save_manager.save("campaign", {"won": {"normal": {"tristram": 3}, "hell": {}},
                                        "learned": [], "at": "tristram", "difficulty": "hell"},
                           "Progress", summary={})
    assert Progress.load(game).won == {"tristram": 3}


def test_learning_needs_its_prerequisite_and_free_sigils_and_unlearning_returns_them_all(game):
    progress = Progress.load(game)
    assert not can_learn(progress.learned, "fire_mastery", progress.sigils)
    assert not progress.learn("fire_mastery")   # no sigils yet
    assert not progress.learn("fire_ball")   # its prerequisite is missing too
    assert progress.record("tristram", "victory", 18) == 3
    assert not can_learn(progress.learned, "fire_ball", progress.sigils)
    assert not progress.learn("fire_ball")   # still needs Fire Mastery first
    assert can_learn(progress.learned, "fire_mastery", progress.sigils)
    assert progress.learn("fire_mastery")
    assert progress.free == progress.sigils - SKILLS["fire_mastery"].cost
    assert can_learn(progress.learned, "fire_ball", progress.sigils)
    assert progress.learn("fire_ball")
    assert progress.free == 0
    assert not progress.learn("warmth")   # no sigils left
    assert not progress.learn("blaze")   # three sigils short of the last tier
    earned = progress.sigils
    progress.unlearn_all()
    assert progress.learned == frozenset()
    assert progress.free == earned


def test_the_way_down_opens_one_location_at_a_time_and_the_lantern_walks_it(game):
    """Property: every location but the first opens exactly once the one before it is held."""
    progress = Progress.load(game)
    assert progress.opened(campaign.LOCATIONS[campaign.ORDER[0]])
    assert not progress.opened(campaign.LOCATIONS[campaign.ORDER[1]])
    assert progress.next_location() == campaign.LOCATIONS[campaign.ORDER[0]]
    for i, key in enumerate(campaign.ORDER):
        assert progress.next_location() == campaign.LOCATIONS[key]
        assert progress.opened(campaign.LOCATIONS[key])
        if i + 1 < len(campaign.ORDER):
            assert not progress.opened(campaign.LOCATIONS[campaign.ORDER[i + 1]])
        progress.record(key, "victory", 18)
    assert progress.next_location() is None
