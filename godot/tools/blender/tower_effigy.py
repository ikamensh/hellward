"""The Effigy in three ranks (tower_effigy_1..3.glb, one run): a straw-and-timber figure on the gothic
plinth, a lightning rod for curses: a post frame, a bound thatch body, outstretched arms, a skull for a head.

Rank 1 is a simple field cross: a post and crossbar, a bound straw torso, rope wraps, a bare skull. Rank 2 is
jointed and bigger: legs, a ribcage of bent withies round a curse-glowing heart, a horned skull, chains with
bone charms hanging from its arms. Rank 3 towers over the field: a crown of iron spikes, a full barrel of
ribs, a skirt of hanging chains, skulls piled at its feet. It never aims (an aura), so there is no turret:
`fx_glow` is the heart where curses ground themselves, `fx_muzzle` the head they strike at.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix  # noqa: E402

from towers import (box, chain, empty, export, lathe, merge, plinth, reset, rot_z, spike, tube, uvbox,  # noqa: E402
                    xform)
from towers import skull as skull_parts


def rope_wrap(p, y: float, r: float, z: float, mat="rope"):
    """A rope ring round the body at height z."""
    p.append(lathe([(r, 0), (r, 0.045), (r - 0.02, 0.045), (r - 0.02, 0)], 14, mat, "rope", loc=(0, y, z),
                   metres=0.4))


def figure(rank: int, deck: float):
    """The straw figure on the deck. Returns (parts, heart_z, head_z)."""
    p = []
    s = (0.85, 1.0, 1.2)[rank - 1]          # overall scale
    hip = deck + 1.05 * s
    shoulder = deck + 1.75 * s
    head = deck + 2.0 * s
    # the mast it hangs on, footed in iron
    p.append(box((0.16 * s, 0.16 * s, head - deck + 0.1), loc=(0, 0, deck - 0.05), base=True, mat="timber",
                 bevel=0.02, name="mast"))
    p.append(box((0.3 * s, 0.3 * s, 0.12), loc=(0, 0, deck), base=True, mat="iron", bevel=0.02, name="iron"))
    uvbox(p[-2], 1.2, 3)
    if rank == 1:
        # legs: two splayed straw-bound posts
        for sx in (-1, 1):
            p.append(tube([(sx * 0.09 * s, 0, hip), (sx * 0.2 * s, 0, deck + 0.06)], 0.09 * s, "thatch", 8,
                           "legs"))
            p.append(box((0.2, 0.2, 0.08), loc=(sx * 0.2 * s, 0, deck), base=True, mat="iron", bevel=0.015,
                         name="iron"))
        # torso: a bound straw cone on the mast, wider at the shoulders
        p.append(lathe([(0.16 * s, 0), (0.3 * s, 0.1 * s), (0.34 * s, 0.55 * s), (0.2 * s, 0.78 * s)], 12,
                       "thatch", "torso", loc=(0, 0, hip - 0.15 * s), metres=0.8))
        for t in (0.05, 0.3, 0.55, 0.75):
            rope_wrap(p, 0, (0.3 - 0.12 * t) * s + 0.01, hip - 0.15 * s + t * 0.78 * s)
        # arms: one crossbar, straw-sleeved, rope at the wrists
        p.append(box((1.7 * s, 0.11 * s, 0.11 * s), loc=(0, 0, shoulder), mat="timber", bevel=0.02,
                     name="arms"))
        for sx in (-1, 1):
            p.append(tube([(sx * 0.3 * s, 0, shoulder), (sx * 0.82 * s, 0, shoulder + 0.04 * s)], 0.08 * s,
                           "thatch", 8, "arms"))
            ring = lathe([(0.1 * s, 0), (0.1 * s, 0.04), (0.08 * s, 0.04), (0.08 * s, 0)], 10, "rope", "rope",
                         loc=(sx * 0.68 * s, 0, shoulder - 0.02))
            xform(ring, Matrix.Rotation(math.radians(90), 4, "Y"))
            xform(ring, Matrix.Translation((0.02 * sx * s, 0, 0.06 * s)))
            p.append(ring)
        p += skull_parts((0, 0.02, head), 0.3 * s, yaw=0)
    else:
        # legs: jointed straw limbs with rope knees, standing on the deck
        for sx in (-1, 1):
            knee = (sx * 0.19 * s, 0.02, deck + 0.55 * s)
            p.append(tube([(sx * 0.1 * s, 0, hip), knee], 0.1 * s, "thatch", 8, "legs"))
            p.append(tube([knee, (sx * 0.22 * s, 0, deck + 0.1)], 0.085 * s, "thatch", 8, "legs"))
            p.append(lathe([(0.11 * s, 0), (0.11 * s, 0.05), (0.09 * s, 0.05), (0.09 * s, 0)], 10, "rope",
                           "rope", loc=knee, metres=0.4))
            p.append(box((0.22, 0.22, 0.09), loc=(sx * 0.22 * s, 0, deck), base=True, mat="iron",
                         bevel=0.015, name="iron"))
        # torso: a barrel of bent withy ribs round the curse-glowing heart
        heart = (shoulder + hip) / 2
        ribs = 6 if rank == 2 else 8
        for i in range(ribs):
            a = math.pi * i / ribs
            c, sn = math.cos(a), math.sin(a)
            w = 0.3 * s
            p.append(tube([(c * 0.1 * s, sn * 0.1 * s, hip - 0.1 * s),
                            (c * w, sn * w, (hip + shoulder) / 2 - 0.1 * s),
                            (c * w * 0.9, sn * w * 0.9, shoulder - 0.12 * s),
                            (c * 0.08 * s, sn * 0.08 * s, shoulder + 0.02)], 0.028 * s, "timber", 6, "ribs"))
        for t in (0.15, 0.45, 0.75):
            z = (hip - 0.1 * s) + t * (shoulder - hip + 0.12 * s)
            p.append(lathe([(0.3 * s, 0), (0.3 * s, 0.04), (0.28 * s, 0.04), (0.28 * s, 0)], 16, "rope",
                           "rope", loc=(0, 0, z), metres=0.4))
        p.append(lathe([(0, 0), (0.1 * s, 0.02), (0.08 * s, 0.2 * s), (0, 0.26 * s)], 10, "glow_curse",
                       "heart", loc=(0, 0, heart - 0.13 * s)))
        # a thatch skirt below the ribs
        p.append(lathe([(0.32 * s, 0), (0.4 * s, 0.25 * s), (0.42 * s, 0.3 * s)], 14, "thatch", "skirt",
                       loc=(0, 0, hip - 0.42 * s), metres=0.8))
        # arms: jointed, raised to the sky to catch curses
        for sx in (-1, 1):
            elbow = (sx * 0.52 * s, 0, shoulder + 0.28 * s)
            wrist = (sx * 0.72 * s, 0, shoulder + 0.72 * s)
            p.append(tube([(sx * 0.14 * s, 0, shoulder + 0.02), elbow], 0.09 * s, "thatch", 8, "arms"))
            p.append(tube([elbow, wrist], 0.07 * s, "thatch", 8, "arms"))
            p.append(lathe([(0.1 * s, 0), (0.1 * s, 0.05), (0.08 * s, 0.05), (0.08 * s, 0)], 10, "rope",
                           "rope", loc=elbow, metres=0.4))
            # a chain from each wrist with a bone charm: a finger-bone and a knuckle
            p += chain(wrist, (wrist[0], wrist[1], wrist[2] - 0.5 * s), sag=0.06, pitch=0.07)
            charm = tube([(wrist[0], 0, wrist[2] - 0.5 * s), (wrist[0], 0, wrist[2] - 0.72 * s)], 0.025,
                         "bone", 6, "charm")
            p.append(charm)
            p.append(box((0.07, 0.07, 0.07), loc=(wrist[0], 0, wrist[2] - 0.76 * s), mat="bone",
                         bevel=0.02, name="charm"))
        p += skull_parts((0, 0.02, head), 0.34 * s, yaw=0, horns=(0.9 if rank == 3 else None))
    if rank == 3:
        # a crown of iron spikes over the skull
        for i in range(7):
            a = 2 * math.pi * i / 7
            r0, r1 = 0.2 * s, 0.3 * s
            p.append(spike((math.cos(a) * r0, math.sin(a) * r0, head + 0.28 * s),
                           (math.cos(a) * r1, math.sin(a) * r1, head + 0.62 * s), 0.035, "iron", 4,
                           "crown"))
        p.append(lathe([(0.2 * s, 0), (0.2 * s, 0.07), (0.17 * s, 0.07), (0.17 * s, 0)], 14, "iron",
                       "crown", loc=(0, 0, head + 0.24 * s)))
        # a skirt of hanging chains round the mast
        for i in range(8):
            a = 2 * math.pi * (i + 0.5) / 8
            x, y = math.cos(a) * 0.34 * s, math.sin(a) * 0.34 * s
            p += chain((x, y, hip + 0.05), (x * 1.15, y * 1.15, hip - 0.55 * s), sag=0.05,
                           pitch=0.07)
        # skulls piled at its feet: the curses it has already drunk
        rng = random.Random(7)
        for i in range(5):
            a = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(0.42, 0.58)
            p += skull_parts((math.cos(a) * r, math.sin(a) * r, deck + 0.02), rng.uniform(0.16, 0.22),
                             yaw=rng.uniform(0, 360), pitch=rng.uniform(-15, 10))
    return p, (shoulder + hip) / 2, head


def build(rank: int) -> None:
    reset()
    stat, deck = plinth(body_h=0.92, seed=30 + rank)
    p, heart, head = figure(rank, deck)
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 1.0)
    tower = merge(stat + p, "tower")
    empty("fx_glow", (0, 0, heart))
    empty("fx_muzzle", (0, 0, head + 0.3))
    tris = sum(len(f.vertices) - 2 for f in tower.data.polygons)
    print(f"tower_effigy_{rank}: {tris} triangles, head {head:.2f}")
    export(f"tower_effigy_{rank}")


if __name__ == "__main__":
    for r in (1, 2, 3):
        build(r)
