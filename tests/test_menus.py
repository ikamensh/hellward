"""The pause menu, the settings and the ways in and out of a defence, through the mock backend."""

import json
from pathlib import Path

import pytest
from saga2d import Game

from hellward.__main__ import build
from hellward.sim import planner
from hellward.ui import menus
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene
from hellward.ui.menus import PauseScene, SettingsScene
from hellward.ui.title import TitleScene


@pytest.fixture(scope="module")
def cache(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("cache")


@pytest.fixture
def game(cache, tmp_path):
    g = Game("Hellward", backend="mock", resolution=(WIDTH, HEIGHT), asset_path=cache, save_dir=tmp_path / "saves")
    art = build(g, cache)
    yield g, art
    g.close()


def fight(g: Game, art) -> BattleScene:
    """A defence the way the game starts one: settings in hand, a way to start again and back to the title."""
    values = menus.settings(g)

    def begin() -> None:
        g.clear_and_push(fight_scene())

    def fight_scene() -> BattleScene:
        return BattleScene(art, planner=planner.smart, settings=values, restart=begin,
                           to_title=lambda: g.clear_and_push(TitleScene(lambda _: None, g.quit)))

    scene = fight_scene()
    g.push(scene)
    g.tick(1 / 30)
    return scene


def press(g: Game, key: str) -> None:
    g.backend.inject_key(key)
    g.tick(1 / 30)


def test_escape_with_nothing_held_opens_the_menu_and_the_fight_stands_still(game):
    g, art = game
    scene = fight(g, art)
    press(g, "1")                     # holding a Pyre: Escape lets go of it first
    press(g, "escape")
    assert scene.placing is None and not isinstance(g.scenes[-1], PauseScene)
    press(g, "escape")
    assert isinstance(g.scenes[-1], PauseScene)
    time = scene.world.time
    for _ in range(30):
        g.tick(1 / 30)
    assert scene.world.time == time
    press(g, "escape")
    assert g.scenes[-1] is scene
    g.tick(1 / 30)
    assert scene.world.time > time


def test_volumes_change_at_once_and_are_remembered(game):
    g, art = game
    fight(g, art)
    press(g, "escape")
    press(g, "s")
    assert isinstance(g.scenes[-1], SettingsScene)
    music = menus.settings(g)["music"]
    press(g, "right")                 # the first row is the music
    assert g.audio.get_volume("music") == pytest.approx(music + 0.1)
    press(g, "down")
    press(g, "left")
    press(g, "left")                  # effects two steps down
    assert g.audio.get_volume("sfx") == pytest.approx(menus.DEFAULTS["sfx"] - 0.2)
    press(g, "escape")                # closing the settings saves them
    saved = json.loads((g.data_dir / "settings.json").read_text())
    assert saved["music"] == pytest.approx(music + 0.1) and saved["sfx"] == pytest.approx(menus.DEFAULTS["sfx"] - 0.2)


def test_the_leaders_minds_setting_is_the_one_tab_toggles(game):
    g, art = game
    scene = fight(g, art)
    assert scene.fx.show_thoughts is True
    press(g, "tab")
    assert scene.fx.show_thoughts is False and menus.settings(g)["minds"] is False
    press(g, "escape")
    press(g, "s")
    for _ in range(3):
        press(g, "down")
    press(g, "right")                 # the minds row, switched back on in the settings
    press(g, "escape")
    press(g, "escape")
    assert scene.fx.show_thoughts is True


def test_starting_again_and_leaving_for_the_title_leave_no_old_fight_behind(game):
    g, art = game
    first = fight(g, art)
    for _ in range(60):
        g.tick(1 / 30)
    press(g, "escape")
    press(g, "r")
    assert len(g.scenes) == 1 and isinstance(g.scenes[0], BattleScene) and g.scenes[0] is not first
    assert g.scenes[0].world.time < 0.1
    press(g, "escape")
    press(g, "t")
    assert len(g.scenes) == 1 and isinstance(g.scenes[0], TitleScene)


def test_escape_on_the_title_does_not_quit(game):
    g, _ = game
    g.push(TitleScene(lambda _: None, g.quit))
    g.tick(1 / 30)
    press(g, "escape")
    assert g.running
    press(g, "s")
    assert isinstance(g.scenes[-1], SettingsScene)
    press(g, "escape")
    press(g, "q")
    assert not g.running
