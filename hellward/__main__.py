"""Hellward: ``uv run hellward`` (``--profile NAME`` plays a separate campaign;
``--demo`` lets a strong scripted player defend the Cathedral; ``--seed N`` changes the queues)."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from pathlib import Path

from saga2d import Game

from hellward.sim import fastsim
from hellward.ui import style
from hellward.ui.loading import LoadingScene

DATA = Path.home() / ".hellward"

COMPILE_MESSAGE = "Compiling the leaders' minds (first launch only)..."


def profile_name(value: str) -> str:
    if not value.isidentifier():
        raise argparse.ArgumentTypeError("profile name must be a simple word (letters, numbers, underscores)")
    return value


def build(game: Game, cache: Path):
    from hellward.art import fx, sprites
    from hellward.audio.bank import SoundBank

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


def _needs_build() -> bool:
    """Whether activation would have to compile: no opt-out, no inherited build, and none on disk yet."""
    if os.environ.get(fastsim.OPT_OUT) or os.environ.get(fastsim.ENV):
        return False
    return not (fastsim.BUILDS / fastsim.key()).is_dir()


def _activate(game: Game) -> None:
    """Run the compiled simulation, building it first when the sources changed.

    A build already on disk attaches instantly. A first launch compiles (up to a minute) in a background
    thread while the window keeps ticking the loading scene; anything else failing raises, but a machine
    without a toolchain just runs the source and says so once.
    """
    if not _needs_build():
        try:
            fastsim.activate()
        except fastsim.NoToolchain as missing:
            print(f"hellward: {missing}; running the source simulation", file=sys.stderr, flush=True)
        return
    style.load_fonts(game)
    game.theme = style.theme()
    game.push(LoadingScene(COMPILE_MESSAGE))
    game.tick(1 / 60)
    outcome: dict = {}

    def _compile() -> None:
        try:
            outcome["path"] = fastsim.build()
        except Exception as failed:   # re-raised below, in this thread
            outcome["error"] = failed

    worker = threading.Thread(target=_compile, name="hellward-fastsim-build", daemon=True)
    worker.start()
    while worker.is_alive():
        game.tick(1 / 60)
    worker.join()
    game.pop()
    failed = outcome.get("error")
    if failed is not None:
        if isinstance(failed, fastsim.NoToolchain):
            print(f"hellward: {failed}; running the source simulation", file=sys.stderr, flush=True)
            return
        raise failed
    fastsim.attach(outcome["path"])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Hellward — a gothic tower defence where demon leaders curse your towers")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--profile", type=profile_name, default="main",
                        help="campaign profile; main keeps the existing save")
    parser.add_argument("--demo", action="store_true", help="skip the title and let the scripted defender play")
    parser.add_argument("--fullscreen", action="store_true")
    args = parser.parse_args(argv)
    cache = DATA / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    # 1280x800 mirrors hellward.ui.battle.WIDTH/HEIGHT, which cannot be imported before the simulation is activated
    game = Game("Hellward", resolution=(1280, 800), fullscreen=args.fullscreen, asset_path=cache,
                save_dir=DATA / "saves")
    # pyglet's Cocoa loop makes Ctrl-C end the process on the spot; Python's own handler lets it unwind instead
    signal.signal(signal.SIGINT, signal.default_int_handler)
    _activate(game)
    from hellward.audio.bank import SoundBank
    from hellward.sim.players.adaptive import Adaptive
    from hellward.ui import menus
    from hellward.ui.flow import Flow
    from hellward.ui.progress import Progress
    from hellward.ui.thinking import Thinker
    from hellward.ui.title import TitleScene

    art = build(game, cache)
    values = menus.settings(game)
    menus.apply_volumes(game, values)
    if values["fullscreen"] and not args.fullscreen:
        game.set_fullscreen(True)   # --fullscreen is for this session; the saved choice is the settings
    sound = SoundBank(game)
    thinker = Thinker()
    flow = Flow(game, art, sound=sound, planner=thinker, settings=values,
                progress=Progress.load(game, args.profile),
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
