"""The campaign's screens on the mock backend: the descent from the title to a defence and back, sigils and
skills that last between sessions, the spells on the panel, and what a location does not offer."""

from pathlib import Path

import pytest
from saga2d import Game
from saga2d.testing import assert_text_fits

from hellward.__main__ import build
from hellward.art import worldmap
from hellward.story import STORIES
from hellward.sim import planner
from hellward.sim.campaign import ACTS, LOCATIONS, ORDER
from hellward.sim.content import CURSES, MONSTERS, SPELLS, Curse
from hellward.sim.model import Monster
from hellward.sim.players.ordinary import Ordinary
from hellward.ui import menus
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene, Silent
from hellward.ui.briefing import BriefingScene
from hellward.ui.flow import Flow
from hellward.ui.mapscreen import MapScene
from hellward.ui.progress import Progress
from hellward.ui.skilltree import SkillTreeScene
from hellward.ui.story import PrologueScene, StoryScene
from hellward.ui.title import ReckoningScene, TitleScene


@pytest.fixture(scope="module")
def cache(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("cache")


def open_game(cache: Path, saves: Path) -> tuple[Game, Flow]:
    g = Game("Hellward", backend="mock", resolution=(WIDTH, HEIGHT), asset_path=cache, save_dir=saves)
    art = build(g, cache)
    flow = Flow(g, art, sound=Silent(), planner=planner.smart, settings=menus.settings(g), progress=Progress.load(g),
                demo_player=Ordinary)
    return g, flow


@pytest.fixture
def game(cache, tmp_path):
    g, flow = open_game(cache, tmp_path / "saves")
    yield g, flow
    g.close()


def tick(g: Game, seconds: float = 1 / 30) -> None:
    for _ in range(max(1, int(seconds * 30))):
        g.tick(1 / 30)


def press(g: Game, key: str) -> None:
    g.backend.inject_key(key)
    tick(g)


def test_a_first_descent_walks_the_lantern_to_tristram_and_its_intro_names_its_host(game):
    g, flow = game
    g.push(TitleScene(flow))
    tick(g)
    press(g, "return")
    assert isinstance(g.scenes[-1], PrologueScene)   # a new campaign opens on the prologue
    press(g, "escape")
    assert isinstance(g.scenes[-1], MapScene)
    tick(g, 4)   # the lantern walks on by itself
    page = g.scenes[-1]
    assert isinstance(page, StoryScene)   # the first arrival tells Tristram's before page
    press(g, "return")   # reveal
    press(g, "return")   # on to the intro
    intro = g.scenes[-1]
    assert isinstance(intro, BriefingScene) and intro.location.key == "tristram"
    assert_text_fits(g)
    tick(g, 0.5)   # past the story page's input guard
    press(g, "return")
    battle = g.scenes[-1]
    assert isinstance(battle, BattleScene) and battle.world.location.key == "tristram"


def test_a_won_defence_earns_sigils_that_open_the_way_and_last_to_the_next_session(cache, tmp_path):
    saves = tmp_path / "saves"
    g, flow = open_game(cache, saves)
    flow.defend(LOCATIONS["tristram"])
    tick(g)
    battle = g.scenes[-1]
    battle.world.lives = 19
    battle.world.outcome = "victory"   # the fight itself is the rules' tests' business
    tick(g, 3.5)
    reckoning = g.scenes[-1]
    assert isinstance(reckoning, ReckoningScene) and reckoning.gained == 3
    tick(g, 2)
    assert reckoning.lit == 3
    assert_text_fits(g)
    press(g, "escape")
    assert isinstance(g.scenes[-1], StoryScene)   # leaving the reckoning tells the after page once
    press(g, "return")
    press(g, "return")
    assert isinstance(g.scenes[-1], MapScene)
    assert flow.progress.opened(LOCATIONS["graveyard"]) and not flow.progress.opened(LOCATIONS["cathedral"])
    g.close()
    g, flow = open_game(cache, saves)
    assert flow.progress.best("tristram") == 3 and flow.progress.sigils == 3
    g.close()


def test_a_fall_earns_nothing_and_again_returns_to_the_intro(game):
    g, flow = game
    flow.defend(LOCATIONS["tristram"])
    tick(g)
    g.scenes[-1].world.outcome = "defeat"
    tick(g, 3.5)
    reckoning = g.scenes[-1]
    assert isinstance(reckoning, ReckoningScene) and reckoning.gained == 0
    assert flow.progress.sigils == 0
    press(g, "return")
    assert isinstance(g.scenes[-1], StoryScene)   # Again returns through the unseen before page
    press(g, "return")
    press(g, "return")
    assert isinstance(g.scenes[-1], BriefingScene)


def test_the_tree_learns_what_the_free_sigils_pay_for_and_unlearns_for_free(game):
    g, flow = game
    flow.progress.won = {"tristram": 3}
    flow.intro(LOCATIONS["graveyard"])
    tick(g)
    assert isinstance(g.scenes[-1], StoryScene)   # the first arrival tells the before page
    press(g, "return")
    press(g, "return")
    assert isinstance(g.scenes[-1], BriefingScene)
    press(g, "k")
    tree = g.scenes[-1]
    assert isinstance(tree, SkillTreeScene)
    tick(g)
    spots = {s.name: s for s in tree.spots}

    def click(key: str) -> None:
        x, y, w, h = spots[key].box
        g.backend.inject_click(x + w / 2, y + h / 2)
        tick(g)

    click("fire_ball")        # damaging area attacks arrive much later
    assert not flow.progress.learned
    click("adept_arrow")
    click("warmth")
    assert flow.progress.learned == {"adept_arrow", "warmth"} and flow.progress.free == 0
    click("adept_fire")           # no sigils left
    assert "adept_fire" not in flow.progress.learned
    assert_text_fits(g)
    press(g, "u")
    assert not flow.progress.learned and flow.progress.free == 3
    press(g, "escape")
    assert isinstance(g.scenes[-1], BriefingScene)


def test_the_learned_skills_go_into_the_defence(game):
    g, flow = game
    flow.progress.won = {"tristram": 3}
    flow.progress.learn("adept_fire")
    flow.defend(LOCATIONS["graveyard"])
    tick(g)
    assert g.scenes[-1].world.perks.top("pyre") == 1


def test_a_late_learned_skill_is_marked_inactive_when_replaying_an_earlier_location(game):
    """A learned Fire Ball cannot affect a Caves run, so its tree card must say so."""
    g, flow = game
    flow.progress.won = {key: 3 for key in ORDER[:9]}
    flow.progress.learned = frozenset({"adept_fire", "master_fire", "fire_ball"})
    flow.skills(LOCATIONS["caves"])
    tick(g)
    tree = g.scenes[-1]
    assert isinstance(tree, SkillTreeScene)
    fire_ball = next(spot for spot in tree.spots if spot.name == "fire_ball")
    assert "Inactive in the Caves" in fire_ball.tip
    flow.defend(LOCATIONS["caves"])
    assert not g.scenes[-1].world.perks.fire_ball


def test_an_earlier_briefing_counts_late_learned_skills_as_inactive(game):
    """A revisit must disclose sigils spent on a skill filtered out of that defence."""
    g, flow = game
    flow.progress.won = {key: 3 for key in ORDER[:9]}
    flow.progress.learned = frozenset({"adept_fire", "master_fire", "fire_ball"})
    flow.progress.seen |= {"caves/before"}
    flow.intro(LOCATIONS["caves"])
    tick(g)
    assert isinstance(g.scenes[-1], BriefingScene)
    assert any("2 sigils sit in skills that do nothing here" in text["text"] for text in g.backend.texts)


def test_q_smites_the_leader_closest_to_cursing_and_no_spell_is_cast_while_paused(game):
    g, flow = game
    flow.progress.won = {"tristram": 1}
    flow.defend(LOCATIONS["graveyard"])
    tick(g)
    battle = g.scenes[-1]
    world = battle.world
    kind = MONSTERS["priest"]
    first = Monster(world._id(), kind, 0, 0, 0, 100, 0)
    second = Monster(world._id(), kind, 0, 0, 0, 100, 0)
    for leader, left in ((first, 0.5), (second, 2.0)):
        leader.s = 4.0
        leader.chant_curse = Curse.BONE_PRISON
        leader.chant_spot = (7, 4)
        leader.chant_left = left
    world.monsters.extend((first, second))
    world.wave_alive[0] = 2
    world.mana = 100
    press(g, "p")
    press(g, "q")
    assert world.chants_broken == 0 and world.mana == 100
    press(g, "p")
    press(g, "q")
    assert world.chants_broken == 1 and world.mana == pytest.approx(100 - SPELLS["smite"].mana, abs=1)
    assert first.chant_curse is None and second.chant_curse is not None


def test_what_a_location_does_not_offer_is_refused_with_where_it_arrives(game):
    g, flow = game
    flow.defend(LOCATIONS["tristram"])
    tick(g)
    battle = g.scenes[-1]
    press(g, "2")             # the Pyre arrives in the Cathedral
    assert battle.placing is None
    assert any("Cathedral" in text for _, text, _ in battle.hud.log)
    press(g, "w")             # Meteor arrives in Travincal
    assert battle.placing is None
    assert any("Travincal" in text for _, text, _ in battle.hud.log)
    assert_text_fits(g)


def test_a_location_the_way_has_not_reached_sends_the_player_back_to_the_map(game):
    g, flow = game
    flow.defend(LOCATIONS["caves"])
    tick(g)
    assert isinstance(g.scenes[-1], MapScene)


def test_the_first_descent_walks_on_by_itself_only_from_the_title(game):
    g, flow = game
    flow.world_map()   # back to the map from Tristram's intro, say: the lantern waits
    tick(g, 3)
    assert isinstance(g.scenes[-1], MapScene)


def test_a_won_defence_is_kept_even_when_the_player_leaves_before_the_reckoning(game):
    g, flow = game
    flow.defend(LOCATIONS["tristram"])
    tick(g)
    battle = g.scenes[-1]
    battle.world.lives = 20
    battle.world.outcome = "victory"
    tick(g)
    battle.to_map()   # the pause menu's To the map, before the reckoning comes
    tick(g)
    assert flow.progress.best("tristram") == 3


def test_map_shows_act_one_for_new_campaign(game):
    g, flow = game
    flow.descend()
    tick(g)
    press(g, "escape")   # skip prologue
    tick(g, 5)
    press(g, "return")   # skip tristram/before
    press(g, "return")
    tick(g, 0.5)   # past input guard
    # Back to map from intro
    press(g, "escape")
    tick(g)
    map_scene = g.scenes[-1]
    assert isinstance(map_scene, MapScene)
    assert map_scene.act == 1


def test_act_two_tab_locked_without_hells_gate(game):
    g, flow = game
    flow.descend()
    tick(g)
    press(g, "escape")   # skip prologue
    tick(g, 5)
    press(g, "return")
    press(g, "return")
    tick(g, 0.5)   # past input guard
    press(g, "escape")   # back to map
    tick(g)
    map_scene = g.scenes[-1]
    assert isinstance(map_scene, MapScene)
    assert map_scene.act == 1
    # Try to switch to Act II - should be refused
    press(g, "2")
    tick(g)
    assert map_scene.act == 1


def test_act_two_tab_opens_after_hells_gate_held(cache, tmp_path):
    saves = tmp_path / "saves"
    g, flow = open_game(cache, saves)
    # Simulate having won all Act I locations including Hell's Gate
    flow.progress.won = {key: 1 for key in ACTS[1]}
    flow.world_map()
    tick(g)
    # Act I ending plays first
    page = g.scenes[-1]
    assert isinstance(page, StoryScene) and page.pages[page.index].key == "act1-end-1"
    for _ in range(2 * len(STORIES["act1/end"].pages)):
        press(g, "return")
    tick(g)
    # Now map should be on Act II
    map_scene = g.scenes[-1]
    assert isinstance(map_scene, MapScene)
    assert map_scene.act == 2
    # Lantern should be at Docks (first location of Act II)
    assert map_scene.lantern == worldmap.ANCHORS[2]["docks"]
    g.close()


def test_after_act1_ending_map_opens_on_act2_and_walks_to_docks(cache, tmp_path):
    """Hell's Gate held, its ending unseen: the map plays the ending, then shows Act II and walks the lantern to the
    Docks, whose first-arrival page opens. The next map opening shows the lantern's own act again, and walks nowhere."""
    g, flow = open_game(cache, tmp_path / "saves")
    try:
        flow.progress.won = {key: 1 for key in ACTS[1]}
        flow.world_map()
        tick(g)
        ending = g.scenes[-1]
        assert isinstance(ending, StoryScene) and ending.pages[0].key == "act1-end-1"
        for _ in range(2 * len(ending.pages)):
            press(g, "return")
        map_scene = g.scenes[-1]
        assert isinstance(map_scene, MapScene) and map_scene.act == 2
        tick(g, 6)
        page = g.scenes[-1]
        assert isinstance(page, StoryScene) and page.pages[page.index].key == "docks-before"
    finally:
        g.close()
