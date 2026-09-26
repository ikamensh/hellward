"""Hellward: ``uv run hellward`` (``--demo`` lets a strong scripted player defend the Cathedral; ``--seed N`` changes
the queues)."""

from __future__ import annotations

import argparse
import signal
from pathlib import Path

from saga2d import Game

from hellward.art import fx, sprites
from hellward.audio.bank import SoundBank
from hellward.sim.players.adaptive import Adaptive
from hellward.ui import menus, style
from hellward.ui.battle import HEIGHT, WIDTH
from hellward.ui.flow import Flow
from hellward.ui.progress import Progress
from hellward.ui.thinking import Thinker
from hellward.ui.title import LoadingScene, TitleScene

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
    flow = Flow(game, art, sound=sound, planner=thinker, settings=values, progress=Progress.load(game),
                demo_player=Adaptive, seed=args.seed)

    try:
        if args.demo:
            game.run(flow.demo_scene())
        else:
            sound.music("title")
            game.run(TitleScene(flow))
    except KeyboardInterrupt:
        pass   # Ctrl-C in the terminal: the player's way out, not an error
    finally:
        thinker.close()


if __name__ == "__main__":
    main()
