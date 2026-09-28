"""The side entrance and salvage choices are playable through the battle panel."""

from pathlib import Path

from saga2d import Game

from hellward.__main__ import build
from hellward.sim.campaign import GRAVEYARD
from hellward.sim.model import SIM_DT
from hellward.ui.battle import BattleScene, HEIGHT, WIDTH


def test_breach_and_salvage_controls_apply_to_the_live_world(tmp_path: Path) -> None:
    game = Game("Hellward", backend="mock", resolution=(WIDTH, HEIGHT),
                asset_path=tmp_path / "cache", save_dir=tmp_path / "saves")
    try:
        scene = BattleScene(build(game, tmp_path / "cache"), GRAVEYARD)
        game.push(scene)
        world = scene.world
        assert world.breach_spec is not None
        world.wave = world.breach_spec.after_wave
        world.wave_alive[world.wave] = 0
        world.break_left = 10.0
        world.salvage_held = 2
        scene.draw()
        cash = next(c for c in scene.hud.controls if c.name == "breach:cash")
        sale = next(c for c in scene.hud.controls if c.name == "salvage:sell")
        assert cash.enabled and sale.enabled
        game.backend.inject_click(sale.box[0] + 5, sale.box[1] + 5)
        game.tick(SIM_DT)
        assert world.salvage_held == 1 and world.salvage_sold == 1
        assert scene.replay[-1][1:] == ["sell_salvage", 1]
        game.backend.inject_click(cash.box[0] + 5, cash.box[1] + 5)
        game.tick(SIM_DT)
        assert world.breach_mode == "cash"
        assert scene.replay[-1][1:] == ["breach", "cash"]
        assert not world.breach_offered
    finally:
        game.close()


def test_a_breach_replay_does_not_offer_a_trophy_already_forfeited(tmp_path: Path) -> None:
    game = Game("Hellward", backend="mock", resolution=(WIDTH, HEIGHT),
                asset_path=tmp_path / "cache", save_dir=tmp_path / "saves")
    try:
        scene = BattleScene(build(game, tmp_path / "cache"), GRAVEYARD, breach_claim="cash")
        game.push(scene)
        world = scene.world
        assert world.breach_spec is not None
        world.wave = world.breach_spec.after_wave
        world.wave_alive[world.wave] = 0
        world.break_left = 10.0
        scene.draw()
        cash = next(c for c in scene.hud.controls if c.name == "breach:cash")
        trophy = next(c for c in scene.hud.controls if c.name == "breach:trophy")
        assert cash.enabled
        assert not trophy.enabled
    finally:
        game.close()
