"""Hellward: ``uv run hellward`` (``--demo`` lets the scripted defender play; ``--seed N`` changes the queues)."""

from __future__ import annotations

import argparse
import signal
from pathlib import Path

from saga2d import Game

from hellward.art import fx, sprites
from hellward.audio.bank import SoundBank
from hellward.sim.players.ordinary import Ordinary
from hellward.sim.model import World
from hellward.ui import menus, style
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene
from hellward.ui.thinking import Thinker
from hellward.ui.title import LoadingScene, ReckoningScene, TitleScene

DATA = Path.home() / ".hellward"


def build(game: Game, cache: Path):
    style.load_fonts(game)
    game.theme = style.theme()
    loading = LoadingScene()
    game.push(loading)
    game.tick(1 / 60)   # the first launch spends a while drawing textures and sounds: show that it is alive
    SoundBank.prepare(cache)
    art = sprites.register(game, cache)
    fx.register(game, cache)
    game.pop()
    return art


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Hellward — a gothic tower defence where demon leaders curse your towers")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--demo", action="store_true", help="skip the title and let the scripted defender play")
    parser.add_argument("--fullscreen", action="store_true")
    args = parser.parse_args(argv)
    cache = DATA / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    game = Game("Hellward", resolution=(WIDTH, HEIGHT), fullscreen=args.fullscreen, asset_path=cache,
                save_dir=DATA / "saves")
    # pyglet's Cocoa loop makes Ctrl-C end the process on the spot; Python's own handler lets it unwind instead
    signal.signal(signal.SIGINT, signal.default_int_handler)
    art = build(game, cache)
    values = menus.settings(game)
    menus.apply_volumes(game, values)
    if values["fullscreen"] and not args.fullscreen:
        game.set_fullscreen(True)   # --fullscreen is for this session; the saved choice is the settings
    sound = SoundBank(game)
    thinker = Thinker()

    def title() -> None:
        game.clear_and_push(TitleScene(begin, game.quit))   # from under a menu or the reckoning too
        sound.music("title")

    def battle(autopilot: bool) -> BattleScene:
        return BattleScene(art, seed=args.seed, planner=thinker, sound=sound, autopilot=Ordinary() if autopilot else None,
                           on_end=end, settings=values, restart=lambda: begin(autopilot), to_title=title)

    def begin(autopilot: bool) -> None:
        game.clear_and_push(battle(autopilot))

    def end(world: World) -> None:
        game.push(ReckoningScene(world, again=lambda: begin(False), title=title))

    try:
        if args.demo:
            game.run(battle(True))
        else:
            sound.music("title")
            game.run(TitleScene(begin, game.quit))
    except KeyboardInterrupt:
        pass   # Ctrl-C in the terminal: the player's way out, not an error
    finally:
        thinker.close()


if __name__ == "__main__":
    main()
