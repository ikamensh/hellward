"""Record Hellward through the real renderer: the scripted defender against the smart leaders.

    uv run python tools/showcase.py OUT                        # find the leaders' curses, film around them
    uv run python tools/showcase.py OUT --at 95,420 --seconds 7
    uv run python tools/showcase.py OUT --moments               # only list the moments worth filming

Writes ``clip.mp4`` (full size, 30 fps), ``clip.gif`` (smaller, for chat) and a still from the middle of every
shot. The fight is the one ``uv run hellward --demo --seed N`` plays: the same seed, the same defender, and
leaders that decide exactly as the game's worker would. The display must be awake (``caffeinate -u``).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def moments(seed: int, limit: float = 900.0) -> list[tuple[float, str]]:
    """Game times worth filming: a leader starting to curse, a gate breaking, the boss arriving."""
    from hellward.sim import planner
    from hellward.sim.autoplay import Defender
    from hellward.sim.model import SIM_DT, World

    world = World(seed=seed, planner=planner.smart)
    defender = Defender()
    found = []
    while world.outcome is None and world.time < limit:
        defender.act(world, SIM_DT)
        world.step(SIM_DT)
        for e in world.events:
            if e[0] == "chant":
                found.append((world.time, f"chant {world.monster(e[1]).kind.key if world.monster(e[1]) else '?'} wave {world.wave + 1}"))
            elif e[0] == "door_broken":
                found.append((world.time, f"gate {e[1]} broken"))
            elif e[0] == "wave" and e[1] == len(world.waves) - 1:
                found.append((world.time, "the boss wave"))
            elif e[0] in ("victory", "defeat"):
                found.append((world.time, e[0]))
        world.events.clear()
    return found


def film(out: Path, seed: int, shots: list[float], seconds: float, fps: int, lead: float) -> None:
    from saga2d import Game

    from hellward.__main__ import build
    from hellward.sim import planner
    from hellward.sim.autoplay import Defender
    from hellward.ui.battle import BattleScene

    frames_dir = out / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    cache = Path.home() / ".hellward" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    game = Game("Hellward", resolution=(1280, 800), backend="pyglet", visible=False, asset_path=cache)
    art = build(game, cache)
    scene = BattleScene(art, seed=seed, planner=planner.smart, autopilot=Defender())
    game.push(scene)
    index = 0
    dt = 1 / fps
    for shot in sorted(shots):
        start = max(0.0, shot - lead)
        scene.speed = 4.0
        while scene.world.time < start and scene.world.outcome is None:
            game.tick(1 / 30)
        scene.speed = 1.0
        taken = 0
        while taken < seconds * fps:
            game.tick(dt)
            image = game.backend.capture_frame().convert("RGB").resize((1280, 800))
            image.save(frames_dir / f"{index:05d}.png")
            if taken == int(lead * fps):
                image.save(out / f"still-{int(shot):04d}.png")
            index += 1
            taken += 1
    game.close()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames_dir / "%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out / "clip.mp4")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / "clip.mp4"), "-vf",
                    "fps=15,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=160[p];[b][p]paletteuse=dither=bayer",
                    str(out / "clip.gif")], check=True)
    shutil.rmtree(frames_dir)
    print(f"wrote {out / 'clip.mp4'}, {out / 'clip.gif'} and {len(shots)} stills")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--at", type=lambda s: [float(x) for x in s.split(",")], default=None, help="game times to film")
    parser.add_argument("--seconds", type=float, default=6.0)
    parser.add_argument("--lead", type=float, default=2.0, help="seconds filmed before each moment")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--moments", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    shots = args.at
    if shots is None or args.moments:
        found = moments(args.seed)
        for t, what in found:
            print(f"{t:7.1f}s  {what}")
        if args.moments:
            return
        chants = [t for t, what in found if what.startswith("chant")]
        picks = [chants[len(chants) // 4], chants[len(chants) // 2], chants[3 * len(chants) // 4]] if len(chants) >= 3 else chants
        boss = [t for t, what in found if what == "the boss wave"]
        shots = picks + [b + 30 for b in boss[:1]]
    film(args.out, args.seed, shots, args.seconds, args.fps, args.lead)


if __name__ == "__main__":
    main()
