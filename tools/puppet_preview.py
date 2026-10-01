"""Inspect the painted 2.5D motion source through the real GPU renderer.

    caffeinate -u uv run python tools/puppet_preview.py OUT

This is the authoring pilot. Battle integration follows visual acceptance.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw
from saga2d import Game, RenderLayer, Scene, Sprite, SpriteAnchor

from hellward.art import puppet, sprites
from hellward.sim.campaign import TRISTRAM
from hellward.ui.puppet import PuppetBody


def record(out: Path) -> None:
    from hellward.__main__ import build

    out.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="hellward-puppet-preview-"))
    cache = Path.home() / ".hellward" / "cache"
    game = Game("Hellward painted puppet", resolution=(1280, 800), backend="pyglet", visible=False,
                asset_path=cache, save_dir=scratch / "saves")
    encoder = None
    try:
        puppet.register(game, puppet.KINDS)
        build(game, cache)
        scene = Scene()
        game.push(scene)
        scene.add_sprite(Sprite(sprites.ground(game, TRISTRAM), position=(0, 0),
                                anchor=SpriteAnchor.TOP_LEFT, size=(1280, 800), layer=RenderLayer.BACKGROUND))
        bodies = [(kind, facing, PuppetBody(scene, kind, facing))
                  for kind in puppet.KINDS for facing in puppet.BEARINGS]
        for i in range(len(bodies)):
            scene.add_sprite(Sprite("fx/shadow", position=(i % 8 * 155 + 95, i // 8 * 235 + 214),
                                    size=(29, 10), opacity=150, layer=RenderLayer.OBJECTS))
        encoder = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", "1280x800", "-r", "60", "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-crf", "18", str(out / "motions.mp4")], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert encoder.stdin is not None and encoder.stderr is not None
        frames = []
        pose_seconds = 0.0
        for index in range(420):
            clock = index / 60
            started = time.perf_counter()
            for i, (kind, facing, body) in enumerate(bodies):
                speed = {"fallen": 1.35, "skeleton": 1.0, "zombie": 0.6}[kind]
                body.update(facing, min(clock, 4.3) * speed, (i % 8) * 155 + 95, (i // 8) * 235 + 200,
                            hit=clock - 2 if 2 <= clock < 2.3 else -1,
                            attack=clock - 2.8 if 2.8 <= clock < 4.1 else -1,
                            death=clock - 4.3 if clock >= 4.3 else -1)
            pose_seconds += time.perf_counter() - started
            game.tick(1 / 60)
            frame = game.backend.capture_frame().convert("RGB").resize((1280, 800))
            draw = ImageDraw.Draw(frame)
            for i, (kind, facing, _) in enumerate(bodies):
                draw.text(((i % 8) * 155 + 50, (i // 8) * 235 + 90), kind + " " + facing, fill=(255, 236, 208))
            encoder.stdin.write(frame.tobytes())
            if index in (48, 123, 192, 270, 294, 324):
                frames.append(frame)
        encoder.stdin.close()
        error = encoder.stderr.read().decode()
        if encoder.wait():
            raise RuntimeError(error)
        encoder = None
        contact = Image.new("RGB", (3840, 1600))
        for i, frame in enumerate(frames):
            contact.paste(frame, (i % 3 * 1280, i // 3 * 800))
        contact.save(out / "contact-sheet.png")
        print(f"24 painted rigs, {len(bodies) * len(puppet.BONES)} parts: mean pose/update {pose_seconds / 420 * 1000:.2f}ms per frame")
        print(f"wrote {out / 'motions.mp4'}")
    finally:
        if encoder is not None:
            encoder.kill()
            encoder.wait()
        game.close()
        shutil.rmtree(scratch)


def record_battle(out: Path) -> None:
    """Compare the old paintings and new live rigs under the real battle clock."""
    from hellward.__main__ import build
    from hellward.sim.content import MONSTERS
    from hellward.sim.level import Level, Route
    from hellward.sim.model import Monster
    from hellward.ui.battle import BattleScene

    os.environ["HELLWARD_MONSTER_STYLE"] = "painted"
    os.environ.pop("HELLWARD_ART", None)
    os.environ.setdefault("SAGA2D_SILENT", "1")
    out.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="hellward-puppet-battle-"))
    cache = Path.home() / ".hellward" / "cache"
    game = Game("Hellward painted rig comparison", resolution=(1280, 800), backend="pyglet", visible=False,
                asset_path=cache, save_dir=scratch / "save")
    encoder = None
    try:
        puppet.register(game, puppet.KINDS)
        art = build(game, cache)
        art = replace(art, puppets=frozenset(puppet.KINDS), monster_style="puppet")
        lanes = [(kind, style, 3 + i * 2) for i, (kind, style) in enumerate(
                 (pair for kind in puppet.KINDS for pair in ((kind, "painted"), (kind, "puppet"))))]
        routes = tuple(Route(f"{kind}_{style}", ((0, y), (28, y), (28, 8), (32, 8))) for kind, style, y in lanes)
        level = Level("painted rig comparison", 33, 18, ((0, 8), (32, 8)), (), extra_routes=routes)
        scene = BattleScene(art, replace(TRISTRAM, level=level), seed=1, autopilot=None)
        game.push(scene)
        scene.hud.banners.clear()
        monsters = []
        figures_by_lane = []
        for i, (kind, style, _) in enumerate(lanes):
            scene.view.art = art if style == "puppet" else replace(art, puppets=frozenset())
            spec = MONSTERS[kind]
            monster = Monster(100 + i, spec, 0, 0.0, 0.0, spec.hp, 0.0, route=f"{kind}_{style}")
            monster.s = 6
            scene.world.monsters.append(monster)
            scene.view.spawn(monster)
            monsters.append(monster)
            figures_by_lane.append(scene.view.figures[monster.id])
        scene.view.art = art
        encoder = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", "1280x800", "-r", "60", "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-crf", "18", str(out / "battle.mp4")], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert encoder.stdin is not None and encoder.stderr is not None
        frames = []
        details = []
        for index in range(420):
            clock = index / 60
            if index == 120:
                for monster in monsters:
                    scene.view.hit(monster.id, "physical")
            if index == 168:
                scene.paused = True
                for monster in monsters:
                    monster.door = 0
            if index >= 168:
                scene.view.sync(1, 1 / 60, animation_dt=1 / 60)
            if index == 258:
                for monster in monsters:
                    scene.view.kill(monster.id)
                scene.world.monsters.clear()
            game.tick(1 / 60)
            frame = game.backend.capture_frame().convert("RGB").resize((1280, 800))
            draw = ImageDraw.Draw(frame)
            draw.text((18, 16), "Painted sprites / live painted 2.5D rigs • same battle", fill=(255, 235, 200))
            for kind, style, y in lanes:
                sx, sy = scene.camera.world_to_screen(80, y * 48)
                draw.text((round(sx), round(sy - 34)), f"{kind} {style}", fill=(255, 235, 200))
            encoder.stdin.write(frame.tobytes())
            if index in (48, 123, 193, 211, 270, 306):
                frames.append(frame)
                strip = Image.new("RGB", (6 * 160, 180), (24, 20, 23))
                for i, figure in enumerate(figures_by_lane):
                    sx, sy = scene.camera.world_to_screen(figure.x, figure.y)
                    crop = frame.crop((round(sx - 40), round(sy - 67), round(sx + 40), round(sy + 10)))
                    strip.paste(crop.resize((160, 154)), (i * 160, 26))
                labels = ImageDraw.Draw(strip)
                for i, (kind, style, _) in enumerate(lanes):
                    labels.text((i * 160 + 5, 3), f"{kind} {style}", fill=(255, 235, 200))
                details.append(strip)
        encoder.stdin.close()
        error = encoder.stderr.read().decode()
        if encoder.wait():
            raise RuntimeError(error)
        encoder = None
        contact = Image.new("RGB", (2560, 2400))
        detail = Image.new("RGB", (960, 1080))
        for i, (frame, strip) in enumerate(zip(frames, details)):
            contact.paste(frame, (i % 2 * 1280, i // 2 * 800))
            detail.paste(strip, (0, i * 180))
        contact.save(out / "battle-contact.png")
        detail.save(out / "battle-detail.png")
        print(f"wrote {out / 'battle.mp4'}")
    finally:
        if encoder is not None:
            encoder.kill()
            encoder.wait()
        game.close()
        shutil.rmtree(scratch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--battle", action="store_true", help="compare against painted sprites in the actual battle scene")
    args = parser.parse_args()
    (record_battle if args.battle else record)(args.out)
