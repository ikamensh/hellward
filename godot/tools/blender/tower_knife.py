"""The Knife Post in three ranks (tower_knife_1..3.glb, one run): a cutthroat's post on the gothic plinth, a
ship's mast stump stepped in the deck and rigged with shrouds, bristling with throwing knives: knives driven
into the mast, a knife-thrower's target board on its south face (toward the battle camera) stuck full of them,
and more hanging point-down on cords from the yard, their steel catching the light.

Rank 1 is a short mast with a cockbilled yard and a lantern at its end; rank 2 a taller mast with ratlines up
the shrouds, a crow's nest over the yard and a red sash round the mast; rank 3 the tallest, a crown of blades
fanned round the nest's rim, a skull spiked on the topmast and a pennant at the truck. Every rank carries more
knives: a rope band round the mast per rank, its knives tucked in with their blades bristling out.

The yard, the nest and the topmast are the child `turret` (origin = yaw pivot on the mast's axis), with
`fx_muzzle` at the front of the nest (the yard at rank 1), where the knives are thrown from.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from docks import coil, crate, lantern, lashing  # noqa: E402
from towers import (aim, beam, box, cloth, empty, export, lathe, merge, plinth, prism, reset, rot_z, skull,  # noqa: E402
                    tube, uvbox, xform)

COCKBILL = 9.0   # degrees the yard hangs askew, as a pirate's does


def knife(m: Matrix, k: float = 1.0):
    """A throwing knife whose point is at the origin of `m`, pointing along its -Z, the handle along +Z: a
    spear-point steel blade, a small iron guard, a leather grip and a ring pommel. `k` scales it."""
    bl, w, gl = 0.22 * k, 0.07 * k, 0.15 * k
    blade = prism([(0, 0), (w / 2, bl * 0.35), (w * 0.42, bl), (-w * 0.42, bl), (-w / 2, bl * 0.35)], 0.014 * k,
                  mat="steel", name="knife")
    guard = box((w * 1.8, 0.03 * k, 0.025 * k), loc=(0, 0, bl + 0.012 * k), mat="iron", name="knife")
    grip = tube([(0, 0, bl + 0.02 * k), (0, 0, bl + gl)], 0.017 * k, "leather", 6, "knife")
    ring = [Vector((0.03 * k * math.cos(2 * math.pi * i / 8), 0, bl + gl + 0.03 * k + 0.03 * k * math.sin(2 * math.pi * i / 8)))
            for i in range(8)]
    pommel = tube(ring, 0.008 * k, "iron", 4, "knife", closed=True)
    parts = [blade, guard, grip, pommel]
    for p in parts:
        xform(p, m)
    return parts


def stuck(at, into, rng: random.Random, k: float = 1.0, embed: float = 0.07):
    """A knife driven into wood at `at`, its point going `into` (a direction), sunk `embed` deep, turned at
    random about itself."""
    at, into = Vector(at), Vector(into).normalized()
    m = aim(at, at - into, rng.uniform(0, 180)) @ Matrix.Translation((0, 0, -embed * k))
    return knife(m, k)


def hanging(at, drop: float, rng: random.Random, k: float = 1.0):
    """A knife hanging point-down on a cord `drop` long from `at`."""
    at = Vector(at)
    length = 0.43 * k
    tip = at - Vector((0, 0, drop + length))
    parts = knife(Matrix.Translation(tip) @ Matrix.Rotation(rng.uniform(0, math.pi), 4, "Z"), k)
    parts.append(tube([at, at - Vector((0, 0, drop + 0.02))], 0.008, "rope", 4, "cord"))
    return parts


def target(c, r: float, rng: random.Random, knives: int, k: float):
    """A knife-thrower's target board on the mast's south face, centred on `c`, facing -Y: planks in an iron
    rim, burnt rings round a red eye, knives in it."""
    c = Vector(c)
    face = Matrix.Translation(c) @ Matrix.Rotation(math.radians(90), 4, "X")   # its +Z turns to -Y
    p = [lathe([(0, 0), (r, 0), (r, 0.06), (0, 0.06)], 16, "planks", "target", smooth_angle=None),
         lathe([(r, 0), (r + 0.025, 0), (r + 0.025, 0.07), (r - 0.015, 0.07), (r - 0.015, 0.06), (r, 0.06)], 16,
               "iron", "target", smooth_angle=None)]
    for r0, r1, mat in ((r * 0.66, r * 0.8, "charred"), (r * 0.36, r * 0.5, "charred"), (0.0, r * 0.16, "banner")):
        p.append(lathe([(r0, 0.061), (r1, 0.061), (r1, 0.066), (r0, 0.066)] if r0 else
                       [(0, 0.061), (r1, 0.061), (r1, 0.066), (0, 0.066)], 16, mat, "target", smooth_angle=None))
    for part in p:
        xform(part, face)
    for i in range(knives):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.0, r * 0.75)
        at = c + Vector((math.cos(a) * rr, -0.065, math.sin(a) * rr))
        into = Vector((rng.uniform(-0.25, 0.25), 1.0, rng.uniform(-0.15, 0.3)))
        p += stuck(at, into, rng, k, 0.06)
    return p


def rigging(deck: float, top: float, mast_r: float, rank: int):
    """Four shrouds from the mast to iron deadeyes at the deck's diagonals; ratlines across each side's pair
    from rank 2."""
    p = []
    foot = 0.38
    anchors = [Vector((sx * foot, sy * foot, deck + 0.04)) for sx in (-1, 1) for sy in (-1, 1)]
    for a in anchors:
        hold = Vector((a.x * mast_r / foot * 0.7, a.y * mast_r / foot * 0.7, top))
        p.append(tube([a + Vector((0, 0, 0.14)), hold], 0.017, "rope", 5, "shroud"))
        p.append(lathe([(0, 0), (0.05, 0), (0.05, 0.05), (0, 0.05)], 8, "iron", "deadeye", loc=tuple(a + Vector((0, 0, 0.06)))))
        p.append(box((0.04, 0.04, 0.12), loc=a, base=True, mat="iron", name="chainplate"))
    if rank >= 2:
        for sx in (-1, 1):
            back, front = (anchors[0], anchors[1]) if sx < 0 else (anchors[2], anchors[3])
            hb = Vector((back.x * mast_r / foot * 0.7, back.y * mast_r / foot * 0.7, top))
            hf = Vector((front.x * mast_r / foot * 0.7, front.y * mast_r / foot * 0.7, top))
            n = 4 + rank
            for i in range(1, n):
                t = i / n * 0.9
                p.append(tube([(back + Vector((0, 0, 0.14))).lerp(hb, t), (front + Vector((0, 0, 0.14))).lerp(hf, t)],
                              0.011, "rope", 4, "ratline"))
    return p


def masthead(rank: int, rng: random.Random, k: float):
    """The turret about its pivot: the yard with knives hanging from it, the crow's nest from rank 2, the
    topmast. Returns (parts, muzzle)."""
    p = []
    yard_half = (0.65, 0.8, 0.95)[rank - 1]
    yard_z = 0.18 if rank == 1 else -0.12
    p.append(lathe([(0.0, -0.2), (0.115, -0.2), (0.115, 0.0), (0.0, 0.0)], 10, "iron", "cap"))   # the mast's cap
    slope = math.tan(math.radians(COCKBILL))

    def on_yard(x: float) -> float:   # the yard's height at x: cockbilled, its starboard arm low
        return yard_z - x * slope

    p.append(beam((-yard_half, 0, on_yard(-yard_half)), (yard_half, 0, on_yard(yard_half)), 0.09, 0.09, "timber",
                  seed=4))
    p.append(lathe([(0, 0), (0.07, 0.03), (0.07, 0.15), (0, 0.18)], 8, "iron", "sling", loc=(0, 0, yard_z - 0.09)))
    for sx in (-1, 1):
        p.append(box((0.06, 0.11, 0.11), loc=(sx * yard_half, 0, on_yard(sx * yard_half)), rot=(0, COCKBILL, 0),
                     mat="iron", bevel=0.01, name="yardarm"))
    n_hang = (4, 6, 8)[rank - 1]
    for i in range(n_hang):
        x = -yard_half + 0.12 + (2 * yard_half - 0.24) * (i + 0.5) / n_hang
        if rank == 1 and x > yard_half - 0.3:
            continue   # the lantern's end
        p += hanging((x, 0, on_yard(x) - 0.045), rng.uniform(0.08, 0.3), rng, k)
    top_h = (0.35, 0.85, 1.0)[rank - 1]
    p.append(tube([(0, 0, 0), (0, 0, top_h)], 0.08, "timber", 8, "topmast", radii=[0.085, 0.065], metres=0.8))
    p.append(lathe([(0, 0), (0.1, 0), (0.1, 0.05), (0, 0.07)], 10, "timber", "truck", loc=(0, 0, top_h)))
    if rank == 1:
        end = Vector((yard_half - 0.08, 0, on_yard(yard_half - 0.08) - 0.05))
        p.append(tube([end, end - Vector((0, 0, 0.12))], 0.01, "iron", 4, "lantern"))
        p += lantern(end - Vector((0, 0, 0.36)), 0.12)
        muzzle = Vector((0, 0.2, yard_z))
    else:
        # the crow's nest: a planked tub on the cap, iron-hooped, a lantern hung under its floor
        nr = (0, 0.4, 0.47)[rank - 1]
        nh = 0.32
        p.append(lathe([(0, 0), (nr, 0), (nr + 0.02, nh), (nr - 0.04, nh), (nr - 0.05, 0.06), (0, 0.06)], 14,
                       "planks", "nest", metres=0.8, smooth_angle=35))
        for z in (0.04, nh - 0.05):
            p.append(lathe([(nr + 0.004 + 0.02 * z / nh, 0), (nr + 0.02 + 0.02 * z / nh, 0.0), (nr + 0.02 + 0.02 * z / nh, 0.05),
                            (nr + 0.004 + 0.02 * z / nh, 0.05)], 14, "iron", "hoop", loc=(0, 0, z), smooth_angle=None))
        for a in range(4):   # trestle brackets under the floor
            ang = math.radians(45 + 90 * a)
            q = Vector((math.cos(ang), math.sin(ang), 0))
            p.append(beam(q * 0.08 + Vector((0, 0, -0.35)), q * (nr - 0.05) + Vector((0, 0, -0.01)), 0.06, 0.06,
                          "timber", seed=a))
        at = Vector((0, -nr * 0.6, -0.04))
        p.append(tube([at, at - Vector((0, 0, 0.1))], 0.01, "iron", 4, "lantern"))
        p += lantern(at - Vector((0, 0, 0.32)), 0.12 + 0.01 * rank)
        muzzle = Vector((0, nr + 0.08, nh * 0.7))
        if rank >= 3:   # a crown of blades round the rim, points out and up
            for i in range(10):
                ang = 2 * math.pi * (i + 0.25) / 10
                out = Vector((math.cos(ang), math.sin(ang), 0.0))
                rim = out * (nr - 0.02) + Vector((0, 0, nh - 0.06))
                d = (out + Vector((0, 0, 0.9))).normalized()
                tip = rim + d * 0.43 * k
                p += knife(aim(tip, tip - d, 90), k)
    if rank >= 3:   # a skull spiked on the topmast by a long knife, and a pennant at the truck
        sz = top_h * 0.45
        p += skull((0, 0.05, sz), 0.28, mat="bone", pitch=-6)
        p += stuck((0, 0.24, sz + 0.2), (0, -1, -0.12), rng, k * 1.3, 0.16)
        pen = cloth(0.18, 0.55, folds=2, amp=0.02, hem="swallow", name="banner", cols=8)
        xform(pen, Matrix.Rotation(math.radians(-90), 4, "Y"))   # the hoist up the topmast, the fly out along +X
        xform(pen, Matrix.Translation((0.06, 0, top_h - 0.13)))
        p.append(pen)
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.6)
    return p, muzzle


def build(rank: int) -> None:
    reset()
    rng = random.Random(40 + rank)
    stat, deck = plinth(body_h=0.92, seed=30 + rank)
    k = (1.35, 1.45, 1.55)[rank - 1]     # the knives, larger than life to read from the battle camera
    h = (1.75, 2.05, 2.35)[rank - 1]     # the mast from the deck to the yaw pivot
    mr = 0.13
    pivot = deck + h
    p = []
    # the mast stepped in an octagonal partner, iron-hooped
    p.append(lathe([(0, 0), (0.3, 0), (0.3, 0.1), (0.2, 0.16), (0, 0.16)], 8, "timber", "partner", phase=22.5,
                   loc=(0, 0, deck - 0.02), smooth_angle=None))
    p.append(tube([(0, 0, deck), (0, 0, pivot - 0.2)], mr, "timber", 10, "mast", radii=[mr, mr * 0.88], metres=1.2))
    for z in (deck + 0.3, deck + h * 0.55):
        p += lashing((0, 0, z), mr * 0.97, 0.07, "iron")
    if rank >= 2:   # a red sash knotted round the mast, its tails hanging
        p += lashing((0, 0, deck + h * 0.72), mr * 0.95, 0.14, "banner")
        for dx in (-0.04, 0.05):
            tail = cloth(0.09, 0.42 + dx, folds=1, amp=0.01, hem="points", n_points=1, name="banner", cols=4)
            xform(tail, Matrix.Translation((dx, mr + 0.01, deck + h * 0.72 + 0.1)))
            rot_z(tail, 160 + dx * 300)
            p.append(tail)
    p += rigging(deck, pivot - 0.3, mr, rank)
    # knives driven into the mast all round, the target board on its south face
    board_z = deck + 0.62 + 0.1 * rank
    board_r = (0.3, 0.34, 0.38)[rank - 1]
    n = (8, 12, 16)[rank - 1]
    for i in range(n):
        z = deck + 0.3 + (h - 0.6) * (i + rng.uniform(0.1, 0.9)) / n
        a = rng.uniform(0, 2 * math.pi)
        if abs(z - board_z) < board_r + 0.1 and math.sin(a) < -0.3:
            a += math.pi   # not through the board
        out = Vector((math.cos(a), math.sin(a), 0))
        into = -out + Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(-0.45, 0.2)))
        p += stuck(out * mr * 0.95 + Vector((0, 0, z)), into, rng, k)
    for i in range(rank):   # rope bands with knives tucked in, their blades bristling out and up
        z = deck + 0.45 + 0.4 * i + (0.55 if i else 0.0) + 0.12 * rank
        p += lashing((0, 0, z), mr * 0.96, 0.09)
        for j in range(7):
            a = 2 * math.pi * (j + 0.5 * i) / 7 + 0.3
            out = Vector((math.cos(a), math.sin(a), 0))
            if abs(z - board_z) < board_r + 0.12 and math.sin(a) < -0.5:
                continue   # the board's face
            d = (out + Vector((0, 0, 0.45))).normalized()
            tip = out * mr + Vector((0, 0, z + 0.045)) + d * 0.32 * k
            p += knife(aim(tip, tip - d, 90), k)
    p += target((0, -mr - 0.07, board_z), board_r, rng, 2 + rank, k)
    p.append(beam((0, -mr - 0.06, board_z - board_r * 0.6), (0, -0.02, board_z - board_r * 0.6), 0.05, 0.05,
                  "iron", name="bracket"))
    # dockside clutter on the deck
    p += coil((0.42, -0.05, deck), 0.15, 3)
    if rank >= 2:
        p += crate((-0.44, 0.06, deck), 0.28, 15)
    if rank >= 3:   # a spare knife driven into the crate's lid
        p += stuck((-0.44, 0.06, deck + 0.29), (0.2, -0.1, -1.0), rng, k)
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 1.0)
    tower = merge(stat + p, "tower")
    parts, muzzle = masthead(rank, rng, k)
    turret = merge(parts, "turret")
    turret.location = (0, 0, pivot)
    empty("fx_muzzle", tuple(muzzle), parent=turret)
    tris = sum(len(f.vertices) - 2 for o in (tower, turret) for f in o.data.polygons)
    print(f"tower_knife_{rank}: {tris} triangles, pivot {pivot:.2f}")
    export(f"tower_knife_{rank}")


if __name__ == "__main__":
    for r in (1, 2, 3):
        build(r)
