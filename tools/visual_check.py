"""Render every screen and every location's battle and check each frame by machine (godot-capture.sh: no window).

    uv run python tools/visual_check.py OUT_DIR [--only NAME ...] [--baseline DIR]

Each shot is checked for what a person would notice at once: the capture ran without a script or engine error, its
frame is not blank (nearly one colour) nor black, and no patch of it is the flat magenta a missing texture draws.
With --baseline (an earlier OUT_DIR) each frame is also compared with the same shot there, and a large change is
reported for a look (not failed: particles, fog and the demo's battle differ run to run). OUT_DIR gets every
frame, sheet.png (all of them, labelled) and report.json; the exit status is 1 when a check failed.
Heavy: run it through ~/saga/tools/slot.py.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
GODOT = ROOT / "godot"
sys.path.insert(0, str(ROOT))

from hellward.sim.campaign import LOCATIONS  # noqa: E402

SCREENS = ["title", "profiles", "settings", "map", "briefing", "skills", "forge", "chronicle", "story",
           "prologue", "pause", "reckoning"]
# lines a capture prints that are not failures (Godot's own notices)
BENIGN = re.compile(r"Vulkan|MoltenVK|Metal|ObjectDB instances leaked|resources still in use|--- Debugging")


def shots(only: list[str]) -> list[tuple[str, list[str]]]:
    """(name, capture arguments) for every screen and every location's battle."""
    out = []
    for s in SCREENS:
        screen, _, act = s.partition(":")
        args = ["scene=res://scenes/game.tscn", f"screen={screen}", "frames=90"]
        if act:
            args.append(f"act={act}")
        if screen in ("briefing", "story"):
            args.append("location=tristram")
        out.append((f"screen_{s.replace(':', '_')}", args))
    for key in LOCATIONS:
        out.append((f"battle_{key}", ["scene=res://scenes/main.tscn", "shot=overview", "frames=600", "demo",
                                      f"location={key}", "timeout=240"]))
    return [s for s in out if not only or any(o in s[0] for o in only)]


def capture(name: str, args: list[str], out: Path) -> list[str]:
    """Render one shot into out/<name>.png; returns the error lines the run printed."""
    png = out / f"{name}.png"
    png.unlink(missing_ok=True)
    cmd = [str(GODOT / "tools" / "godot-capture.sh"), "--path", "game", "--fixed-fps", "30", "res://scenes/capture.tscn",
           "--", *args, f"snap={png}"]
    run = subprocess.run(cmd, cwd=GODOT, capture_output=True, text=True, timeout=900)
    log = (run.stdout + run.stderr).splitlines()
    return [l.strip() for l in log if re.search(r"SCRIPT ERROR|^ERROR|^\s*ERROR:", l) and not BENIGN.search(l)]


def checks(png: Path) -> list[str]:
    """What is wrong with a frame at a glance."""
    if not png.is_file():
        return ["no frame was saved"]
    a = np.asarray(Image.open(png).convert("RGB"), dtype=np.float32) / 255.0
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    problems = []
    if lum.std() < 0.02:
        problems.append(f"blank: nearly one colour (spread {lum.std():.3f})")
    if lum.mean() < 0.02:
        problems.append(f"black (mean {lum.mean():.3f})")
    magenta = (a[..., 0] > 0.9) & (a[..., 2] > 0.9) & (a[..., 1] < 0.15)
    if magenta.mean() > 0.002:
        problems.append(f"{magenta.mean() * 100:.1f}% flat magenta (a missing texture)")
    return problems


def change(png: Path, base: Path) -> float | None:
    """How far a frame moved from its baseline: mean absolute difference of the two at 1/8 size, 0..1."""
    if not base.is_file():
        return None
    small = [np.asarray(Image.open(p).convert("L").resize((240, 135)), dtype=np.float32) / 255.0 for p in (png, base)]
    return float(np.abs(small[0] - small[1]).mean())


def sheet(out: Path, names: list[str], report: dict) -> None:
    w, h, cols = 480, 270, 4
    rows = (len(names) + cols - 1) // cols
    img = Image.new("RGB", (w * cols, (h + 22) * rows), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    for i, n in enumerate(names):
        x, y = (i % cols) * w, (i // cols) * (h + 22)
        png = out / f"{n}.png"
        if png.is_file():
            img.paste(Image.open(png).convert("RGB").resize((w, h)), (x, y + 22))
        bad = report[n]["problems"]
        draw.text((x + 6, y + 5), n + ("  FAILED: " + bad[0] if bad else ""), fill=(255, 90, 80) if bad else (220, 220, 200))
    img.save(out / "sheet.png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--baseline", type=Path)
    a = ap.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, args in shots(a.only):
        errors = capture(name, args, out)
        problems = checks(out / f"{name}.png") + [f"log: {e}" for e in errors[:3]]
        moved = change(out / f"{name}.png", a.baseline / f"{name}.png") if a.baseline else None
        report[name] = {"problems": problems, "change": moved}
        note = "; ".join(problems) or "ok"
        if moved is not None and moved > 0.08:
            note += f"  (changed {moved:.2f} from the baseline: look at it)"
        print(f"{name:24s} {note}", flush=True)
    sheet(out, list(report), report)
    (out / "report.json").write_text(json.dumps(report, indent=1))
    failed = [n for n, r in report.items() if r["problems"]]
    print(f"\n{len(report) - len(failed)} of {len(report)} shots pass; sheet: {out / 'sheet.png'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
