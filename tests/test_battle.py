"""The battle scene on the mock backend: a scripted defence plays through it, and a player can build by clicking."""

from dataclasses import replace
from pathlib import Path

import pytest
from saga2d import Game
from saga2d.testing import assert_text_fits

from hellward.__main__ import build
from hellward.sim import planner
from hellward.sim.campaign import CATHEDRAL
from hellward.sim.players.ordinary import Ordinary
from hellward.sim.content import DOOR, TOWERS
from hellward.sim.model import SIM_DT
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene
from hellward.ui.hud import BUILD, SLOT, SLOT_X, TOP
from hellward.ui.view import MAP_X, MAP_Y, T


@pytest.fixture(scope="module")
def cache(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("cache")


@pytest.fixture
def game(cache, tmp_path):
    g = Game("Hellward", backend="mock", resolution=(WIDTH, HEIGHT), asset_path=cache, save_dir=tmp_path / "saves")
    yield g, build(g, cache)
    g.close()


def run(g: Game, seconds: float, dt: float = 1 / 30) -> None:
    for _ in range(int(seconds / dt)):
        g.tick(dt)


def test_a_scripted_defence_plays_through_the_scene(game):
    g, art = game
    scene = BattleScene(art, replace(CATHEDRAL, life=1.0), seed=1, planner=planner.smart, autopilot=Ordinary())   # the scene, not the tuning
    g.push(scene)
    scene.speed = 4.0
    cursed = False
    while scene.world.wave < 2 or scene.world.monsters:
        g.tick(1 / 30)
        cursed = cursed or any(t.curses for t in scene.world.towers.values())
        assert scene.world.time < 400
    assert scene.world.towers and cursed
    assert set(scene.view.figures) == {m.id for m in scene.world.monsters}
    assert set(scene.view.towers) == set(scene.world.towers)
    assert_text_fits(g)


def slot_centre(key: str) -> tuple[int, int]:
    i = BUILD.index(key)
    return SLOT_X + i * (SLOT + 10) + SLOT // 2, TOP + 16 + SLOT // 2


def tile_centre(x: int, y: int) -> tuple[int, int]:
    return int(MAP_X + (x + 0.5) * T), int(MAP_Y + (y + 0.5) * T)


def test_a_player_builds_a_tower_and_a_gate_by_clicking(game):
    g, art = game
    scene = BattleScene(art, seed=0, planner=planner.smart)
    g.push(scene)
    g.tick(SIM_DT)
    g.backend.inject_click(*slot_centre("pyre"))
    g.tick(SIM_DT)
    g.backend.inject_click(*tile_centre(4, 3))
    g.tick(SIM_DT)
    tower = scene.world.tower_at((4, 3))
    assert tower is not None and tower.kind is TOWERS["pyre"]
    g.backend.inject_key("5")
    g.tick(SIM_DT)
    door = scene.world.level.doors[1]
    g.backend.inject_click(*tile_centre(*door))
    g.tick(SIM_DT)
    assert scene.world.doors[1].built and scene.world.doors[1].hp == DOOR.hp
    g.backend.inject_click(*tile_centre(4, 3))
    g.tick(SIM_DT)
    assert scene.selected is tower
    gold = scene.world.gold
    g.backend.inject_key("s")
    g.tick(SIM_DT)
    assert scene.world.tower_at((4, 3)) is None and scene.world.gold > gold
    assert_text_fits(g)


def test_a_refused_build_is_explained_not_raised(game):
    g, art = game
    scene = BattleScene(art, seed=0, planner=planner.smart)
    g.push(scene)
    g.tick(SIM_DT)
    g.backend.inject_key("1")
    g.tick(SIM_DT)
    path = scene.world.level.path_tiles[5]
    g.backend.inject_click(*tile_centre(*path))
    g.tick(SIM_DT)
    assert not scene.world.towers
    assert any("floor" in text for _, text, _ in scene.hud.log)
