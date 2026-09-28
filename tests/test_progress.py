"""The campaign's progress: fresh lanterns, sigils from defences, learned skills, the way down, and saving."""

import pytest
from saga2d import Game

from hellward.sim import campaign
from hellward.sim.items import PATTERNS
from hellward.sim.skills import SKILLS, can_learn
from hellward.ui.progress import BREACH_SITES, Progress


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
        assert progress.learn("adept_fire")
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


def test_a_save_listing_a_removed_mastery_loads_with_it_forgotten(game):
    game.save_manager.save("campaign", {"won": {"tristram": 3}, "learned": ["fire_mastery", "adept_fire"],
                                        "at": "tristram"}, "Progress", summary={})
    progress = Progress.load(game)
    assert progress.learned == frozenset({"adept_fire"})
    assert progress.free == 2


def test_the_save_ilya_played_before_the_new_tree_loads(game):
    """His 2026-09-26 save: Blaze stays learned in the file, but the new tree puts Master of Fire above it, which
    the save does not have. Every skill that lost a step above it goes; the save loads and its sigils are free."""
    game.save_manager.save("campaign", {
        "won": {"normal": {k: 3 for k in ("tristram", "graveyard", "cathedral", "catacombs", "caves", "hells_gate")},
                "hell": {}},
        "learned": ["blaze", "chain_lightning", "cold_mastery", "fire_ball", "fire_mastery", "glacial_spike",
                    "lightning_mastery", "poison_mastery", "warmth"],
        "at": "hells_gate", "difficulty": "hell"}, "Progress", summary={})
    progress = Progress.load(game)
    assert progress.learned == frozenset({"warmth"})
    assert progress.free == 17


def test_a_save_whose_skills_now_cost_more_than_its_sigils_loads_with_none_owed(game):
    """Property: whatever a save lists, the loaded tree never spends more sigils than were won, and what it keeps
    still has every skill above it."""
    from hellward.sim.skills import SKILLS, check
    game.save_manager.save("campaign", {"won": {"tristram": 3}, "learned": sorted(SKILLS), "at": "tristram"},
                           "Progress", summary={})
    progress = Progress.load(game)
    assert progress.free >= 0 and progress.learned
    check(progress.learned)


def test_an_old_save_with_a_difficulty_loads_its_normal_sigils(game):
    game.save_manager.save("campaign", {"won": {"normal": {"tristram": 3}, "hell": {}},
                                        "learned": [], "at": "tristram", "difficulty": "hell"},
                           "Progress", summary={})
    assert Progress.load(game).won == {"tristram": 3}


def test_learning_needs_its_prerequisite_and_free_sigils_and_unlearning_returns_them_all(game):
    progress = Progress.load(game)
    assert not can_learn(progress.learned, "adept_fire", progress.sigils)
    assert not progress.learn("adept_fire")   # no sigils yet
    assert not progress.learn("fire_ball")   # its prerequisite is missing too
    assert progress.record("tristram", "victory", 18) == 3
    assert not can_learn(progress.learned, "fire_ball", progress.sigils)
    assert not progress.learn("fire_ball")   # still needs Adept of Fire first
    assert can_learn(progress.learned, "adept_fire", progress.sigils)
    assert progress.learn("adept_fire")
    assert progress.free == progress.sigils - SKILLS["adept_fire"].cost
    assert can_learn(progress.learned, "master_fire", progress.sigils)
    assert not progress.learn("fire_ball")   # its area attack opens much later
    assert progress.learn("warmth")
    assert progress.learn("adept_cold")
    assert progress.free == 0
    assert not progress.learn("holy_shield")   # no sigils left
    assert not progress.learn("master_fire")   # one sigil short of the next tier
    earned = progress.sigils
    progress.unlearn_all()
    assert progress.learned == frozenset()
    assert progress.free == earned


def test_the_way_down_opens_one_location_at_a_time_and_the_lantern_walks_it(game):
    """Property: every location but the first opens exactly once the one before it is held."""
    progress = Progress.load(game)
    assert progress.opened(campaign.LOCATIONS[campaign.ORDER[0]])
    assert not progress.opened(campaign.LOCATIONS[campaign.ORDER[1]])
    assert progress.next_location(1) == campaign.LOCATIONS[campaign.ORDER[0]]
    for i, key in enumerate(campaign.ORDER):
        act = campaign.LOCATIONS[key].act
        assert progress.next_location(act) == campaign.LOCATIONS[key]
        assert progress.opened(campaign.LOCATIONS[key])
        if i + 1 < len(campaign.ORDER):
            assert not progress.opened(campaign.LOCATIONS[campaign.ORDER[i + 1]])
        progress.record(key, "victory", 18)
    assert progress.next_location(1) is None and progress.next_location(2) is None


def test_area_skills_wait_for_the_late_campaign(game):
    progress = Progress.load(game)
    for key in campaign.ORDER[:6]:
        progress.record(key, "victory", 18)
    assert progress.learn("adept_fire")
    assert progress.learn("master_fire")
    assert not progress.learn("fire_ball")
    for key in campaign.ORDER[6:8]:
        progress.record(key, "victory", 18)
    assert progress.learn("fire_ball")


def test_a_victory_banks_only_the_improvement_in_salvage_alongside_sigils(game):
    """Replays improve a location's persistent yield without farming it repeatedly."""
    progress = Progress.load(game)
    first = progress.record_result("tristram", "victory", 18, salvage=2)
    assert (first.sigils, first.salvage) == (3, 2)
    assert Progress.load(game).salvage == 2

    worse = progress.record_result("tristram", "victory", 5, salvage=1)
    assert (worse.sigils, worse.salvage) == (0, 0)
    better = progress.record_result("tristram", "victory", 5, salvage=4)
    assert (better.sigils, better.salvage) == (0, 2)
    lost = progress.record_result("tristram", "defeat", 20, salvage=9)
    assert (lost.sigils, lost.salvage) == (0, 0)
    again = Progress.load(game)
    assert again.salvage == 4 and again.salvage_best == {"tristram": 4}
    assert again.won == {"tristram": 3}


def test_a_breach_trophy_is_claimed_once_only_after_all_side_enemies_die_and_the_defence_wins(game):
    """An opened breach and a fallen sanctuary cannot grant a persistent trophy."""
    progress = Progress.load(game)
    progress.record_result("graveyard", "defeat", 0, breach_mode="trophy", breach_cleared=True)
    progress.record_result("graveyard", "victory", 18, breach_mode="trophy", breach_cleared=False)
    assert progress.trophies == frozenset()
    assert progress.breach_claims == {}

    gained = progress.record_result("graveyard", "victory", 18, breach_mode="trophy", breach_cleared=True)
    assert gained.trophy == "graveyard"
    assert progress.trophies == frozenset({"graveyard"})
    assert progress.breach_claims == {"graveyard": "trophy"}
    assert progress.record_result("graveyard", "victory", 18, breach_mode="trophy", breach_cleared=True).trophy is None
    assert Progress.load(game).trophies == frozenset({"graveyard"})


def test_a_successful_cash_breach_forfeits_its_one_trophy_but_cash_can_be_replayed(game):
    """Choosing help now commits the future reward only after a victorious clear."""
    progress = Progress.load(game)
    progress.record_result("catacombs", "victory", 18, breach_mode="cash", breach_cleared=True)
    assert progress.breach_claims == {"catacombs": "cash"}
    assert progress.trophies == frozenset()
    assert progress.record_result("catacombs", "victory", 18, breach_mode="trophy", breach_cleared=True).trophy is None
    assert Progress.load(game).breach_claims == {"catacombs": "cash"}


def test_declining_a_breach_saves_the_defence_without_claiming_the_side_reward(game):
    progress = Progress.load(game)
    gained = progress.record_result("graveyard", "victory", 18, salvage=2, breach_mode="decline")
    assert (gained.sigils, gained.salvage, gained.trophy) == (3, 2, None)
    again = Progress.load(game)
    assert again.won == {"graveyard": 3}
    assert again.breach_claims == {}
    with pytest.raises(ValueError, match="cleared breach"):
        again.record_result("graveyard", "victory", 18, breach_mode="decline", breach_cleared=True)


def test_forged_patterns_are_owned_once_and_equipped_one_per_family(game):
    """The forge pays a permanent price; changing the Arrow loadout replaces its earlier pattern."""
    progress = Progress.load(game)
    with pytest.raises(ValueError, match="location"):
        progress.forge("honed_string")
    progress.record_result("tristram", "victory", 18, salvage=2)
    with pytest.raises(ValueError, match="salvage"):
        progress.forge("honed_string")
    progress.record_result("tristram", "victory", 18, salvage=20)
    assert progress.forge("honed_string") == PATTERNS["honed_string"]
    assert progress.salvage == 17 and progress.patterns == frozenset({"honed_string"})
    with pytest.raises(ValueError, match="already forged"):
        progress.forge("honed_string")
    with pytest.raises(ValueError, match="not owned"):
        progress.equip("laminated_limbs")

    progress.equip("honed_string")
    assert progress.loadout.for_family("arrow") == PATTERNS["honed_string"]
    progress.forge("laminated_limbs")
    progress.equip("laminated_limbs")
    assert progress.loadout.equipped == ("laminated_limbs",)
    assert progress.patterns == frozenset({"honed_string", "laminated_limbs"})
    progress.unequip("arrow")
    assert progress.loadout.equipped == ()
    reloaded = Progress.load(game)
    assert reloaded.salvage == 11 and reloaded.patterns == progress.patterns
    assert reloaded.loadout.equipped == ()


def test_six_breach_trophies_can_be_spent_once_across_the_late_recipes(game):
    """The high-end recipes compete for the campaign's finite named trophies."""
    sites = ("graveyard", "catacombs", "hells_gate", "spider_forest", "drowned_city", "temple")
    assert BREACH_SITES == frozenset(sites)
    progress = Progress.load(game)
    for key in campaign.ORDER:
        progress.record_result(key, "victory", 18, salvage=40 if key == "tristram" else 0,
                               breach_mode="trophy" if key in sites else None, breach_cleared=key in sites)
    assert progress.trophies == frozenset(sites)
    for key in sites:
        assert progress.record_result(key, "victory", 18, breach_mode="trophy", breach_cleared=True).trophy is None

    progress.forge("blast_chamber")
    progress.forge("forked_coil")
    progress.equip("blast_chamber")
    progress.equip("forked_coil")
    assert progress.salvage == 23
    assert progress.trophies == frozenset({"temple"})
    assert progress.loadout.equipped == ("blast_chamber", "forked_coil")
    with pytest.raises(ValueError, match="trophies"):
        progress.forge("execution_bow")
    reloaded = Progress.load(game)
    assert reloaded.patterns == frozenset({"blast_chamber", "forked_coil"})
    assert reloaded.trophies == frozenset({"temple"})
    assert reloaded.loadout == progress.loadout


def test_a_victory_writes_all_rewards_in_one_save(game, monkeypatch):
    """Sigils, salvage, and a trophy are committed at the same outcome boundary."""
    progress = Progress.load(game)
    original = game.save_manager.save
    saves = 0

    def counted(*args, **kwargs):
        nonlocal saves
        saves += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(game.save_manager, "save", counted)
    progress.record_result("graveyard", "victory", 18, salvage=2, breach_mode="trophy", breach_cleared=True)
    assert saves == 1
    reloaded = Progress.load(game)
    assert reloaded.won == {"graveyard": 3}
    assert reloaded.salvage == 2
    assert reloaded.trophies == frozenset({"graveyard"})


def test_invalid_breach_receipt_changes_nothing(game):
    """A malformed optional reward must fail before sigils or salvage are granted."""
    progress = Progress.load(game)
    with pytest.raises(ValueError, match="no breach"):
        progress.record_result("tristram", "victory", 18, salvage=5,
                               breach_mode="trophy", breach_cleared=True)
    assert progress.won == {} and progress.salvage == 0 and progress.breach_claims == {}
    assert game.save_manager.load("campaign") is None


def test_a_saved_loadout_cannot_equip_a_pattern_that_is_not_owned(game):
    """Ownership is checked when a save is loaded, before a defence can use its modifiers."""
    game.save_manager.save("campaign", {"won": {}, "learned": [], "at": "tristram",
                                        "patterns": ["honed_string"], "loadout": ["laminated_limbs"]},
                           "Progress", summary={})
    with pytest.raises(ValueError, match="not owned"):
        Progress.load(game)


def test_a_saved_pattern_must_still_exist_in_the_recipe_catalog(game):
    """A removed recipe is reported clearly instead of silently granting a ghost item."""
    game.save_manager.save("campaign", {"won": {}, "learned": [], "at": "tristram",
                                        "patterns": ["missing_pattern"], "loadout": []},
                           "Progress", summary={})
    with pytest.raises(ValueError, match="Unknown tower pattern"):
        Progress.load(game)
