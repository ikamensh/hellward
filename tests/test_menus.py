"""The pause menu, the settings and the ways in and out of a defence, through the mock backend."""

import json
from pathlib import Path

import pytest
from saga2d import Game

from hellward.__main__ import build
from hellward.sim import planner
from hellward.sim.campaign import CATHEDRAL
from hellward.sim.players.ordinary import Ordinary
from hellward.ui import menus
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene, Silent
from hellward.ui.flow import Flow
from hellward.ui.mapscreen import MapScene
from hellward.ui.menus import PauseScene, SettingsScene
from hellward.ui.progress import Progress
from hellward.ui.story import StoryScene
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


def flow_of(g: Game, art) -> Flow:
    return Flow(g, art, sound=Silent(), planner=planner.smart, settings=menus.settings(g), progress=Progress.load(g),
                demo_player=Ordinary)


def fight(g: Game, art) -> BattleScene:
    """A defence the way the game starts one: settings in hand, ways to start again, to the map and to the title."""
    flow = flow_of(g, art)
    flow.progress.won = {"tristram": 1, "graveyard": 1}   # the way down to the Cathedral is open
    flow.defend(CATHEDRAL)
    g.tick(1 / 30)
    return g.scenes[-1]


def title(g: Game, art) -> None:
    g.push(TitleScene(flow_of(g, art)))
    g.tick(1 / 30)


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
    saved = json.loads((g.data_dir / "settings.json").read_text())   # saved as they change, before closing
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
    press(g, "m")
    assert isinstance(g.scenes[-1], StoryScene)   # Tristram's after page is due and unseen on the way to the map
    press(g, "return")
    press(g, "return")
    assert len(g.scenes) == 1 and isinstance(g.scenes[0], MapScene)
    fight(g, art)
    press(g, "escape")
    press(g, "t")
    assert len(g.scenes) == 1 and isinstance(g.scenes[0], TitleScene)


def test_escape_on_the_title_does_not_quit(game):
    g, art = game
    title(g, art)
    press(g, "escape")
    assert g.running
    press(g, "s")
    assert isinstance(g.scenes[-1], SettingsScene)
    press(g, "escape")
    press(g, "q")
    assert not g.running


def test_a_player_who_looks_away_comes_back_to_the_menu_and_resume_resumes(game):
    g, art = game
    g.backend.inject_focus(True)
    g.tick(1 / 30)
    scene = fight(g, art)
    g.backend.inject_focus(False)
    g.tick(1 / 30)
    g.backend.inject_focus(True)
    g.tick(1 / 30)
    assert isinstance(g.scenes[-1], PauseScene)
    press(g, "escape")
    time = scene.world.time
    for _ in range(30):
        g.tick(1 / 30)
    assert g.scenes[-1] is scene and scene.world.time > time


def test_resume_also_lifts_a_pause_from_the_p_key(game):
    g, art = game
    scene = fight(g, art)
    press(g, "p")
    assert scene.paused
    press(g, "escape")
    press(g, "escape")
    assert not scene.paused


def test_a_broken_settings_file_is_set_aside_and_the_game_saves_again(cache, tmp_path):
    saves = tmp_path / "saves"
    saves.mkdir()
    (tmp_path / "settings.json").write_text('{"music": 7, "sfx": "loud"')
    g = Game("Hellward", backend="mock", resolution=(WIDTH, HEIGHT), asset_path=cache, save_dir=saves)
    try:
        art = build(g, cache)
        values = menus.settings(g)
        assert values["music"] == menus.DEFAULTS["music"]
        assert list(tmp_path.glob("settings.recovery-*.json"))
        scene = fight(g, art)
        press(g, "tab")                               # saves: no longer refused because of the old file
        assert json.loads((tmp_path / "settings.json").read_text())["minds"] is False
        assert scene.fx.show_thoughts is False
    finally:
        g.close()


def test_changing_a_volume_neither_leaves_nor_saves_a_session_fullscreen(game):
    g, art = game
    g.set_fullscreen(True)                            # what --fullscreen does for one session
    title(g, art)
    press(g, "s")
    press(g, "right")
    assert g.fullscreen
    assert json.loads((g.data_dir / "settings.json").read_text())["fullscreen"] is False


def test_the_planners_workers_end_with_the_game_however_it_ends(tmp_path):
    """Cmd+Q on a Mac ends the process without closing the pool; the workers must not outlive it."""
    import os
    import subprocess
    import sys
    import time

    script = tmp_path / "orphan.py"
    script.write_text(
        "import os, signal\n"
        "from hellward.ui.thinking import Thinker\n"
        "if __name__ == '__main__':\n"
        "    thinker = Thinker()\n"
        "    print(' '.join(str(p) for p in thinker.pool._processes), flush=True)\n"
        "    os.kill(os.getpid(), signal.SIGKILL)\n")
    run = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
    workers = [int(p) for p in run.stdout.split()]
    assert workers

    def alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    deadline = time.monotonic() + 10
    while any(alive(p) for p in workers) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not any(alive(p) for p in workers)
