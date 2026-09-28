"""The battle view draws a monster where its committed route actually runs."""

from dataclasses import replace

from saga2d import Game

from hellward.__main__ import build
from hellward.sim.campaign import TRISTRAM
from hellward.sim.content import MONSTERS
from hellward.sim.level import Level, Route
from hellward.sim.model import Monster
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene
from hellward.ui.view import px


def test_a_side_entrance_turn_and_leak_are_drawn_on_the_monsters_route(tmp_path):
    level = Level("yard", 25, 14, ((0, 6), (12, 6), (12, 7), (24, 7)), (),
                  extra_routes=(Route("north", ((0, 2), (5, 2), (5, 10), (24, 7))),
                                Route("breach", ((0, 11), (6, 11), (14, 8), (24, 7)))))
    game = Game("Hellward", backend="mock", resolution=(WIDTH, HEIGHT), asset_path=tmp_path / "assets",
                save_dir=tmp_path / "saves")
    try:
        art = build(game, tmp_path / "assets")
        scene = BattleScene(art, replace(TRISTRAM, level=level))
        game.push(scene)
        active_portals = {(light.x, light.y) for light in scene.view.static_lights if light.color == (255, 60, 30)}
        assert active_portals == {px(0.5, 6.5), px(0.5, 2.5)}
        assert scene.view.seals

        scene.world.breach_mode = "cash"
        scene.view.sync(1.0, 1 / 30)
        active_portals = {(light.x, light.y) for light in scene.view.static_lights if light.color == (255, 60, 30)}
        assert active_portals == {px(0.5, 6.5), px(0.5, 2.5), px(0.5, 11.5)}
        assert not scene.view.seals

        kind = MONSTERS["fallen"]
        monster = Monster(501, kind, 0, 0.0, 0.0, kind.hp, 0.0, route="north")
        scene.world.monsters.append(monster)
        scene.view.spawn(monster)
        figure = scene.view.figures[monster.id]
        cell = art.monster[kind.key]
        x, y = px(0.5, 2.5)
        assert figure.sprite.position == (x - cell.origin[0], y - cell.origin[1])

        scene.view.before_step()
        monster.s = 7.0
        scene.view.sync(1.0, 1 / 30)
        assert (figure.x, figure.y) == px(5.5, 4.5)
        assert figure.sprite.image.startswith("mon/fallen/front/")

        monster.s = level.route("north").length
        scene.fx.on_leak(monster.id, kind.key, 1)
        exit_x, exit_y = px(24.5, 7.5)
        assert scene.fx.blooms[-1].sprite.position == (exit_x, exit_y - 20)
    finally:
        game.close()
