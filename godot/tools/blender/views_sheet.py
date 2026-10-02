"""The second half of views.py (run with the tools' Python, which has PIL): grid, labels and bones over the
orthographic renders, side by side in one sheet."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

tmp, out = Path(sys.argv[1]), Path(sys.argv[2])
meta = json.loads((tmp / "meta.json").read_text())
size, centre = meta["size"], meta["centre"]
AX = {"x": 0, "y": 1, "z": 2}
font = ImageFont.load_default(size=14)
small = ImageFont.load_default(size=11)
tiles = []
for name, view in meta["views"].items():
    im = Image.open(tmp / f"{name}.png").convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    right, up = view["right"], view["up"]
    ha = max(range(3), key=lambda i: abs(right[i]))
    va = max(range(3), key=lambda i: abs(up[i]))

    def px(p):
        rel = [p[i] - centre[i] for i in range(3)]
        return (W / 2 + sum(rel[i] * right[i] for i in range(3)) / size * W,
                H / 2 - sum(rel[i] * up[i] for i in range(3)) / size * H)
    lo_h, hi_h = centre[ha] - size / 2, centre[ha] + size / 2
    lo_v, hi_v = centre[va] - size / 2, centre[va] + size / 2
    step = 100 if size < 0.4 else 20   # a line every 1 cm in a close-up, else every 5 cm
    k = int(lo_h * step) - 1
    while k / step < hi_h + 0.05:
        c = k / step
        p = list(centre)
        p[ha] = c
        u = px(p)[0]
        major = k % 2 == 0
        d.line([(u, 0), (u, H)], fill=(255, 255, 255, 70 if major else 30), width=1)
        if major:
            d.text((u + 2, H - 16), f"{c:+.2f}" if step == 100 else f"{c:+.1f}", fill=(255, 255, 0, 255), font=small)
        k += 1
    k = int(lo_v * step) - 1
    while k / step < hi_v + 0.05:
        c = k / step
        p = list(centre)
        p[va] = c
        v = px(p)[1]
        major = k % 2 == 0
        d.line([(0, v), (W, v)], fill=(255, 255, 255, 70 if major else 30), width=1)
        if major:
            d.text((2, v - 14), f"{c:.2f}" if step == 100 else f"{c:.1f}", fill=(0, 255, 255, 255), font=small)
        k += 1
    if meta["show_rig"]:
        for bone, (h, t) in meta["bones"].items():
            a, b = px(h), px(t)
            d.line([a, b], fill=(255, 40, 200, 230), width=3)
            d.ellipse([a[0] - 4, a[1] - 4, a[0] + 4, a[1] + 4], fill=(255, 255, 255, 255))
            if name in ("front", "right"):
                d.text((a[0] + 5, a[1] - 6), bone, fill=(255, 160, 230, 255), font=small)
    d.text((6, 6), f"{name}  across: {'xyz'[ha]} ({'+' if right[ha] > 0 else '-'} to the right)  up: {'xyz'[va]}",
           fill=(255, 255, 255, 255), font=font)
    tiles.append(im)
sheet = Image.new("RGB", (sum(t.width for t in tiles), tiles[0].height))
x = 0
for t in tiles:
    sheet.paste(t, (x, 0))
    x += t.width
sheet.save(out)
