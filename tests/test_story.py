"""The story on the mock backend: the pages' words, the scenes that tell them, and when the flow plays them."""

import re
from pathlib import Path

import pytest
from saga2d import Game
from saga2d.testing import assert_text_fits

from hellward.__main__ import build
from hellward.sim import planner
from hellward.sim.campaign import LOCATIONS, ORDER
from hellward.sim.players.ordinary import Ordinary
from hellward.story import STORIES, Page
from hellward.ui import menus
from hellward.ui.battle import HEIGHT, WIDTH, Silent
from hellward.ui.briefing import BriefingScene
from hellward.ui.flow import Flow
from hellward.ui.mapscreen import MapScene
from hellward.ui.progress import Progress
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


def test_every_story_key_names_its_moment_and_every_page_has_text():
    for key in STORIES:
        assert re.fullmatch(r"[a-z_]+/(before|after)", key) or re.fullmatch(r"act\d/end", key), key
    for story in STORIES.values():
        for page in story.pages:
            assert page.text and all(line.strip() for line in page.text), page.key
    for key, story in STORIES.items():
        if story.act == 1:
            assert key == "act1/end" or key.split("/")[0] in LOCATIONS, key


def test_a_story_page_reveals_then_advances_and_esc_skips(cache, tmp_path):
    g, flow = open_game(cache, tmp_path / "one")
    shown: list[str] = []
    g.push(StoryScene(flow, STORIES["tristram/before"].pages, then=lambda: shown.append("then")))
    tick(g)
    assert_text_fits(g)
    press(g, "return")   # the first Enter shows every paragraph at once
    assert shown == [] and isinstance(g.scenes[-1], StoryScene)
    press(g, "return")   # the next goes past the last page
    assert shown == ["then"]
    tick(g, 1)
    assert shown == ["then"]
    g.close()

    g, flow = open_game(cache, tmp_path / "two")
    shown.clear()
    g.push(StoryScene(flow, STORIES["tristram/before"].pages, then=lambda: shown.append("then")))
    tick(g)
    press(g, "escape")   # Esc calls then() at once
    assert shown == ["then"]
    g.close()


def test_a_page_whose_picture_is_missing_draws_without_crashing(cache, tmp_path):
    g, flow = open_game(cache, tmp_path / "saves")
    shown: list[str] = []
    g.push(StoryScene(flow, (Page("no-such-picture", "nothing painted yet", ("Some words.",)),),
                      then=lambda: shown.append("then")))
    tick(g, 2)   # draws the gradient stand-in, never crashing
    assert_text_fits(g)
    press(g, "return")
    press(g, "return")
    assert shown == ["then"]
    g.close()


def test_the_prologue_runs_to_its_end_and_esc_ends_it(cache, tmp_path):
    g, flow = open_game(cache, tmp_path / "one")
    ended: list[str] = []
    g.push(PrologueScene(flow, then=lambda: ended.append("then")))
    tick(g)
    assert_text_fits(g)
    scene = g.scenes[-1]
    assert isinstance(scene, PrologueScene)
    tick(g, scene.end + 2)   # past its end on its own clock
    assert ended == ["then"]
    tick(g, 2)
    assert ended == ["then"]
    g.close()

    g, flow = open_game(cache, tmp_path / "two")
    ended.clear()
    g.push(PrologueScene(flow, then=lambda: ended.append("then")))
    tick(g)
    press(g, "escape")
    assert ended == ["then"]
    g.close()


def test_a_new_campaign_first_descend_plays_the_prologue(game):
    g, flow = game
    g.push(TitleScene(flow))
    tick(g)
    press(g, "return")
    assert isinstance(g.scenes[-1], PrologueScene)
    press(g, "escape")
    assert isinstance(g.scenes[-1], MapScene)
    flow.title()
    tick(g)
    press(g, "return")
    assert isinstance(g.scenes[-1], MapScene)


def test_the_first_arrival_at_tristram_tells_its_before_page(game):
    g, flow = game
    flow.descend()
    tick(g)
    assert isinstance(g.scenes[-1], PrologueScene)
    press(g, "escape")   # skip the prologue: the lantern walks on by itself
    tick(g, 5)
    assert isinstance(g.scenes[-1], StoryScene)   # the first arrival shows tristram/before
    press(g, "return")
    press(g, "return")
    intro = g.scenes[-1]
    assert isinstance(intro, BriefingScene) and intro.location.key == "tristram"
    assert_text_fits(g)
    flow.intro(LOCATIONS["tristram"])   # the second arrival goes straight to the intro
    tick(g)
    intro = g.scenes[-1]
    assert isinstance(intro, BriefingScene) and intro.location.key == "tristram"


def test_winning_tristram_shows_its_after_page_once(game):
    g, flow = game
    flow.defend(LOCATIONS["tristram"])
    tick(g)
    battle = g.scenes[-1]
    battle.world.lives = 19
    battle.world.outcome = "victory"   # the fight itself is the rules' tests' business
    tick(g, 3.5)
    assert isinstance(g.scenes[-1], ReckoningScene)
    press(g, "escape")   # leaving the reckoning shows tristram/after
    page = g.scenes[-1]
    assert isinstance(page, StoryScene) and page.pages[page.index].key == "tristram-after"
    assert_text_fits(g)
    press(g, "return")
    press(g, "return")
    assert isinstance(g.scenes[-1], MapScene)
    flow.world_map()   # the second map opening shows no page
    tick(g)
    assert isinstance(g.scenes[-1], MapScene)


def test_a_save_holding_act_one_plays_the_ending_once(game):
    g, flow = game
    flow.progress.won = {key: 1 for key in ORDER}
    flow.world_map()
    tick(g)
    page = g.scenes[-1]
    assert isinstance(page, StoryScene) and page.pages[page.index].key == "act1-end-1"
    for _ in range(2 * len(STORIES["act1/end"].pages)):
        press(g, "return")
    assert isinstance(g.scenes[-1], MapScene)
    flow.world_map()
    tick(g)
    assert isinstance(g.scenes[-1], MapScene)


def test_seen_pages_save_and_load(cache, tmp_path):
    saves = tmp_path / "saves"
    g, flow = open_game(cache, saves)
    flow.progress.see("prologue")
    flow.progress.see("tristram/before")
    g.close()
    g, flow = open_game(cache, saves)
    assert flow.progress.seen == frozenset({"prologue", "tristram/before"})
    g.close()
