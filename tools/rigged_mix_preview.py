"""Capture painted and baked 3D monsters together in the real battle renderer.

    caffeinate -u uv run python tools/rigged_mix_preview.py /tmp/hellward-rigged-mix

Four ordinary spawns use the game's mixed style assignment. The clip includes
walking, a hit, and death, all with the actual battle clock and sprite path.
"""

from __future__ import annotations

import os
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FPS = 60
SECONDS = 5.0
LANES = (("skeleton", "painted", 4), ("skeleton", "rigged", 7),
         ("zombie", "painted", 10), ("zombie", "rigged", 13))


def _id_for(kind: str, style: str, used: set[int]) -> int:
    want = style == "rigged"
    return next(i for i in range(100, 300) if i not in used
                and bool(random.Random(f"{kind}:{i}").getrandbits(1)) == want)


def record(out: Path) -> None:
    os.environ["HELLWARD_MONSTER_STYLE"] = "mixed"
    os.environ.pop("HELLWARD_ART", None)
    os.environ.setdefault("SAGA2D_SILENT", "1")

    from saga2d import Game

    from hellward.__main__ import build
    from hellward.sim.campaign import TRISTRAM
    from hellward.sim.content import MONSTERS
    from hellward.sim.level import Level, Route
    from hellward.sim.model import Monster
    from hellward.ui.battle import HEIGHT, WIDTH, BattleScene

    out.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="hellward-rigged-preview-"))
    cache = Path.home() / ".hellward" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    game = Game("Hellward rigged comparison", resolution=(WIDTH, HEIGHT), backend="pyglet",
                visible=False, asset_path=cache, save_dir=scratch / "saves")
    encoder = None
    try:
        art = build(game, cache)
        routes = tuple(Route(f"{kind}_{style}", ((0, y), (28, y), (28, 8), (32, 8)))
                       for kind, style, y in LANES)
        level = Level("rigged comparison", 33, 18, ((0, 8), (32, 8)), (), extra_routes=routes)
        scene = BattleScene(art, replace(TRISTRAM, level=level), seed=1, autopilot=None)
        game.push(scene)
        scene.hud.banners.clear()
        monster_ids: list[int] = []
        used_ids: set[int] = set()
        for kind, style, _ in LANES:
            spec = MONSTERS[kind]
            monster_id = _id_for(kind, style, used_ids)
            used_ids.add(monster_id)
            monster = Monster(monster_id, spec, 0, 0.0, 0.0, spec.hp, 0.0, route=f"{kind}_{style}")
            monster.s = 5.0
            scene.world.monsters.append(monster)
            scene.view.spawn(monster)
            assert scene.view.figures[monster_id].rigged == (style == "rigged")
            monster_ids.append(monster_id)

        encoder = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-crf", "18", str(out / "mixed-in-game.mp4")],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert encoder.stdin is not None and encoder.stderr is not None
        review: list[Image.Image] = []
        for index in range(round(FPS * SECONDS)):
            if index == round(2.0 * FPS):
                for monster_id in monster_ids:
                    scene.view.hit(monster_id, "physical")
            if index == round(3.5 * FPS):
                for monster_id in monster_ids:
                    scene.view.kill(monster_id)
                scene.world.monsters.clear()
            game.tick(1 / FPS)
            frame = game.backend.capture_frame().convert("RGB").resize((WIDTH, HEIGHT))
            draw = ImageDraw.Draw(frame)
            draw.text((18, 16), "Same battle: painted (upper lane) / baked rigged 3D (lower lane)",
                      fill=(255, 235, 200), stroke_width=2, stroke_fill=(18, 14, 16))
            for kind, style, y in LANES:
                x, sy = scene.camera.world_to_screen(96, y * 48)
                draw.text((round(x), round(sy - 42)), f"{kind}  {style}", fill=(255, 235, 200),
                          stroke_width=2, stroke_fill=(18, 14, 16))
            encoder.stdin.write(frame.tobytes())
            if index in (round(1.0 * FPS), round(2.06 * FPS), round(3.7 * FPS), round(4.05 * FPS)):
                review.append(frame)
        encoder.stdin.close()
        stderr = encoder.stderr.read().decode()
        if encoder.wait():
            raise RuntimeError(f"ffmpeg failed:\n{stderr}")
        encoder = None
        contact = Image.new("RGB", (WIDTH * 2, HEIGHT * 2))
        for i, frame in enumerate(review):
            contact.paste(frame, ((i % 2) * WIDTH, (i // 2) * HEIGHT))
        contact.save(out / "contact-sheet.png")
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        command = shlex.join(["caffeinate", "-u", "uv", "run", "python", "tools/rigged_mix_preview.py", str(out)])
        (out / "README.txt").write_text(f"Source commit: {commit}\nReproduce: {command}\n", encoding="utf-8")
        print(f"wrote {out / 'mixed-in-game.mp4'} and {out / 'contact-sheet.png'}")
    finally:
        if encoder is not None:
            encoder.kill()
            encoder.wait()
        game.close()
        shutil.rmtree(scratch)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: rigged_mix_preview.py OUT")
    record(Path(sys.argv[1]))
