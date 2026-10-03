"""The sentinel idol in three ranks (tower_idol_1..3.glb, one run): a stone warden on the gothic plinth,
its face a bone funerary mask with holy light in the eye slits, its right arm raised with a flanged mace the
smite falls from.

Rank 1 is a weathered warden on a single step; rank 2 stands taller on two steps, gilt torc and belt, a golden
halo, skulls of the judged at its foot; rank 3 is crowned in bone, its halo spiked, holy runes down its robe, a
great mace with a burning core. It never turns (the smite falls from the sky), so the tower is one static mesh:
`fx_muzzle` is the mace's head, `fx_glow` the mask's brow.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from towers import box, empty, export, lathe, merge, plinth, reset, skull, sphere, spike, tube, uvbox, xform  # noqa: E402


def warden(z: float, rank: int):
    """The warden standing on its dais top at z, facing +Y. Returns (parts, muzzle, brow)."""
    p = []
    H = (1.5, 1.8, 2.1)[rank - 1]   # hem to neck
    # the robe: a bell of stone from the hem to the shoulders
    p.append(lathe([(0, 0), (0.44, 0), (0.4, 0.12), (0.3, H * 0.55), (0.34, H * 0.8), (0.3, H * 0.92),
                    (0.13, H), (0, H)], 14, "stone", "robe", loc=(0, 0, z)))
    # folds: shallow vertical ribs round the skirt
    for k in range(10):
        a = 2 * math.pi * k / 10
        c, s = math.cos(a), math.sin(a)
        p.append(tube([(c * 0.4, s * 0.4, z + 0.06), (c * 0.34, s * 0.34, z + H * 0.5)], 0.028, "stone", 5, "fold"))
    if rank >= 2:   # a gilt belt and torc
        p.append(lathe([(0.315, 0), (0.345, 0.02), (0.345, 0.08), (0.315, 0.1)], 14, "gold", "belt",
                       loc=(0, 0, z + H * 0.55)))
        ring = [(math.cos(t) * 0.15, math.sin(t) * 0.15, z + H * 0.97) for t in [2 * math.pi * k / 16 for k in range(16)]]
        p.append(tube(ring, 0.03, "gold", 5, "torc", closed=True, metres=0.3))
    if rank >= 3:   # holy runes burning down the robe's front
        for k in range(3):
            p.append(box((0.07, 0.02, 0.2), loc=(0, 0.33 - 0.02 * k, z + H * (0.62 - 0.14 * k)), mat="glow_holy",
                       name="rune"))
    # the head: a bone skull under a stone cowl, a funerary mask with lit eyes
    head = Vector((0, 0.02, z + H + 0.16))
    p.append(sphere(0.155, loc=tuple(head), scale=(0.9, 0.95, 1.0), mat="bone", segments=12, rings=8, name="head"))
    p.append(lathe([(0, 0), (0.27, 0), (0.24, 0.12), (0.17, 0.34), (0.08, 0.5), (0, 0.55)], 12, "stone", "cowl",
                   loc=(0, -0.03, z + H + 0.02)))
    mask = sphere(0.125, loc=(0, head.y + 0.1, head.z - 0.01), scale=(0.82, 0.55, 1.05), mat="bone", segments=10,
                  rings=7, name="mask")
    p.append(mask)
    for sx in (-1, 1):   # the eyes: slits of holy light
        p.append(box((0.05, 0.025, 0.028), loc=(sx * 0.055, head.y + 0.155, head.z + 0.03), mat="glow_holy",
                     name="eyes"))
    p.append(box((0.03, 0.02, 0.09), loc=(0, head.y + 0.16, head.z - 0.05), mat="bone", name="mask"))
    brow = Vector((0, head.y + 0.1, head.z + 0.12))
    if rank >= 2:   # a golden halo standing behind the head
        halo = lathe([(0.3, 0), (0.3, 0.035), (0.2, 0.035), (0.2, 0)], 20, "gold", "halo")
        xform(halo, Matrix.Rotation(math.radians(90), 4, "X"))
        xform(halo, Matrix.Translation((0, -0.16, head.z + 0.02)))
        p.append(halo)
    if rank >= 3:   # spikes round the halo and a crown of bone on the cowl
        for k in range(8):
            a = 2 * math.pi * k / 8
            base = Vector((math.cos(a) * 0.3, -0.16, head.z + 0.02 + math.sin(a) * 0.3))
            out = Vector((math.cos(a), 0, math.sin(a)))
            p.append(spike(base, base + out * 0.14, 0.03, "gold", 4, "halo"))
        for k in range(5):
            a = math.pi * (0.15 + 0.7 * k / 4)
            base = Vector((math.cos(a) * 0.12, -0.03 + math.sin(a) * 0.02, z + H + 0.42))
            p.append(spike(base, base + Vector((math.cos(a) * 0.1, 0, 0.2)), 0.035, "bone", 5, "crown"))
    # the right arm raised with the mace the smite falls from
    shoulder = Vector((0.28, 0.02, z + H * 0.88))
    elbow = Vector((0.52, 0.06, z + H * 1.04))
    fist = Vector((0.44, 0.1, z + H * 1.3))
    p.append(tube([tuple(shoulder), tuple(elbow)], 0.085, "stone", 7, "arm", radii=[0.1, 0.075]))
    p.append(tube([tuple(elbow), tuple(fist)], 0.07, "stone", 7, "arm", radii=[0.075, 0.06]))
    p.append(sphere(0.075, loc=tuple(fist), mat="bone", segments=8, rings=6, name="fist"))
    grip = fist + Vector((-0.03, 0.02, 0.05))
    mace_top = grip + Vector((-0.06, 0.04, 0.52))
    p.append(tube([tuple(grip - Vector((0, 0, 0.1))), tuple(mace_top)], 0.032, "iron", 6, "mace"))
    p.append(sphere(0.105, loc=tuple(mace_top), mat="iron", segments=10, rings=7, name="mace"))
    for k in range(6):   # the flanges
        a = 2 * math.pi * k / 6
        flange = box((0.03, 0.03, 0.16), loc=(0, 0, 0), mat="iron", bevel=0.008, name="mace")
        m = Matrix.Translation(mace_top) @ Matrix.Rotation(a, 4, "Z") @ Matrix.Translation((0.1, 0, 0))
        xform(flange, m)
        p.append(flange)
    p.append(spike(mace_top + Vector((0, 0, 0.06)), mace_top + Vector((0, 0, 0.26)), 0.045, "iron", 4, "mace"))
    if rank >= 3:   # the mace's burning core
        p.append(lathe([(0.108, -0.03), (0.115, 0), (0.108, 0.03)], 10, "glow_holy", "mace", loc=tuple(mace_top)))
    muzzle = mace_top + Vector((0, 0, 0.26))
    # the left arm bent across the chest, a bone orb in its hand
    sh2 = Vector((-0.28, 0.02, z + H * 0.88))
    el2 = Vector((-0.4, 0.14, z + H * 0.68))
    hand = Vector((-0.12, 0.3, z + H * 0.72))
    p.append(tube([tuple(sh2), tuple(el2)], 0.085, "stone", 7, "arm", radii=[0.1, 0.075]))
    p.append(tube([tuple(el2), tuple(hand)], 0.07, "stone", 7, "arm", radii=[0.075, 0.06]))
    p.append(sphere(0.09, loc=tuple(hand + Vector((0, 0.03, 0.02))), mat="bone", segments=10, rings=7, name="orb"))
    return p, muzzle, brow


def build(rank: int) -> None:
    reset()
    stat, deck = plinth(body_h=0.92, seed=20 + rank)
    p = []
    # the dais: one step, two at higher ranks
    steps = 1 if rank == 1 else 2
    w = 1.14
    z = deck
    for _ in range(steps):
        p.append(box((w, w, 0.12), loc=(0, 0, z), base=True, bevel=0.025, mat="stone", name="dais"))
        z += 0.12
        w -= 0.2
    more, muzzle, brow = warden(z, rank)
    p += more
    if rank >= 2:   # skulls of the judged round the dais
        n = 4 if rank == 2 else 6
        for k in range(n):
            a = 2 * math.pi * (k + 0.5) / n
            r = 0.62 if rank == 2 else 0.58
            p += skull((math.cos(a) * r, math.sin(a) * r, deck), 0.2, yaw=math.degrees(a) + 180, mat="bone")
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.8)
    tower = merge(stat + p, "tower")
    empty("fx_muzzle", tuple(muzzle))
    empty("fx_glow", tuple(brow))
    tris = sum(len(f.vertices) - 2 for f in tower.data.polygons)
    print(f"tower_idol_{rank}: {tris} triangles, mace at {tuple(round(c, 2) for c in muzzle)}")
    export(f"tower_idol_{rank}")


if __name__ == "__main__":
    for r in (1, 2, 3):
        build(r)
