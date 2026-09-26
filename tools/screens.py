"""PNG frames of every screen through the real renderer, for looking at.

    uv run python tools/screens.py OUT [--only NAME,NAME] [--seconds 60] [--seed 1]

Writes ``OUT/<name>.png``: ``title``, ``map``, ``intro-<location>`` for every location,
``skills``, ``battle-<location>`` for every location, ``magic``, ``reckoning``, ``story-tristram-before``,
``prologue-12``, ``prologue-27`` and ``chronicle-first``.
The display must be awake (``caffeinate -u``). The frames are for looking at,
not for keeping in the repository.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("--only", default="", help="comma-separated frame names")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    from saga2d import Game

    from hellward.__main__ import build
    from hellward.sim import planner
    from hellward.sim.campaign import LOCATIONS
    from hellward.sim.content import Curse
    from hellward.sim.players.ordinary import Ordinary
    from hellward.sim.skills import perks
    from hellward.story import STORIES
    from hellward.ui.battle import BattleScene, Silent
    from hellward.ui.flow import Flow
    from hellward.ui.progress import Progress
    from hellward.ui.story import ChronicleScene, PrologueScene, StoryScene

    cache = Path.home() / ".hellward" / "cache"
    game = Game("Hellward", resolution=(1280, 800), backend="pyglet", visible=False,
                asset_path=cache, save_dir=args.out / "saves")
    art = build(game, cache)
    progress = Progress.load(game)
    progress.won = {"tristram": 3, "graveyard": 2, "cathedral": 1}
    progress.learned = frozenset({"fire_mastery", "fire_ball", "holy_shield", "warmth"})
    progress.at = "cathedral"
    flow = Flow(game, art, sound=Silent(), planner=planner.smart, settings=None,
                progress=progress, demo_player=Ordinary, seed=args.seed)

    def ticks(n: int) -> None:
        for _ in range(n):
            game.tick(1 / 30)

    def shot(name: str) -> None:
        game.backend.capture_frame().save(args.out / f"{name}.png")

    def title() -> None:
        flow.title()
        ticks(4)
        shot("title")

    def world_map() -> None:
        flow.world_map()
        ticks(6)
        shot("map")

    def make_intro(key: str):
        def intro() -> None:
            flow.intro(LOCATIONS[key])
            ticks(4)
            shot(f"intro-{key}")
        return intro

    def skills() -> None:
        flow.intro(LOCATIONS["graveyard"])
        flow.skills(LOCATIONS["graveyard"])
        ticks(4)
        shot("skills")

    def make_battle(key: str):
        def battle() -> None:
            progress.won = {k: 1 for k in LOCATIONS}   # the whole descent open, whatever the map frame showed
            flow.defend(LOCATIONS[key])
            scene = game.scenes[-1]
            scene.autopilot = Ordinary()
            scene.speed = 4.0
            while scene.world.time < args.seconds and scene.world.outcome is None:
                ticks(1)
            scene.speed = 1.0
            ticks(3)
            shot(f"battle-{key}")
        return battle

    def magic() -> None:
        scene = BattleScene(art, LOCATIONS["hells_gate"], seed=args.seed, planner=planner.smart,
                            autopilot=Ordinary(), perks=perks({"holy_shield", "salvation"}))
        game.clear_and_push(scene)
        world = scene.world
        scene.speed = 4.0
        while not any(m.chant_curse is not None for m in world.monsters) and world.time < 200:
            ticks(1)
        scene.speed = 1.0
        ticks(12)
        while not any(t.curses for t in world.towers.values()) and world.time < 200:
            ticks(1)
        ticks(4)
        towers = list(world.towers.values())
        towers[0].curses[Curse.BONE_PRISON] = 4.0
        if len(towers) > 1:
            towers[1].curses[Curse.DIM_VISION] = 6.0
            towers[1].curses[Curse.DECREPIFY] = 6.0
        if len(towers) > 2:
            towers[2].ward = 6.0
        world.mana = 400
        monsters = list(world.monsters)
        if monsters:
            x, y = world.level.point(monsters[0].s)
            world.orb(x, y)
            world.smite(monsters[-1].id)
            x2, y2 = world.level.point(monsters[len(monsters) // 2].s)
            world.meteor(x2, y2)
        ticks(3)
        shot("magic")

    def reckoning() -> None:
        flow.defend(LOCATIONS["tristram"])
        scene = game.scenes[-1]
        scene.autopilot = Ordinary()
        scene.speed = 4.0
        while scene.world.time < 150 and scene.world.outcome is None:
            ticks(1)
        scene.speed = 1.0
        ticks(3)
        scene.world.lives = 15
        scene.world.outcome = "victory"
        ticks(150)
        shot("reckoning")

    def story_page() -> None:
        game.clear_and_push(StoryScene(flow, STORIES["tristram/before"].pages, then=lambda: None))
        ticks(60)
        shot("story-tristram-before")

    def make_prologue(name: str, seconds: float):
        def prologue() -> None:
            game.clear_and_push(PrologueScene(flow, then=lambda: None))
            ticks(int(seconds * 30))
            shot(name)
        return prologue

    def chronicle_first() -> None:
        progress.won = {k: 1 for k in LOCATIONS}   # every before/after moment has come
        scene = ChronicleScene(flow, then=lambda: None)
        game.clear_and_push(scene)
        scene._prologue.clock = scene._prologue.end   # past the prologue, onto the first story page
        ticks(60)
        shot("chronicle-first")

    frames = {"title": title, "map": world_map, "skills": skills, "magic": magic, "reckoning": reckoning,
              "story-tristram-before": story_page, "prologue-12": make_prologue("prologue-12", 12.0),
              "prologue-27": make_prologue("prologue-27", 27.0), "chronicle-first": chronicle_first}
    for key in LOCATIONS:
        frames[f"intro-{key}"] = make_intro(key)
    for key in LOCATIONS:
        frames[f"battle-{key}"] = make_battle(key)
    only = {name for name in args.only.split(",") if name} or set(frames)
    unknown = only - set(frames)
    if unknown:
        parser.error(f"no frame named {', '.join(sorted(unknown))}; the frames: {', '.join(frames)}")
    for name in frames:
        if name in only:
            frames[name]()
    game.close()
    print(f"wrote {len(only)} frames to {args.out}")


if __name__ == "__main__":
    main()
