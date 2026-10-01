"""Live painted rigs through Saga2D's actual sprite and asset interfaces."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from saga2d import Game, Scene
from saga2d.rendering.layers import Y_SORT_STEP

from hellward.art import puppet
from hellward.ui.puppet import PuppetBody


@pytest.fixture
def stage(tmp_path):
    game = Game("painted rigs", backend="mock", resolution=(1280, 800),
                asset_path=tmp_path / "assets", save_dir=tmp_path / "save")
    puppet.register(game, puppet.KINDS)
    scene = Scene()
    game.push(scene)
    yield game, scene
    game.close()


def test_every_bearing_walks_using_fixed_painted_parts(stage):
    """Continuous movement changes transforms while keeping the same painted surfaces."""
    _, scene = stage
    for kind in puppet.KINDS:
        for facing in puppet.BEARINGS:
            body = PuppetBody(scene, kind, facing)
            body.walk(facing, 0, 500, 304)
            names = tuple(sprite.image for sprite in body.sprites)
            previous = tuple(sprite.position for sprite in body.sprites)
            positions = set()
            for i in range(1, 61):
                body.walk(facing, i / 60 * puppet.CYCLE[kind], 500, 304)
                assert tuple(sprite.image for sprite in body.sprites) == names
                # The engine sorts at 8px intervals. Every piece must stay in the
                # root's interval, even when cancellation happens at a bin boundary.
                assert {int(sprite.top_left[1] + sprite.height - sprite.ground) // Y_SORT_STEP for sprite in body.sprites} == {304 // Y_SORT_STEP}
                current = tuple(sprite.position for sprite in body.sprites)
                assert all(math.dist(a, b) < 4 for a, b in zip(previous, current)), (kind, facing, i)
                assert all(math.isfinite(value) and value > 0 for sprite in body.sprites for value in sprite.size)
                positions.add(current)
                previous = current
            assert len(positions) == 60
            body.remove()
            assert all(sprite.is_removed for sprite in body.sprites)


def test_hit_recoils_without_changing_part_sizes(stage):
    """A reaction rotates the walking body; it cannot load an oversized hit painting."""
    _, scene = stage
    for kind in puppet.KINDS:
        for facing in puppet.BEARINGS:
            body = PuppetBody(scene, kind, facing)
            body.walk(facing, 0.17, 500, 300)
            before = [(sprite.image, sprite.size, sprite.rotation) for sprite in body.sprites]
            body.update(facing, 0.17, 500, 300, hit=0.055)
            assert max(abs(sprite.rotation - old[2]) for sprite, old in zip(body.sprites, before)) > 8
            for sprite, (name, size, _) in zip(body.sprites, before):
                assert sprite.image == name
                assert sprite.size == pytest.approx(size)
            body.update(facing, 0.17, 500, 300, hit=puppet.HIT_LIFE)
            assert [sprite.rotation for sprite in body.sprites] == pytest.approx([old[2] for old in before])
            body.remove()


def test_death_starts_in_place_and_settles_before_fading(stage):
    """Death captures the current gait, then preserves visible corpses before cleanup."""
    _, scene = stage
    for kind in puppet.KINDS:
        body = PuppetBody(scene, kind, "right")
        body.walk("right", 0.19, 500, 300)
        before = [(sprite.position, sprite.rotation) for sprite in body.sprites]
        body.update("right", 0.19, 500, 300, death=0)
        for sprite, (position, rotation) in zip(body.sprites, before):
            assert sprite.position == pytest.approx(position)
            assert sprite.rotation == pytest.approx(rotation)
        body.update("right", 0.19, 500, 300, death=0.80)
        assert all(sprite.opacity == 255 for sprite in body.sprites)
        assert max(math.dist(sprite.position, old[0]) for sprite, old in zip(body.sprites, before)) > 20
        body.update("right", 0.19, 500, 300, death=puppet.DEATH_LIFE[kind])
        assert all(sprite.opacity == 0 for sprite in body.sprites)
        body.remove()



def test_strike_keeps_the_walking_body_and_its_death_continuous(stage):
    """Starting a strike cannot snap to an unrelated stance; killing it keeps the visible pose."""
    _, scene = stage
    for kind in puppet.KINDS:
        for facing in puppet.BEARINGS:
            body = PuppetBody(scene, kind, facing)
            body.walk(facing, 0.17, 500, 300)
            before = {sprite.image: (sprite.position, sprite.rotation, sprite.size) for sprite in body.sprites}
            body.update(facing, 0.17, 500, 300, attack=0)
            for sprite in body.sprites:
                position, rotation, size = before[sprite.image]
                assert sprite.position == pytest.approx(position)
                assert sprite.rotation == pytest.approx(rotation)
                assert sprite.size == pytest.approx(size)
            body.update(facing, 0.17, 500, 300, attack=0.32)
            struck = [(sprite.image, sprite.position, sprite.rotation) for sprite in body.sprites]
            assert max(math.dist(sprite.position, before[sprite.image][0]) for sprite in body.sprites) > 4
            body.update(facing, 0.17, 500, 300, death=0)
            for sprite, (image, position, rotation) in zip(body.sprites, struck):
                assert sprite.image == image
                assert sprite.position == pytest.approx(position)
                assert sprite.rotation == pytest.approx(rotation)
            body.remove()

def test_battle_uses_live_rigs_through_turns_pause_hits_and_death(tmp_path, monkeypatch):
    """Exercise the new body on the game's clock, including its retained cleanup."""
    from hellward.__main__ import build
    from hellward.sim.campaign import TRISTRAM
    from hellward.sim.content import MONSTERS
    from hellward.sim.level import Level, Route
    from hellward.sim.model import Monster
    from hellward.ui.battle import BattleScene

    monkeypatch.setenv("HELLWARD_MONSTER_STYLE", "puppet")
    monkeypatch.delenv("HELLWARD_ART", raising=False)
    game = Game("live battle rigs", backend="mock", resolution=(1280, 800),
                asset_path=tmp_path / "cache", save_dir=tmp_path / "save")
    try:
        art = build(game, tmp_path / "cache")
        assert art.puppets == frozenset(puppet.KINDS)
        level = Level("turns", 33, 18, ((0, 8), (32, 8)), (),
                      extra_routes=(Route("turns", ((0, 4), (6, 4), (9, 7), (9, 12), (32, 8))),))
        scene = BattleScene(art, replace(TRISTRAM, level=level), seed=1, autopilot=None)
        game.push(scene)
        for index, kind in enumerate(puppet.KINDS):
            spec = MONSTERS[kind]
            monster = Monster(100 + index, spec, 0, 0.0, 0.0, spec.hp, 0.0, route="turns")
            monster.s = 3
            scene.world.monsters.append(monster)
            scene.view.spawn(monster)
            figure = scene.view.figures[monster.id]
            assert figure.puppet is not None
            scene.view.sync(1, 0, animation_dt=0)
            assert all(f"/{kind}/right/" in sprite.image for sprite in figure.puppet.sprites)
            monster.s = 8
            figure.prev = 8
            scene.view.sync(1, 0, animation_dt=0)
            assert all(f"/{kind}/front_right/" in sprite.image for sprite in figure.puppet.sprites)

            scene.view.hit(monster.id, "physical")
            scene.paused = True
            before = [(sprite.position, sprite.rotation) for sprite in figure.puppet.sprites]
            for _ in range(10):
                game.tick(1 / 60)
            assert figure.hit_time == 0
            assert [(sprite.position, sprite.rotation) for sprite in figure.puppet.sprites] == before
            scene.paused = False
            scene.speed = 4
            game.tick(1 / 60)
            game.tick(1 / 60)
            assert figure.hit_time == pytest.approx(8 / 60)
            assert [(sprite.position, sprite.rotation) for sprite in figure.puppet.sprites] != before
            scene.view.kill(monster.id)
            scene.world.monsters.remove(monster)
            for _ in range(30):
                game.tick(1 / 60)
            assert all(sprite.is_removed for sprite in figure.puppet.sprites)
            assert figure.sprite is None and figure.shadow.is_removed
            assert figure not in scene.view.dying
    finally:
        game.close()
