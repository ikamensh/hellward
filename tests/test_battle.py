"""The battle scene on the mock backend: a scripted defence plays through it, and a player can build by clicking."""

from dataclasses import replace
from pathlib import Path

import pytest
from saga2d import Game
from saga2d.testing import assert_text_fits

from hellward.__main__ import build
from hellward.sim import planner
from hellward.sim.campaign import CATHEDRAL, TRISTRAM
from hellward.sim.level import Level
from hellward.sim.players.ordinary import Ordinary
from hellward.sim.content import DOOR, TOWERS
from hellward.sim.model import SIM_DT
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene
from hellward.ui.hud import BUILD, SLOT, SLOT_X, TOP, slot_size
from hellward.ui.view import px


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
    while scene.world.wave < 2 or scene.world.monsters:
        g.tick(1 / 30)
        assert scene.world.time < 400
    assert scene.world.towers and scene.world.wave >= 2
    assert set(scene.view.figures) == {m.id for m in scene.world.monsters}
    assert set(scene.view.towers) == set(scene.world.towers)
    assert_text_fits(g)


def slot_centre(key: str) -> tuple[int, int]:
    i = BUILD.index(key)
    size, step = slot_size(len(BUILD))
    return int(SLOT_X + i * step + size / 2), int(TOP + 16 + SLOT / 2)


def tile_centre(scene: BattleScene, x: int, y: int) -> tuple[int, int]:
    sx, sy = scene.camera.world_to_screen(*px(x + 0.5, y + 0.5))
    return int(sx), int(sy)


def test_a_player_builds_a_tower_and_a_gate_by_clicking(game):
    g, art = game
    scene = BattleScene(art, seed=0, planner=planner.smart)
    g.push(scene)
    g.tick(SIM_DT)
    tile = next((x, y) for y in range(scene.world.level.height) for x in range(scene.world.level.width)
                if scene.world.level.buildable(x, y))
    g.backend.inject_click(*slot_centre("pyre"))
    g.tick(SIM_DT)
    g.backend.inject_click(*tile_centre(scene, *tile))
    g.tick(SIM_DT)
    tower = scene.world.tower_at(tile)
    assert tower is not None and tower.kind is TOWERS["pyre"]
    g.backend.inject_key(str(BUILD.index("gate") + 1))
    g.tick(SIM_DT)
    door = scene.world.level.doors[0]
    g.backend.inject_click(*tile_centre(scene, *door))
    g.tick(SIM_DT)
    assert scene.world.doors[0].built and scene.world.doors[0].hp == scene.world.gate_life
    g.backend.inject_click(*tile_centre(scene, *tile))
    g.tick(SIM_DT)
    assert scene.selected is tower
    gold = scene.world.gold
    g.backend.inject_key("s")
    g.tick(SIM_DT)
    assert scene.world.tower_at(tile) is None and scene.world.gold > gold
    assert_text_fits(g)


def test_a_refused_build_is_explained_not_raised(game):
    g, art = game
    scene = BattleScene(art, seed=0, planner=planner.smart)
    g.push(scene)
    g.tick(SIM_DT)
    g.backend.inject_key("1")
    g.tick(SIM_DT)
    path = scene.world.level.path_tiles[5]
    g.backend.inject_click(*tile_centre(scene, *path))
    g.tick(SIM_DT)
    assert not scene.world.towers
    assert any("floor" in text for _, text, _ in scene.hud.log)


def test_a_larger_field_fits_above_the_hud_and_its_far_corner_accepts_a_build(game):
    """A player can see and click every approach when a location needs a larger field."""
    g, art = game
    level = Level("wide yard", 33, 18, ((0, 9), (32, 9)), ())
    scene = BattleScene(art, replace(TRISTRAM, level=level))
    g.push(scene)
    g.tick(SIM_DT)
    left, top = scene.camera.world_to_screen(*px(0, 0))
    right, bottom = scene.camera.world_to_screen(*px(level.width, level.height))
    assert 0 <= left < right <= WIDTH
    assert 0 <= top < bottom <= TOP
    tile = (level.width - 2, level.height - 2)
    assert level.buildable(*tile)
    g.backend.inject_key("1")
    g.tick(SIM_DT)
    sx, sy = scene.camera.world_to_screen(*px(tile[0] + 0.5, tile[1] + 0.5))
    g.backend.inject_click(int(sx), int(sy))
    g.tick(SIM_DT)
    assert scene.world.tower_at(tile) is not None
