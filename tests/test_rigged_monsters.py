"""Battle-level integration of the baked 3D and painted monster modes."""

from __future__ import annotations

import math
from dataclasses import replace

from PIL import Image
from saga2d import Game

from hellward.__main__ import build
from hellward.art import figures, rigged
from hellward.sim.campaign import TRISTRAM
from hellward.sim.content import MONSTERS
from hellward.sim.level import Level, Route
from hellward.sim.model import Monster
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene

TOUR = ((0, 4), (6, 4), (9, 7), (9, 10), (6, 13), (3, 13), (1, 11), (1, 7), (4, 4), (32, 8))


def midpoint(route: Route, leg: int) -> float:
    before = sum(math.dist(a, b) for a, b in zip(route.waypoints[:leg], route.waypoints[1:leg + 1]))
    return before + math.dist(route.waypoints[leg], route.waypoints[leg + 1]) / 2


def stage(game: Game, art) -> BattleScene:
    level = Level("animation bearings", 33, 18, ((0, 8), (32, 8)), (),
                  extra_routes=(Route("tour", TOUR),))
    scene = BattleScene(art, replace(TRISTRAM, level=level), seed=1, autopilot=None)
    game.clear_and_push(scene)
    scene.paused = True
    return scene


def test_committed_3d_frames_match_the_current_rigs():
    """Rebake after changing the 3D bodies or poses; fixed cells must not go stale."""
    for kind in rigged.KINDS:
        _, atlas = rigged.load(kind)
        for facing in ("front", "right", "back"):
            for frame in ("walk1", "walk2", "hit2", "strike", "death3"):
                rendered = rigged.render(kind, facing, frame)
                # The atlas compositor clears RGB beneath fully transparent pixels.
                visible = Image.alpha_composite(Image.new("RGBA", rendered.size), rendered)
                assert atlas[f"{facing}/{frame}"].tobytes() == visible.tobytes()


def test_normal_battle_uses_painted_monsters(tmp_path, monkeypatch):
    """Blockout 3D is an opt-in comparison, never an ordinary spawn."""
    monkeypatch.delenv("HELLWARD_MONSTER_STYLE", raising=False)
    monkeypatch.delenv("HELLWARD_ART", raising=False)
    game = Game("Hellward painted default test", backend="mock", resolution=(WIDTH, HEIGHT),
                asset_path=tmp_path / "cache", save_dir=tmp_path / "saves")
    try:
        art = build(game, tmp_path / "cache")
        assert art.monster_style == "painted"
        assert not art.rigged
        scene = stage(game, art)
        for kind in ("fallen", "skeleton", "zombie"):
            spec = MONSTERS[kind]
            monster = Monster(100, spec, 0, 0.0, 0.0, spec.hp, 0.0, route="tour")
            scene.world.monsters.append(monster)
            scene.view.spawn(monster)
            figure = scene.view.figures[monster.id]
            assert figure.sprite.image.startswith(f"mon/{kind}/")
            scene.view.hit(monster.id, "physical")
            for _ in range(18):
                scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
                assert figure.sprite.image.startswith(f"mon/{kind}/")
            scene.view.kill(monster.id)
            for _ in range(35):
                scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
                assert figure.sprite.image.startswith(f"mon/{kind}/")
            scene.world.monsters.remove(monster)
            scene.view.vanish(monster.id)
    finally:
        game.close()


def test_two_rigged_monsters_mix_with_painted_spawns_in_battle(tmp_path, monkeypatch):
    """A battle can display both baked 3D and painted bodies of each supported kind."""
    monkeypatch.setenv("HELLWARD_MONSTER_STYLE", "mixed")
    monkeypatch.delenv("HELLWARD_ART", raising=False)
    game = Game("Hellward rigged mix test", backend="mock", resolution=(WIDTH, HEIGHT),
                asset_path=tmp_path / "cache", save_dir=tmp_path / "saves")
    try:
        art = build(game, tmp_path / "cache")
        scene = stage(game, art)
        for kind in ("skeleton", "zombie"):
            seen: set[str] = set()
            rigged_id = -1
            for monster_id in range(100, 124):
                spec = MONSTERS[kind]
                monster = Monster(monster_id, spec, 0, 0.0, 0.0, spec.hp, 0.0, route="tour")
                monster.s = midpoint(scene.world.level.route("tour"), 0)
                scene.world.monsters.append(monster)
                scene.view.spawn(monster)
                figure = scene.view.figures[monster.id]
                prefix = figure.sprite.image.split("/", 1)[0]
                seen.add(prefix)
                if prefix == "mon3d":
                    rigged_id = monster_id
                assert game.assets.has_image(figure.sprite.image)
                scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
                assert figure.sprite.image.startswith(f"{prefix}/{kind}/right/walk")
                scene.view.vanish(monster.id)
                scene.world.monsters.remove(monster)
                scene.view.spawn(monster)
                assert figure.sprite.image.split("/", 1)[0] == prefix
                scene.view.vanish(monster.id)
            assert seen == {"mon", "mon3d"}, (kind, seen)
            for facing in figures.facings(kind):
                for frame in rigged.FRAMES:
                    assert game.assets.has_image(f"mon3d/{kind}/{facing}/{frame}")

            spec = MONSTERS[kind]
            monster = Monster(rigged_id, spec, 0, 0.0, 0.0, spec.hp, 0.0, route="tour")
            scene.world.monsters.append(monster)
            scene.view.spawn(monster)
            figure = scene.view.figures[rigged_id]
            stride = figures.stride(kind) / 2
            names = set()
            for step in range(16):
                monster.s = (step + 0.1) * stride
                figure.prev = monster.s
                scene.view.sync(1.0, 0.0, animation_dt=0.0)
                names.add(figure.sprite.image)
            assert names == {f"mon3d/{kind}/right/{frame}" for frame in rigged.WALK}

            scene.view.hit(rigged_id, "physical")
            seen_hits: set[str] = set()
            for _ in range(18):
                scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
                if "/hit" in figure.sprite.image:
                    seen_hits.add(figure.sprite.image)
            assert seen_hits == {f"mon3d/{kind}/right/{frame}" for frame in figures.HIT}
            scene.view.kill(rigged_id)
            deaths: set[str] = set()
            for _ in range(35):
                scene.view.sync(1.0, 1 / 60, animation_dt=1 / 60)
                if "/death" in figure.sprite.image:
                    deaths.add(figure.sprite.image)
            assert deaths == {f"mon3d/{kind}/right/{frame}" for frame in figures.DEATH}
            scene.world.monsters.remove(monster)
    finally:
        game.close()
