"""Hellward: ``uv run hellward`` (``--demo`` lets the scripted defender play; ``--seed N`` changes the queues)."""

from __future__ import annotations

import argparse
from pathlib import Path

from saga2d import Game

from hellward.art import fx, sprites
from hellward.audio.bank import SoundBank
from hellward.sim.autoplay import Defender
from hellward.sim.level import CATHEDRAL
from hellward.sim.model import World
from hellward.ui import style
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene
from hellward.ui.thinking import Thinker
from hellward.ui.title import ReckoningScene, TitleScene

DATA = Path.home() / ".hellward"


def build(game: Game, cache: Path):
    style.load_fonts(game)
    game.theme = style.theme()
    art = sprites.register(game, CATHEDRAL, cache)
    fx.register(game)
    fx.register_ui(game)
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
    SoundBank.prepare(cache)
    art = build(game, cache)
    sound = SoundBank(game)
    thinker = Thinker()

    def title() -> None:
        game.replace(TitleScene(begin, game.quit))
        sound.music("title")

    def begin(autopilot: bool) -> None:
        game.replace(BattleScene(art, seed=args.seed, planner=thinker, sound=sound,
                                 autopilot=Defender() if autopilot else None, on_end=end))

    def end(world: World) -> None:
        game.push(ReckoningScene(world, again=lambda: begin(False), title=title))

    try:
        if args.demo:
            game.run(BattleScene(art, seed=args.seed, planner=thinker, sound=sound, autopilot=Defender(), on_end=end))
        else:
            sound.music("title")
            game.run(TitleScene(begin, game.quit))
    finally:
        thinker.close()


if __name__ == "__main__":
    main()
