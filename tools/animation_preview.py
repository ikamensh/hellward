"""Review the first three monsters' animations through Hellward's real renderer.

    caffeinate -u uv run python tools/animation_preview.py /tmp/hellward-animation-preview
    caffeinate -u uv run python tools/animation_preview.py /tmp/hellward-animation-3d --art procedural

Writes a 60 fps MP4, ordered eight-frame walk cycles, an action contact sheet,
and reproduction details. Walking and walk-to-hit transitions use BattleScene's
normal 20 Hz rules steps and interpolated 60 Hz draws at each monster's own
speed. Door blows and deaths hold the rules clock for a reproducible review.
Every picture uses the game's real Sprite, camera and pyglet backend.
"""

from __future__ import annotations

import argparse
import math
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KINDS = ("fallen", "skeleton", "zombie")
TOUR = ((0, 4), (6, 4), (9, 7), (9, 10), (6, 13), (3, 13), (1, 11), (1, 7), (4, 4), (32, 8))
BEARINGS = ("right", "front_right", "front", "front_left", "left", "back_left", "back", "back_right")
REACTIONS = (("front", 2), ("right", 0), ("front_right", 1))
DOORS = (("front_right", 1), ("right", 0))
CROP = (150, 170)


def midpoint(route, leg: int) -> float:
    before = sum(math.dist(a, b) for a, b in zip(route.waypoints[:leg], route.waypoints[1:leg + 1]))
    return before + math.dist(route.waypoints[leg], route.waypoints[leg + 1]) / 2


def _crop(frame: Image.Image, scene, figure) -> Image.Image:
    sx, sy = scene.camera.world_to_screen(figure.x, figure.y)
    return frame.crop((round(sx - CROP[0] / 2), round(sy - CROP[1] + 60),
                       round(sx + CROP[0] / 2), round(sy + 60)))


def _sheet(cells: dict[tuple[str, str, str], Image.Image], out: Path, reactions: tuple[str, ...],
           doors: tuple[str, ...], door_frames: tuple[str, ...], fps: int, art_mode: str) -> None:
    pad, heading, label = 10, 28, 24
    width = pad + len(BEARINGS) * (CROP[0] + pad)
    height = heading + len(KINDS) * (1 + len(reactions) + len(doors)) * (CROP[1] + label + pad)
    sheet = Image.new("RGB", (width, height), (24, 20, 23))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((pad, 8), f"Hellward: {art_mode} walk, hit, death • real {fps} fps renderer",
              fill=(235, 224, 205), font=font)
    for kind_index, kind in enumerate(KINDS):
        for group_index, group in enumerate(("walk", *reactions, *doors)):
            row = kind_index * (1 + len(reactions) + len(doors)) + group_index
            y = heading + row * (CROP[1] + label + pad)
            names = (BEARINGS if group == "walk" else door_frames if group in doors else
                     ("hit1", "hit2", "hit3", "death1", "death2", "death3", "death4", "death5"))
            for col, name in enumerate(names):
                x = pad + col * (CROP[0] + pad)
                sheet.paste(cells[(kind, group, name)], (x, y))
                draw.text((x + 2, y + CROP[1] + 4), f"{kind}  {group}  {name}", fill=(235, 224, 205), font=font)
    sheet.save(out)


def _walk_sheet(cells: dict[tuple[str, str, str], Image.Image], out: Path, fps: int, art_mode: str) -> None:
    """Show every bearing in playback order, including the transition from step 8 to 1."""
    from hellward.art import figures

    pad, heading, label = 10, 28, 24
    width = pad + 8 * (CROP[0] + pad)
    height = heading + len(KINDS) * len(BEARINGS) * (CROP[1] + label + pad)
    sheet = Image.new("RGB", (width, height), (24, 20, 23))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 8), f"Hellward: {art_mode} ordered 1x walk cycles • {fps} fps real renderer",
              fill=(235, 224, 205))
    for kind_index, kind in enumerate(KINDS):
        for facing_index, bearing in enumerate(BEARINGS):
            row = kind_index * len(BEARINGS) + facing_index
            y = heading + row * (CROP[1] + label + pad)
            for col, frame in enumerate(figures.walk(kind)):
                x = pad + col * (CROP[0] + pad)
                sheet.paste(cells[(kind, bearing, frame)], (x, y))
                draw.text((x + 2, y + CROP[1] + 4), f"{kind}  {bearing}  {frame}",
                          fill=(235, 224, 205))
    sheet.save(out)


def record(out: Path, fps: int, art_mode: str = "painted") -> None:
    os.environ["HELLWARD_ART"] = art_mode
    from saga2d import Game

    from hellward.__main__ import build
    from hellward.art import figures
    from hellward.sim.campaign import TRISTRAM
    from hellward.sim.content import MONSTERS
    from hellward.sim.level import Level, Route
    from hellward.sim.model import SIM_DT, Monster
    from hellward.ui.battle import HEIGHT, WIDTH, BattleScene
    from hellward.ui.view import HIT_FRAME_DT, T

    class AnimationScene(BattleScene):
        """Run ordinary travel, but allow staged actions without changing the HUD pace."""

        staged = False

        def update(self, dt: float) -> None:
            if not self.staged:
                super().update(dt)
                return
            self.speed = 0.0
            try:
                super().update(dt)
            finally:
                self.speed = 1.0

    os.environ.setdefault("SAGA2D_SILENT", "1")
    out.mkdir(parents=True, exist_ok=True)
    cache = Path.home() / ".hellward" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="hellward-animation-"))
    game = Game("Hellward animation preview", resolution=(WIDTH, HEIGHT), backend="pyglet", visible=False,
                asset_path=cache, save_dir=scratch / "saves")
    encoder = None
    try:
        art = build(game, cache)
        if art_mode == "painted":
            for kind in KINDS:
                expected = {f"{facing}/{frame}" for facing in figures.facings(kind) for frame in figures.frames(kind)}
                if set(art.monster_painted[kind]) != expected:
                    raise RuntimeError(f"{kind}: preview requires all {len(expected)} frames painted")
        level = Level("animation bearings", 33, 18, ((0, 8), (32, 8)), (),
                      extra_routes=(Route("tour", TOUR),))
        scene = AnimationScene(art, replace(TRISTRAM, level=level), seed=1, autopilot=None)
        game.push(scene)
        scene.hud.banners.clear()
        route = level.route("tour")
        dt = 1 / fps

        encoder = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{WIDTH}x{HEIGHT}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-crf", "20", str(out / "clip.mp4")],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        assert encoder.stdin is not None
        assert encoder.stderr is not None
        cells: dict[tuple[str, str, str], Image.Image] = {}
        walk_cells: dict[tuple[str, str, str], Image.Image] = {}
        font = ImageFont.load_default()

        def capture(label: str) -> Image.Image:
            game.tick(dt)
            # The pyglet capture is in physical pixels on Retina displays;
            # camera coordinates and the film are in Hellward's logical pixels.
            frame = game.backend.capture_frame().convert("RGB").resize((WIDTH, HEIGHT))
            annotated = frame.copy()
            ImageDraw.Draw(annotated).text((20, 18), label, fill=(255, 238, 210), font=font)
            encoder.stdin.write(annotated.tobytes())
            return frame

        for index, kind in enumerate(KINDS):
            scene.staged = False
            scene.acc = 0.0
            spec = MONSTERS[kind]
            monster = Monster(100 + index, spec, 0, 0.0, 0.0, spec.hp, 0.0, route="tour")
            monster.s = midpoint(route, 0)
            scene.world.monsters.append(monster)
            scene.view.spawn(monster)
            figure = scene.view.figures[monster.id]

            for leg, bearing in enumerate(BEARINGS):
                center = midpoint(route, leg)
                stride = figures.stride(kind)
                cycle = len(figures.walk(kind)) * stride
                # Start at phase one, safely inside the straight leg. The normal
                # world step and BattleScene interpolation do the rest.
                monster.s = round((center - cycle / 2) / cycle) * cycle + 0.1 * stride
                figure.prev = monster.s
                scene.acc = 0.0
                scene.view.sync(1.0, 0.0, animation_dt=0.0)
                seen: list[str] = []
                previous_position = (figure.x, figure.y)
                for _ in range(math.ceil((cycle / spec.speed + SIM_DT + 0.3) * fps)):
                    frame = capture(f"{kind} — {bearing} walk at 1x")
                    position = (figure.x, figure.y)
                    if math.dist(previous_position, position) > spec.speed * T / fps + 0.1:
                        raise RuntimeError(f"{kind} {bearing}: preview jumped between drawn frames")
                    previous_position = position
                    frame_name = figure.sprite.image.rsplit("/", 1)[-1]
                    if not seen or frame_name != seen[-1]:
                        seen.append(frame_name)
                    key = (kind, bearing, frame_name)
                    if frame_name in figures.walk(kind) and key not in walk_cells:
                        walk_cells[key] = _crop(frame, scene, figure)
                    if seen == [*figures.walk(kind), "walk1"]:
                        break
                if seen != [*figures.walk(kind), "walk1"]:
                    raise RuntimeError(f"{kind} {bearing}: incomplete ordered walk cycle {seen}")
                cells[(kind, "walk", bearing)] = walk_cells[(kind, bearing, "walk1")]

            scene.staged = True
            scene.acc = 0.0
            for bearing, leg in DOORS:
                monster.s = midpoint(route, leg)
                figure.prev = monster.s
                scene.view.sync(1.0, 0.0, animation_dt=0.0)
                monster.door = 0
                for _ in range(fps):
                    scene.view.sync(1.0, dt, animation_dt=dt)
                    frame = capture(f"{kind} — {bearing} door strike")
                    frame_name = figure.sprite.image.rsplit("/", 1)[-1]
                    key = (kind, f"door_{bearing}", frame_name)
                    if frame_name in figures.STRIKE and key not in cells:
                        cells[key] = _crop(frame, scene, figure)
                monster.door = -1
                scene.view.sync(1.0, 0.0, animation_dt=0.0)

            for action_index, (bearing, leg) in enumerate(REACTIONS):
                if action_index:
                    scene.view.spawn(monster)
                    figure = scene.view.figures[monster.id]
                scene.staged = False
                scene.acc = 0.0
                monster.s = midpoint(route, leg) - 0.3
                figure.prev = monster.s
                scene.view.sync(1.0, 0.0, animation_dt=0.0)
                for _ in range(round(0.18 * fps)):
                    capture(f"{kind} — {bearing} walk before hit")
                scene.view.hit(monster.id, "physical")
                recovered = False
                for _ in range(math.ceil((len(figures.hit_frames(kind)) * HIT_FRAME_DT + 0.25) * fps)):
                    frame = capture(f"{kind} — {bearing} hit")
                    frame_name = figure.sprite.image.rsplit("/", 1)[-1]
                    key = (kind, bearing, frame_name)
                    if frame_name in figures.hit_frames(kind) and key not in cells:
                        cells[key] = _crop(frame, scene, figure)
                    if frame_name in figures.walk(kind):
                        recovered = True
                if not recovered:
                    raise RuntimeError(f"{kind} {bearing}: hit never returned to the walk")

                scene.staged = True
                scene.acc = 0.0
                scene.view.kill(monster.id)
                for _ in range(2 * fps):
                    scene.view.sync(1.0, dt, animation_dt=dt)
                    frame = capture(f"{kind} — {bearing} death")
                    if figure.sprite.is_removed:
                        break
                    frame_name = figure.sprite.image.rsplit("/", 1)[-1]
                    key = (kind, bearing, frame_name)
                    if frame_name in figures.death_frames(kind) and key not in cells:
                        cells[key] = _crop(frame, scene, figure)
                if not figure.sprite.is_removed:
                    raise RuntimeError(f"{kind} {bearing} death never completed")
            scene.world.monsters.remove(monster)

        missing = [(kind, "walk", bearing) for kind in KINDS for bearing in BEARINGS
                   if (kind, "walk", bearing) not in cells]
        missing += [(kind, bearing, frame) for kind in KINDS for bearing in BEARINGS
                    for frame in figures.walk(kind) if (kind, bearing, frame) not in walk_cells]
        missing += [(kind, bearing, frame) for kind in KINDS for bearing, _ in REACTIONS
                    for frame in (*figures.hit_frames(kind), *figures.death_frames(kind))
                    if (kind, bearing, frame) not in cells]
        missing += [(kind, f"door_{bearing}", frame) for kind in KINDS for bearing, _ in DOORS
                    for frame in figures.STRIKE if (kind, f"door_{bearing}", frame) not in cells]
        if missing:
            raise RuntimeError(f"preview missed animation frames: {missing}")
        _sheet(cells, out / "contact-sheet.png", tuple(bearing for bearing, _ in REACTIONS),
               tuple(f"door_{bearing}" for bearing, _ in DOORS), figures.STRIKE, fps, art_mode)
        _walk_sheet(walk_cells, out / "walk-cycles.png", fps, art_mode)
        encoder.stdin.close()
        stderr = encoder.stderr.read().decode()
        if encoder.wait() != 0:
            raise RuntimeError(f"ffmpeg failed:\n{stderr}")
        encoder = None

        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        command = shlex.join(["caffeinate", "-u", "uv", "run", "python", "tools/animation_preview.py", str(out),
                               "--fps", str(fps), "--art", art_mode])
        (out / "README.txt").write_text(f"Source commit: {commit}\nReproduce: {command}\n", encoding="utf-8")
        print(f"wrote {out / 'walk-cycles.png'}, {out / 'contact-sheet.png'} and {out / 'clip.mp4'}")
    finally:
        if encoder is not None:
            encoder.kill()
            encoder.wait()
        game.close()
        shutil.rmtree(scratch)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--art", choices=("painted", "procedural"), default="painted")
    args = parser.parse_args()
    if args.fps < 24:
        parser.error("fps must be at least 24 to capture every hit and death pose")
    record(args.out, args.fps, args.art)


if __name__ == "__main__":
    main()
