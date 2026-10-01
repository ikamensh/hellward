"""Evenly spaced stills from a video as one contact sheet: uv run python tools/filmstrip.py VIDEO OUT.png [N] [--cols C]

To review a recording at a glance (tools/record.sh) without watching it.
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument("video", type=Path)
parser.add_argument("out", type=Path)
parser.add_argument("n", type=int, nargs="?", default=24)
parser.add_argument("--cols", type=int, default=6)
parser.add_argument("--width", type=int, default=2400)
args = parser.parse_args()
length = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                               str(args.video)], capture_output=True, text=True, check=True).stdout)
cell_w = args.width // args.cols
cell_h = cell_w * 9 // 16
rows = (args.n + args.cols - 1) // args.cols
sheet = Image.new("RGB", (cell_w * args.cols, cell_h * rows))
draw = ImageDraw.Draw(sheet)
with tempfile.TemporaryDirectory() as tmp:
    for i in range(args.n):
        t = length * (i + 0.5) / args.n
        frame = Path(tmp) / f"{i}.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(args.video), "-frames:v", "1",
                        str(frame)], check=True)
        x, y = (i % args.cols) * cell_w, (i // args.cols) * cell_h
        sheet.paste(Image.open(frame).convert("RGB").resize((cell_w, cell_h), Image.LANCZOS), (x, y))
        draw.text((x + 6, y + 4), f"{int(t // 60)}:{int(t % 60):02d}", fill=(255, 230, 150))
sheet.save(args.out)
print(args.out)
