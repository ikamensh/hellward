"""The Moon Well in three ranks (tower_well_1..3.glb, one run): a round moonlit wellhouse on the gothic
plinth, nothing like the village prop's open windlass: a stone drum with a glowing water heart, an arch frame
over the mouth, and a moon above it.

Rank 1 is a low drum with a coping ring, dark water lit from below, and a twin-pillared arch carrying a pale
moon disc; rank 2 raises a taller banded drum pierced by glowing arches, under a shingled canopy with a
crescent finial; rank 3 is a grand drum tower with pinnacles, a spire roof, a great gold crescent, and a
glowing rill ring at its foot. The well never aims (an aura), so there is no turret: `fx_glow` is the water
heart, `fx_muzzle` the mouth where its moonbeam rises.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from towers import (arch_outline, box, cut, empty, export, lathe, merge, pinnacle, plinth, prism, reset, rot_z,  # noqa: E402
                    shade, spike, tube, uvbox, xform)


def moon_disc(r: float, mat="glow_frost"):
    """A pale moon disc r across, facing +Y, its centre at the origin."""
    disc = lathe([(0, -0.03), (r, -0.03), (r, 0.03), (0, 0.03)], 24, mat, "moon")
    xform(disc, Matrix.Rotation(math.radians(90), 4, "X"))
    return disc


def crescent(r: float, mat="gold"):
    """A crescent moon r across, facing +Y, its horns pointing up, centred at the origin."""
    disc = lathe([(0, -0.035), (r, -0.035), (r, 0.035), (0, 0.035)], 24, mat, "moon")
    xform(disc, Matrix.Rotation(math.radians(90), 4, "X"))
    bite = lathe([(0, -0.06), (r * 0.92, -0.06), (r * 0.92, 0.06), (0, 0.06)], 24, None, "cutter")
    xform(bite, Matrix.Rotation(math.radians(90), 4, "X"))
    xform(bite, Matrix.Translation((r * 0.42, 0, r * 0.28)))
    cut(disc, bite)
    return shade(disc, 40)


def drum(rank: int, deck: float):
    """The round wellhouse drum on the deck. Returns (parts, mouth_z, drum_r, drum_h)."""
    p = []
    drum_r = (0.62, 0.68, 0.74)[rank - 1]
    drum_h = (0.85, 1.5, 2.2)[rank - 1]
    rng = random.Random(40 + rank)
    # coursed stone drum with a flared foot and a corbelled rim
    p.append(lathe([(drum_r + 0.1, 0), (drum_r + 0.06, 0.1), (drum_r, 0.22), (drum_r, drum_h - 0.12),
                    (drum_r + 0.07, drum_h), (drum_r + 0.07, drum_h + 0.08)], 24, "stone", "drum",
                   loc=(0, 0, deck), metres=1.6))
    # coping slabs round the mouth, a little uneven
    n = 12
    for i in range(n):
        a = 2 * math.pi * (i + 0.5 * (rank % 2)) / n
        slab = box((0.34, 0.2, 0.07), mat="stone", bevel=0.012, name="drum")
        xform(slab, Matrix.Translation((math.cos(a) * (drum_r + 0.02), math.sin(a) * (drum_r + 0.02),
                                        deck + drum_h + 0.11 + rng.uniform(-0.012, 0.012))))
        rot_z(slab, math.degrees(a) + rng.uniform(-4, 4))
        uvbox(slab, 1.5, 3 + i)
        p.append(slab)
    # iron bands round the taller drums
    for t in ([0.45] if rank == 2 else ([0.3, 0.55, 0.8] if rank == 3 else [])):
        p.append(lathe([(drum_r + 0.015, 0), (drum_r + 0.015, 0.06), (drum_r - 0.01, 0.06), (drum_r - 0.01, 0)],
                       24, "iron", "iron", loc=(0, 0, deck + drum_h * t)))
    # glowing arch windows pierced in the drum (dark recess, moonlit pane)
    if rank >= 2:
        nw = 0.26
        for f in range(4):
            recess = prism(arch_outline(nw, 0.3, n=8), 0.1, mat="basalt", name="window")
            xform(recess, Matrix.Translation((0, drum_r - 0.06, deck + drum_h * 0.42)))
            rot_z(recess, -90 * f)
            p.append(recess)
            pane = prism(arch_outline(nw - 0.1, 0.24, n=8), 0.04, mat="glow_frost", name="window")
            xform(pane, Matrix.Translation((0, drum_r - 0.02, deck + drum_h * 0.42 + 0.03)))
            rot_z(pane, -90 * f)
            p.append(pane)
    return p, deck + drum_h + 0.14, drum_r, drum_h


def water(rank: int, mouth: float, drum_r: float):
    """Dark water in the mouth with the moon's glow burning up through it. Returns (parts, heart)."""
    wr = drum_r - 0.1
    p = [lathe([(0, -0.3), (wr, -0.3), (wr, 0), (0, 0)], 20, "basalt", "water", loc=(0, 0, mouth - 0.28))]
    p.append(lathe([(0, 0), (wr, 0), (wr, 0.015), (0, 0.015)], 20, "ice", "water", loc=(0, 0, mouth - 0.3)))
    glow_r = (0.16, 0.22, 0.28)[rank - 1]
    p.append(lathe([(0, 0), (glow_r, 0), (glow_r * 0.7, 0.1), (0, 0.16)], 12, "glow_frost", "water",
                   loc=(0, 0, mouth - 0.3)))
    return p, (0, 0, mouth - 0.22)


def arch_frame(rank: int, deck: float, mouth: float, drum_r: float):
    """The frame over the mouth: twin pillars and an arch at rank 1, a roofed canopy above."""
    p = []
    top = mouth + (1.15, 1.5, 1.9)[rank - 1]
    if rank == 1:
        # two stone pillars with capitals, a pointed arch between them, the moon hung in it
        for sx in (-1, 1):
            x = sx * (drum_r + 0.02)
            p.append(box((0.16, 0.16, top - mouth + 0.1), loc=(x, 0, mouth - 0.1), base=True, mat="stone",
                       bevel=0.02, name="arch"))
            p.append(box((0.24, 0.24, 0.09), loc=(x, 0, top - 0.15), mat="stone", bevel=0.02, name="arch"))
            uvbox(p[-2], 1.5, 7 + sx)
        span = drum_r + 0.02
        rib = tube([(-span, 0, top - 0.1), (-span * 0.55, 0, top + 0.28), (0, 0, top + 0.42),
                    (span * 0.55, 0, top + 0.28), (span, 0, top - 0.1)], 0.07, "stone", 8, "arch")
        p.append(rib)
        p.append(spike((0, 0, top + 0.36), (0, 0, top + 0.72), 0.06, "stone", 4, "arch"))
        moon = moon_disc(0.17)
        xform(moon, Matrix.Translation((0, 0, top + 0.02)))
        p.append(moon)
        # a chain from the arch's crown down towards the water
        p.append(tube([(0, 0, top + 0.3), (0, 0, mouth + 0.35)], 0.018, "iron", 6, "chain"))
        p.append(box((0.09, 0.09, 0.12), loc=(0, 0, mouth + 0.28), base=True, mat="iron", bevel=0.015,
                     name="chain"))
    else:
        # four posts carry a shingled canopy; a crescent rides its peak
        pr = drum_r + 0.12
        post_h = top - deck
        for i in range(4):
            a = math.radians(45 + 90 * i)
            x, y = math.cos(a) * pr, math.sin(a) * pr
            p.append(box((0.13, 0.13, post_h), loc=(x, y, deck), base=True, mat="timber", bevel=0.015,
                         name="canopy"))
            p.append(box((0.19, 0.19, 0.1), loc=(x, y, deck), base=True, mat="iron", bevel=0.015, name="iron"))
            uvbox(p[-2], 1.2, 11 + i)
        plate = lathe([(pr + 0.1, 0), (pr + 0.1, 0.09), (0, 0.09)], 4, "timber", "canopy", phase=45,
                      loc=(0, 0, top - 0.1), smooth_angle=None)
        uvbox(plate, 1.2, 5)
        p.append(plate)
        tiers = [(pr + 0.28, top - 0.02, 0.5)] if rank == 2 else [(pr + 0.32, top - 0.02, 0.42),
                                                                 (pr * 0.62, top + 0.4, 0.55)]
        peak = top
        for r0, z0, h in tiers:
            p.append(lathe([(r0, 0), (r0 * 0.55, h * 0.55), (0.06, h)], 4, "slate", "canopy", phase=45,
                           loc=(0, 0, z0), smooth_angle=None))
            peak = z0 + h
        finial = crescent(0.22 if rank == 2 else 0.3)
        xform(finial, Matrix.Translation((0, 0, peak + (0.24 if rank == 2 else 0.32))))
        p.append(finial)
        p.append(tube([(0, 0, peak - 0.05), (0, 0, peak + 0.1)], 0.03, "iron", 6, "pole"))
        # a chain from the canopy's heart down to the water, with a dowsing crystal
        p.append(tube([(0, 0, top - 0.1), (0, 0, mouth + 0.4)], 0.018, "iron", 6, "chain"))
        p.append(spike((0, 0, mouth + 0.52), (0, 0, mouth + 0.3), 0.05, "ice", 6, "chain"))
    return p, top


def build(rank: int) -> None:
    reset()
    stat, deck = plinth(body_h=0.92, seed=20 + rank)
    p, mouth, drum_r, drum_h = drum(rank, deck)
    wp, heart = water(rank, mouth, drum_r)
    p += wp
    ap, _top = arch_frame(rank, deck, mouth, drum_r)
    p += ap
    if rank == 3:
        # pinnacles ring the drum's foot; a glowing rill runs round them
        for i in range(4):
            a = math.radians(45 + 90 * i)
            p += pinnacle(math.cos(a) * 0.62, math.sin(a) * 0.62, deck, 0.2, 0.75, name="foot")
        p.append(lathe([(0.86, 0), (0.86, 0.05), (0.78, 0.05), (0.78, 0)], 32, "glow_frost", "rill",
                       loc=(0, 0, deck + 0.02)))
        # moon-phases on the drum: small pale discs waxing round it
        for i, ph in enumerate((0.05, 0.08, 0.11, 0.08)):
            a = math.radians(90 * i)
            disc = moon_disc(ph, "ice")
            xform(disc, Matrix.Translation((math.cos(a) * (drum_r + 0.01), math.sin(a) * (drum_r + 0.01),
                                            deck + drum_h * 0.72)))
            xform(disc, Matrix.Rotation(a - math.pi / 2, 4, "Z"))
            p.append(disc)
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 1.0)
    tower = merge(stat + p, "tower")
    empty("fx_glow", heart)
    empty("fx_muzzle", (0, 0, mouth + 0.55))
    tris = sum(len(f.vertices) - 2 for f in tower.data.polygons)
    print(f"tower_well_{rank}: {tris} triangles, mouth {mouth:.2f}")
    export(f"tower_well_{rank}")


if __name__ == "__main__":
    for r in (1, 2, 3):
        build(r)
