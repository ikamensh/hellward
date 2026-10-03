"""The martyr's censer in three ranks (tower_censer_1..3.glb, one run): an iron gibbet on the gothic
plinth with a chained thurible hanging from its crossbar, embers breathing inside the bowl, firelight through
the lid's piercings.

Rank 1 is a low gibbet with one censer; rank 2 stands taller, a bigger bowl, its crossbar chained down to the
plinth's pinnacles, the martyr's manacles hanging beside; rank 3 is crowned with gablets, the great censer
spiked, two small censers at the crossbar's ends, skulls at the posts' feet. It never aims (the field burns
round it), so the tower is one static mesh: `fx_fire` is in the bowl, `fx_muzzle` above it.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from towers import (beam, box, chain, empty, export, hull, lathe, merge, plinth, reset, skull, spike, tube,  # noqa: E402
                    uvbox, xform)


def thurible(cx: float, cy: float, cz: float, r: float, rank: int, rng: random.Random, spiked: bool = False):
    """A hanging censer bowl, its pierced lid on top, centred on (cx, cy) with the bowl's rim at cz.
    Returns (parts, rim height)."""
    p = []
    # the bowl: a thick iron cup on a knopped foot
    p.append(lathe([(0, -0.16), (r * 0.3, -0.16), (r * 0.34, -0.1), (r * 0.2, -0.06), (r * 0.5, 0.02), (r * 0.85, 0.16),
                    (r, 0.3), (r * 1.04, 0.34), (r * 0.94, 0.34), (r * 0.82, 0.24), (r * 0.6, 0.1), (0, 0.06)], 16,
                   "iron", "censer", loc=(cx, cy, cz - 0.34), metres=0.6))
    rim = cz
    # embers heaped in the bowl: glowing coals and charred crust
    for k in range(20):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0, r * 0.72)
        ez = rim - 0.02 + 0.1 * (1 - rr / (r * 0.8)) + rng.uniform(-0.02, 0.03)
        sz = rng.uniform(0.045, 0.085)
        pts = [(cx + math.cos(a) * rr + rng.uniform(-sz, sz), cy + math.sin(a) * rr + rng.uniform(-sz, sz),
                ez + rng.uniform(-sz, sz) * 0.6) for _ in range(8)]
        p.append(hull(pts, "glow_fire" if k % 3 else "charred", "ember"))
    # the lid: a pierced dome, firelight through the slits, a knob ring on top
    lid = cz + 0.02
    p.append(lathe([(r * 1.02, 0), (r * 0.98, 0.1), (r * 0.7, 0.24), (r * 0.4, 0.32), (r * 0.18, 0.36), (0, 0.37)], 16,
                   "iron", "censer", loc=(cx, cy, lid), metres=0.6))
    for k in range(6):   # the piercings glow from the embers within, standing proud of the dome
        a = 2 * math.pi * k / 6 + 0.2
        slit = box((0.05, 0.035, 0.16), loc=(0, 0, 0), mat="glow_fire", name="censer")
        rr = r * 0.87
        xform(slit, Matrix.Translation((cx + math.cos(a) * rr, cy + math.sin(a) * rr, lid + 0.16)))
        xform(slit, Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(a - math.pi / 2, 4, "Z")
              @ Matrix.Translation((-cx, -cy, 0)))
        p.append(slit)
    # firelight seeping from the seam where the lid meets the bowl
    p.append(lathe([(r * 0.97, 0), (r * 1.02, 0.015), (r * 0.97, 0.03)], 16, "glow_fire", "censer",
                   loc=(cx, cy, lid - 0.015), metres=0.6))
    p.append(lathe([(0, 0), (0.045, 0), (0.045, 0.06), (0, 0.06)], 8, "iron", "censer",
                   loc=(cx, cy, lid + 0.37)))
    crown = [(cx + math.cos(t) * 0.055, cy + math.sin(t) * 0.055, lid + 0.47) for t in [2 * math.pi * k / 12 for k in range(12)]]
    p.append(tube(crown, 0.016, "iron", 5, "censer", closed=True, metres=0.3))
    if spiked:   # a crown of spear points round the bowl's rim
        for k in range(8):
            a = 2 * math.pi * k / 8
            base = Vector((cx + math.cos(a) * r * 1.0, cy + math.sin(a) * r * 1.0, rim - 0.02))
            p.append(spike(base, base + Vector((math.cos(a) * 0.05, math.sin(a) * 0.05, 0.2)), 0.035, "iron", 4,
                           "censer"))
    return p, rim


def build(rank: int) -> None:
    reset()
    rng = random.Random(90 + rank)
    stat, deck = plinth(body_h=0.92, seed=24 + rank)
    p = []
    # the gibbet: two iron posts and a crossbar, spear-tipped, bolted to the deck
    top = deck + (2.1, 2.5, 2.9)[rank - 1]
    for sx in (-1, 1):
        x = sx * 0.55
        p.append(box((0.24, 0.24, 0.07), loc=(x, 0, deck), base=True, mat="iron", bevel=0.012, name="gibbet"))
        p.append(box((0.13, 0.13, top - deck), loc=(x, 0, deck + 0.07), base=True, mat="iron", bevel=0.015,
                     name="gibbet"))
        for zz in (deck + 0.5, (deck + top) / 2):
            p.append(box((0.17, 0.17, 0.06), loc=(x, 0, zz), mat="iron", bevel=0.01, name="gibbet"))
        p.append(spike((x, 0, top + 0.02), (x, 0, top + 0.34), 0.06, "iron", 4, "gibbet"))
    p.append(beam((-0.68, 0, top), (0.68, 0, top), 0.11, 0.13, "iron", name="gibbet", seed=3))
    for sx in (-1, 1):
        p.append(box((0.07, 0.16, 0.17), loc=(sx * 0.68, 0, top), mat="iron", bevel=0.012, name="gibbet"))
    if rank >= 3:   # gablets crowning the crossbar
        for sx in (-1, 1):
            gable = lathe([(0, 0), (0.09, 0.02), (0.05, 0.12), (0.07, 0.18), (0, 0.3)], 4, "iron", "gibbet",
                          phase=45, loc=(sx * 0.3, 0, top + 0.06), smooth_angle=None)
            p.append(gable)
    # the great censer hangs from the crossbar's middle
    r = (0.3, 0.36, 0.42)[rank - 1]
    rim = deck + (1.05, 1.2, 1.35)[rank - 1]
    more, _ = thurible(0, 0, rim, r, rank, rng, spiked=(rank == 3))
    p += more
    gather = rim + 0.62   # the suspension chains meet in a ring above the bowl
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.5
        foot = Vector((math.cos(a) * r * 0.95, math.sin(a) * r * 0.95, rim - 0.04))
        p += chain(foot, Vector((0, 0, gather)), sag=0.02, pitch=0.07)
    gather_ring = [(math.cos(t) * 0.06, math.sin(t) * 0.06, gather) for t in [2 * math.pi * k / 12 for k in range(12)]]
    p.append(tube(gather_ring, 0.018, "iron", 5, "chain", closed=True, metres=0.3))
    p += chain(Vector((0, 0, gather)), Vector((0, 0, top - 0.05)), sag=0.015, pitch=0.085)
    if rank >= 2:
        # the crossbar chained down to the plinth's pinnacles, as the pyre's bowl is
        for sx in (-1, 1):
            p += chain(Vector((sx * 0.62, 0, top - 0.02)), Vector((sx * 0.65, 0, deck + 0.62)), sag=0.1, pitch=0.085)
        # the martyr's manacles hanging from the crossbar
        for sx in (-1, 1):
            mx = sx * 0.3
            p += chain(Vector((mx, 0, top - 0.05)), Vector((mx, 0, top - 0.42)), sag=0.01, pitch=0.07)
            cuff = [(mx + math.cos(t) * 0.085, math.sin(t) * 0.085, top - 0.52)
                    for t in [2 * math.pi * k / 14 for k in range(14)]]
            p.append(tube(cuff, 0.02, "iron", 5, "manacle", closed=True, metres=0.3))
    if rank == 3:
        # two small censers at the crossbar's ends
        for sx in (-1, 1):
            mx = sx * 0.62
            side_rim = top - 0.85
            more, _ = thurible(mx, 0, side_rim, 0.15, 3, rng)
            p += more
            p += chain(Vector((mx, 0, side_rim + 0.42)), Vector((mx, 0, top - 0.05)), sag=0.015, pitch=0.07)
        for sx in (-1, 1):   # skulls at the posts' feet
            p += skull((sx * 0.55, 0.32, deck), 0.2, mat="bone")
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.8)
    tower = merge(stat + p, "tower")
    empty("fx_fire", (0, 0, rim + 0.02))
    empty("fx_muzzle", (0, 0, rim + 0.62))
    tris = sum(len(f.vertices) - 2 for f in tower.data.polygons)
    print(f"tower_censer_{rank}: {tris} triangles, bowl rim at {rim:.2f}")
    export(f"tower_censer_{rank}")


if __name__ == "__main__":
    for r in (1, 2, 3):
        build(r)
