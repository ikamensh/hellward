"""Tile PNG frames into one contact sheet: python3 tools/sheet.py OUT.png FRAME... [--cols N] [--width W]"""
import argparse
from pathlib import Path

from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument("out", type=Path)
parser.add_argument("frames", nargs="+", type=Path)
parser.add_argument("--cols", type=int, default=4)
parser.add_argument("--width", type=int, default=1600)
args = parser.parse_args()
ims = [Image.open(f).convert("RGB") for f in args.frames]
cell_w = args.width // args.cols
cell_h = round(cell_w * ims[0].height / ims[0].width)
rows = (len(ims) + args.cols - 1) // args.cols
sheet = Image.new("RGB", (cell_w * args.cols, cell_h * rows))
for i, im in enumerate(ims):
    sheet.paste(im.resize((cell_w, cell_h), Image.LANCZOS), ((i % args.cols) * cell_w, (i // args.cols) * cell_h))
sheet.save(args.out)
print(args.out)
