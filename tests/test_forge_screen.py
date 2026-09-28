"""Forging in the campaign screen changes the next live defence."""

from pathlib import Path

from saga2d import Game

from hellward.__main__ import build
from hellward.sim import planner
from hellward.sim.campaign import CATHEDRAL, GRAVEYARD
from hellward.sim.content import TOWERS
from hellward.ui.battle import BattleScene, Silent
from hellward.ui.flow import Flow
from hellward.ui.forge import ForgeScene
from hellward.ui.progress import Progress


def test_forged_pattern_is_equipped_and_applied_to_next_defence(tmp_path: Path) -> None:
    game = Game("Hellward", backend="mock", resolution=(1280, 800),
                asset_path=tmp_path / "cache", save_dir=tmp_path / "saves")
    try:
        progress = Progress.load(game)
        progress.record_result("tristram", "victory", 18, salvage=3)
        flow = Flow(game, build(game, tmp_path / "cache"), sound=Silent(), planner=planner.smart,
                    settings=None, progress=progress, demo_player=lambda: None)
        flow.forge()
        game.tick(1 / 30)
        screen = game.scenes[-1]
        assert isinstance(screen, ForgeScene)
        choice = next(spot for spot in screen.spots if spot.name == "honed_string")
        assert choice.enabled
        game.backend.inject_click(choice.box[0] + 5, choice.box[1] + 5)
        game.tick(1 / 30)
        assert "honed_string" in progress.patterns
        assert progress.loadout.equipped == ("honed_string",)
        assert progress.salvage == 0
        flow.defend(GRAVEYARD)
        battle = game.scenes[-1]
        assert isinstance(battle, BattleScene)
        assert battle.world.tower_levels["arrow"][0].damage == TOWERS["arrow"].levels[0].damage + 1
    finally:
        game.close()


def test_a_won_breach_and_unsold_drops_reach_the_forge_in_the_same_campaign(tmp_path: Path) -> None:
    game = Game("Hellward", backend="mock", resolution=(1280, 800),
                asset_path=tmp_path / "cache", save_dir=tmp_path / "saves")
    try:
        progress = Progress.load(game)
        progress.record("tristram", "victory", 18)
        flow = Flow(game, build(game, tmp_path / "cache"), sound=Silent(), planner=planner.smart,
                    settings=None, progress=progress, demo_player=lambda: None)
        flow.defend(GRAVEYARD)
        battle = game.scenes[-1]
        assert isinstance(battle, BattleScene)
        world = battle.world
        world.salvage_held = 3
        world.breach_mode = "trophy"
        world.breach_cleared = True
        world.lives = 18
        world.outcome = "victory"
        game.tick(1 / 30)
        assert (flow.reward.salvage, flow.reward.trophy) == (3, "graveyard")
        assert Progress.load(game).trophies == {"graveyard"}
        flow.forge()
        game.tick(1 / 30)
        forge = game.scenes[-1]
        assert isinstance(forge, ForgeScene)
        choice = next(spot for spot in forge.spots if spot.name == "honed_string")
        game.backend.inject_click(choice.box[0] + 5, choice.box[1] + 5)
        game.tick(1 / 30)
        flow.defend(CATHEDRAL)
        next_battle = game.scenes[-1]
        assert isinstance(next_battle, BattleScene)
        assert next_battle.world.loadout.equipped == ("honed_string",)
        assert Progress.load(game).trophies == {"graveyard"}
    finally:
        game.close()
