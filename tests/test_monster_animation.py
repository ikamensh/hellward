"""The upgraded monsters through game asset registration and the battle view.

The renderer-facing tests use Saga2D's mock backend to observe the same sprite
names and transforms that the real backend receives.  The visual review uses
``tools/animation_preview.py``, which captures the real renderer instead.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from PIL import Image, ImageOps
from saga2d import Game
from saga2d.backends.mock_backend import MockBackend

from hellward.__main__ import build
from hellward.art import figures
from hellward.sim.campaign import TRISTRAM
from hellward.sim.content import MONSTERS
from hellward.sim.level import Level, Route
from hellward.sim.model import Monster
from hellward.sim.players.ordinary import Ordinary
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene


KINDS = ("fallen", "skeleton", "zombie")
TOUR = ((0, 4), (6, 4), (9, 7), (9, 10), (6, 13), (3, 13), (1, 11), (1, 7), (4, 4), (32, 8))
BEARINGS = ("right", "front_right", "front", "front_left", "left", "back_left", "back", "back_right")


class PictureBackend(MockBackend):
    """Keep registered pixels so the asset test can detect a mirrored facing."""

    def __init__(self) -> None:
        super().__init__()
        self.pictures: dict[str, Image.Image] = {}

    def load_image_from_pil(self, image: Image.Image) -> str:
        handle = super().load_image_from_pil(image)
        self.pictures[handle] = image.copy()
        return handle


@pytest.fixture(scope="module")
def game_art(tmp_path_factory):
    root = tmp_path_factory.mktemp("animation")
    backend = PictureBackend()
    game = Game("Hellward animation test", backend=backend, resolution=(WIDTH, HEIGHT),
                asset_path=root / "cache", save_dir=root / "saves")
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.delenv("HELLWARD_ART", raising=False)
            art = build(game, root / "cache")
        yield game, art, backend
    finally:
        game.close()


def stage(game: Game, art) -> BattleScene:
    level = Level("animation bearings", 33, 18, ((0, 8), (32, 8)), (),
                  extra_routes=(Route("tour", TOUR),))
    scene = BattleScene(art, replace(TRISTRAM, level=level), seed=1, autopilot=Ordinary())
    game.clear_and_push(scene)
    scene.paused = True
    return scene


def midpoint(route: Route, leg: int) -> float:
    before = sum(math.dist(a, b) for a, b in zip(route.waypoints[:leg], route.waypoints[1:leg + 1]))
    return before + math.dist(route.waypoints[leg], route.waypoints[leg + 1]) / 2


def add_monster(scene: BattleScene, kind: str) -> Monster:
    spec = MONSTERS[kind]
    monster = Monster(100 + KINDS.index(kind), spec, 0, 0.0, 0.0, spec.hp, 0.0, route="tour")
    monster.s = midpoint(scene.world.level.route("tour"), 0)
    scene.world.monsters.append(monster)
    scene.view.spawn(monster)
    return monster


def test_enhanced_sprites_are_registered_in_eight_authored_bearings(game_art):
    game, art, backend = game_art
    assert figures.ENHANCED == set(KINDS)
    for kind in KINDS:
        assert len(figures.facings(kind)) == 8
        assert set(BEARINGS) == set(figures.facings(kind))
        assert len(figures.walk(kind)) > 4
        assert figures.hit_frames(kind) and figures.death_frames(kind)
        assert kind in art.monster
        expected = {f"{facing}/{frame}" for facing in figures.facings(kind) for frame in figures.frames(kind)}
        assert len(expected) == 152
        assert set(art.monster_painted[kind]) == expected, f"{kind}: procedural style gaps in production art"
        for facing in figures.facings(kind):
            for frame in figures.frames(kind):
                assert game.assets.has_image(f"mon/{kind}/{facing}/{frame}")
            walk_pictures = [backend.pictures[game.assets.image(f"mon/{kind}/{facing}/{frame}")]
                             for frame in figures.walk(kind)]
            distinct_walks = len({picture.tobytes() for picture in walk_pictures})
            expected_distinct = 4 if kind == "fallen" and facing in {"front", "back"} else 8
            assert distinct_walks >= expected_distinct, (kind, facing, distinct_walks)

        # Direction-specific renderings preserve the weapon and wounds on the
        # character's own side; a flipped right-facing sheet does not.
        assert any(
            backend.pictures[game.assets.image(f"mon/{kind}/left/{frame}")].tobytes()
            != ImageOps.mirror(backend.pictures[game.assets.image(f"mon/{kind}/right/{frame}")]).tobytes()
            for frame in figures.walk(kind)
        ), kind
        deaths = [backend.pictures[game.assets.image(f"mon/{kind}/front/{frame}")]
                  for frame in figures.death_frames(kind)]
        assert len({picture.tobytes() for picture in deaths}) == len(deaths), kind


@pytest.mark.parametrize("kind", KINDS)
def test_distance_walks_smoothly_through_every_bearing(game_art, kind):
    game, art, _ = game_art
    scene = stage(game, art)
    monster = add_monster(scene, kind)
    figure = scene.view.figures[monster.id]
    route = scene.world.level.route("tour")

    for leg, bearing in enumerate(BEARINGS):
        monster.s = midpoint(route, leg)
        figure.prev = monster.s
        scene.view.sync(1.0, 0.0, animation_dt=0.0)
        assert figure.sprite.image.startswith(f"mon/{kind}/{bearing}/"), (kind, bearing, figure.sprite.image)

    # Distance, not wall time, selects the step. The same frame persists while
    # stopped, and substep interpolation puts the feet halfway along a diagonal.
    diagonal = midpoint(route, 1)
    stride = figures.stride(kind)
    start = math.floor(diagonal / stride) * stride + 0.25 * stride
    monster.s = start
    figure.prev = start
    scene.view.sync(1.0, 0.0, animation_dt=0.0)
    first = figure.sprite.image
    scene.view.sync(1.0, 0.25, animation_dt=0.25)
    assert figure.sprite.image == first
    monster.s = start + stride
    scene.view.sync(0.5, 1 / 60, animation_dt=1 / 60)
    assert (figure.x, figure.y) == pytest.approx(scene.view.monster_point(monster, start + stride / 2))
    scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
    assert figure.sprite.image != first
    assert figure.sprite.image.rsplit("/", 1)[-1] in figures.walk(kind)


@pytest.mark.parametrize("kind", KINDS)
def test_hit_reacts_before_attacking_and_death_finishes_the_clip(game_art, kind):
    game, art, _ = game_art
    scene = stage(game, art)
    monster = add_monster(scene, kind)
    figure = scene.view.figures[monster.id]
    monster.door = 0  # the hit clip must take precedence over a door attack
    scene.view.hit(monster.id, "physical")

    seen_hits: list[str] = []
    for tick in range(30):
        if tick == 2:
            scene.view.hit(monster.id, "physical")  # repeated blows must not restart the reaction
        scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
        frame = figure.sprite.image.rsplit("/", 1)[-1]
        if frame in figures.hit_frames(kind) and (not seen_hits or seen_hits[-1] != frame):
            seen_hits.append(frame)
    assert seen_hits == list(figures.hit_frames(kind))
    assert figure.sprite.image.rsplit("/", 1)[-1] in figures.STRIKE

    monster.door = -1
    scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
    assert figure.sprite.image.rsplit("/", 1)[-1] in figures.walk(kind)

    scene.view.hit(monster.id, "physical")
    scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
    assert figure.sprite.image.rsplit("/", 1)[-1] in figures.hit_frames(kind)
    scene.view.kill(monster.id)
    assert not figure.shadow.is_removed

    seen_deaths: list[str] = []
    opacity: list[int] = []
    for _ in range(65):
        scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
        if figure.sprite.is_removed:
            break
        frame = figure.sprite.image.rsplit("/", 1)[-1]
        if frame in figures.death_frames(kind) and (not seen_deaths or seen_deaths[-1] != frame):
            seen_deaths.append(frame)
        opacity.append(figure.sprite.opacity)
    assert seen_deaths == list(figures.death_frames(kind))
    assert opacity and min(opacity) < max(opacity)
    assert figure.sprite.is_removed
    assert figure.shadow.is_removed
    assert monster.id not in scene.view.figures
    assert figure not in scene.view.dying


def test_battle_pause_freezes_reactions_and_speed_advances_them(game_art):
    game, art, _ = game_art
    scene = stage(game, art)
    monster = add_monster(scene, "fallen")
    figure = scene.view.figures[monster.id]
    scene.view.hit(monster.id, "physical")

    for _ in range(12):
        game.tick(1 / 30)
    assert figure.sprite.image.endswith("/hit1")

    scene.autopilot = None
    scene.paused = False
    scene.speed = 4.0
    game.tick(1 / 30)
    game.tick(1 / 30)
    assert figure.sprite.image.endswith("/hit2")


def test_hit_keeps_its_facing_through_a_corner_then_walk_turns(game_art):
    game, art, _ = game_art
    scene = stage(game, art)
    monster = add_monster(scene, "fallen")
    figure = scene.view.figures[monster.id]
    scene.view.hit(monster.id, "physical")
    scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
    assert figure.sprite.image.startswith("mon/fallen/right/hit")

    monster.s = midpoint(scene.world.level.route("tour"), 1)
    figure.prev = monster.s
    for _ in range(6):
        scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
        assert figure.sprite.image.startswith("mon/fallen/right/hit")
    for _ in range(30):
        scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
    assert figure.sprite.image.startswith("mon/fallen/front_right/walk")


def test_three_deaths_finish_in_their_own_cadence(game_art):
    game, art, _ = game_art
    scene = stage(game, art)
    figures_by_kind = {}
    for kind in KINDS:
        monster = add_monster(scene, kind)
        figures_by_kind[kind] = scene.view.kill(monster.id)
    removed_at = {}
    for tick in range(120):
        scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
        for kind, figure in figures_by_kind.items():
            assert figure is not None
            if figure.sprite.is_removed and kind not in removed_at:
                removed_at[kind] = tick
        if len(removed_at) == len(KINDS):
            break
    assert list(sorted(removed_at, key=removed_at.get)) == list(KINDS)
