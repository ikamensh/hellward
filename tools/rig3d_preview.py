"""Compare stepped sprites with continuous poses from the same 3D monster rig.

    uv run python tools/rig3d_preview.py /tmp/hellward-rig3d-preview

This is an offline animation experiment, not a replacement game renderer. Both
lanes use the same skeleton mesh, camera, materials, canvas, pivot, and travel
speed. Only pose sampling differs: eight held keys versus interpolated joints.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sagaforge import render3d as r3  # noqa: E402

from hellward.art import figures  # noqa: E402
from hellward.art.rig import DENSITY, PROJECTION, yaw  # noqa: E402
from hellward.sim.content import MONSTERS  # noqa: E402

KIND = "skeleton"
ANGLES = {-90: "right", -45: "front_right", 0: "front"}
FPS = 60
CYCLES = 4
STRIDE = figures.stride(KIND)
CYCLE_SECONDS = 8 * STRIDE / MONSTERS[KIND].speed
WALK = figures.walk(KIND)


def between(first: figures.Pose, second: figures.Pose, amount: float) -> figures.Pose:
    """Interpolate pose controls, including a limb's implicit opposite swing."""
    values: dict[str, float | int | None] = {}
    for field in fields(figures.Pose):
        name = field.name
        if name == "death":
            values[name] = 0
            continue
        a, b = getattr(first, name), getattr(second, name)
        if a is None and b is None:
            values[name] = None
            continue
        if a is None:
            a = -first.leg if name == "left_leg" else first.arm
        if b is None:
            b = -second.leg if name == "left_leg" else second.arm
        values[name] = a + (b - a) * amount
    return figures.Pose(**values)


def frame(phase: float, smooth: bool, angle: float = -90) -> Image.Image:
    index = int(phase) % len(WALK)
    if not smooth:
        bearing = ANGLES[round(angle / 45) * 45]
        return figures.render(KIND, bearing, WALK[index])
    pose = between(figures.pose_of(KIND, WALK[index]),
                   figures.pose_of(KIND, WALK[(index + 1) % len(WALK)]), phase % 1)
    model = r3.scale(yaw(figures.BUILDERS[KIND](pose), angle), figures.SCALE)
    size, origin = figures.cell(KIND)
    return r3.render(model, PROJECTION, scale=DENSITY, canvas=size, origin=origin)


def compose(stepped: Image.Image, smooth: Image.Image, phase: float, angle: float = -90) -> Image.Image:
    canvas = Image.new("RGB", (600, 350), (28, 25, 28))
    draw = ImageDraw.Draw(canvas)
    for lane, sprite, heading in ((0, stepped, "8 held poses / 45° bearings"),
                                  (1, smooth, "Continuous 3D pose + yaw")):
        x = 150 + 300 * lane
        draw.text((x - 105, 18), heading, fill=(238, 224, 202))
        draw.line((x - 125, 298, x + 125, 298), fill=(97, 78, 62), width=3)
        size, origin = figures.cell(KIND)
        position = (round(x - origin[0] * DENSITY), round(298 - origin[1] * DENSITY))
        canvas.paste(sprite, position, sprite)
        draw.ellipse((x - 2, 296, x + 2, 300), fill=(237, 103, 68))
    draw.text((155, 326), f"Same skeleton, camera, pivot and {MONSTERS[KIND].speed:g} tile/s speed  |  "
              f"walk {phase % 8:.2f}/8, yaw {angle:.0f}°", fill=(176, 162, 146))
    return canvas


def render(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    phases = [8 * index / (CYCLE_SECONDS * FPS) for index in range(round(CYCLE_SECONDS * FPS))]
    stepped = [frame(phase, False) for phase in phases]
    smooth = [frame(phase, True) for phase in phases]
    contact = Image.new("RGB", (600 * 4, 350 * 2), (28, 25, 28))
    for i in range(8):
        # Halfway between authored keys is where pose continuity differs.
        phase_index = round((i + .5) * len(phases) / 8)
        contact.paste(compose(stepped[phase_index], smooth[phase_index], phases[phase_index]),
                      ((i % 4) * 600, (i // 4) * 350))
    contact.save(out / "contact-sheet.png")

    process = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", "600x350", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-crf", "18", str(out / "walk-comparison.mp4")],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    assert process.stderr is not None
    for _ in range(CYCLES):
        for phase, held, interpolated in zip(phases, stepped, smooth):
            process.stdin.write(compose(held, interpolated, phase).tobytes())
    turn_frames = round(1.2 * FPS)
    for index in range(turn_frames):
        elapsed = index / FPS
        phase = 8 * elapsed / CYCLE_SECONDS
        angle = -90 + 90 * index / (turn_frames - 1)
        held, interpolated = frame(phase, False, angle), frame(phase, True, angle)
        process.stdin.write(compose(held, interpolated, phase, angle).tobytes())
    process.stdin.close()
    error = process.stderr.read().decode()
    if process.wait():
        raise RuntimeError(error)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    command = shlex.join(["uv", "run", "python", "tools/rig3d_preview.py", str(out)])
    (out / "README.txt").write_text(f"Source commit: {commit}\nReproduce: {command}\n", encoding="utf-8")
    print(f"Wrote {out / 'walk-comparison.mp4'} and {out / 'contact-sheet.png'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    render(parser.parse_args().out)
