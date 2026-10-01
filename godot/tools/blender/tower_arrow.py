"""The arrow tower in three ranks: a wooden ballista on a gothic stone plinth. Built by tower_arrow_1..3.py.

Rank 1 carries the ballista on a flared timber post; rank 2 raises it on a braced trestle with a planked
platform skirted in red cloth; rank 3 is heavier still: iron-banded legs, a hoarding parapet, banners on
spear poles, a bigger iron-shod ballista. The ballista is the child `turret` (origin = yaw pivot) with
`fx_muzzle` at the bolt's tip.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from towers import (beam, box, cloth, empty, export, lathe, merge, plinth, prism, reset, rot_z, shade, skull, spike,  # noqa: E402
                    tube, uvbox, xform)


def ballista(rank: int):
    """The turret, built about its pivot (the origin), facing +Y. Returns (parts, muzzle)."""
    p = []
    z = 0.36  # height of the bow's plane above the pivot
    arm = (1.05, 1.15, 1.25)[rank - 1]
    wood = "planks"
    # turntable and the yoke that carries the stock
    p.append(lathe([(0, 0), (0.36, 0), (0.36, 0.05), (0.31, 0.08), (0, 0.08)], 16, "planks", "turret", metres=0.8))
    p.append(lathe([(0.37, 0.0), (0.37, 0.035), (0.33, 0.035), (0.33, 0.0)], 16, "iron", "turret"))
    for sx in (-1, 1):
        cheek = prism([(-0.32, 0.0), (0.26, 0.0), (0.18, 0.3), (-0.22, 0.3)], 0.06, mat=wood, name="turret")
        xform(cheek, Matrix.Rotation(math.radians(90), 4, "Z"))
        xform(cheek, Matrix.Translation((sx * 0.11, 0.0, 0.08)))
        uvbox(cheek, 0.8, 3 + sx)
        p.append(shade(cheek, 40))
        p.append(lathe([(0, 0), (0.045, 0), (0.045, 0.03), (0, 0.03)], 8, "iron", "turret"))
        xform(p[-1], Matrix.Rotation(math.radians(90 * sx), 4, "Y"))
        xform(p[-1], Matrix.Translation((sx * 0.14, 0.0, 0.26)))
    # the stock, with iron straps
    p.append(beam((0, -0.82, z - 0.06), (0, 1.02, z - 0.06), 0.16, 0.12, wood, name="turret", seed=11))
    for y in (-0.55, -0.15, 0.95):
        p.append(box((0.18, 0.05, 0.14), loc=(0, y, z - 0.06), mat="iron", bevel=0.01, name="turret"))
    # the bow frame (capitulum) holding two twisted rope skeins
    fy = 0.66
    for sx in (-1, 1):
        p.append(beam((sx * 0.34, fy, z - 0.24), (sx * 0.34, fy, z + 0.24), 0.08, 0.12, wood, name="turret"))
        p.append(beam((sx * 0.09, fy, z - 0.24), (sx * 0.09, fy, z + 0.24), 0.07, 0.12, wood, name="turret"))
        skein = lathe([(0, 0), (0.07, 0), (0.078, 0.12), (0.08, 0.24), (0.078, 0.36), (0.07, 0.48), (0, 0.48)], 10,
                      "rope", "turret", metres=0.35)
        xform(skein, Matrix.Translation((sx * 0.215, fy, z - 0.24)))
        p.append(skein)
        for zz in (z - 0.27, z + 0.24):
            p.append(lathe([(0, 0), (0.1, 0), (0.1, 0.035), (0, 0.035)], 10, "iron", "turret"))
            xform(p[-1], Matrix.Translation((sx * 0.215, fy, zz)))
    for zz in (z - 0.27, z + 0.24):
        p.append(beam((-0.42, fy, zz + 0.015), (0.42, fy, zz + 0.015), 0.1, 0.08, wood, name="turret", seed=5))
        for sx in (-1, 1):
            p.append(box((0.07, 0.15, 0.1), loc=(sx * 0.42, fy, zz + 0.015), mat="iron", bevel=0.012, name="turret"))
    # the arms sweep out and back from the skeins; iron-shod tips
    tips = []
    for sx in (-1, 1):
        root = Vector((sx * 0.215, fy + 0.02, z))
        elbow = Vector((sx * (0.38 + arm * 0.45), fy - 0.06, z + 0.02))
        tip = Vector((sx * (0.38 + arm), fy - 0.32, z + 0.08))
        p.append(beam(root, elbow, 0.11, 0.14, wood, name="turret", seed=7 + sx))
        p.append(beam(elbow, tip, 0.1, 0.13, wood, name="turret", taper=0.72, seed=9 + sx, extend=0.03))
        p.append(box((0.13, 0.13, 0.16), loc=(0, 0, 0), mat="iron", bevel=0.02, name="turret"))
        xform(p[-1], Matrix.Translation(tip))
        if rank >= 2:
            p.append(box((0.14, 0.17, 0.17), loc=elbow, mat="iron", bevel=0.015, name="turret"))
        if rank >= 3:
            p.append(spike(tip + Vector((sx * 0.04, 0, 0)), tip + Vector((sx * 0.24, -0.03, 0.06)), 0.04, "iron", 5,
                           "turret"))
        tips.append(tip + Vector((0, -0.02, 0)))
    # drawn string to the claw, and the loaded bolt
    claw = Vector((0, -0.42, z + 0.06))
    p.append(tube([tips[0], claw, tips[1]], 0.014, "rope", 5, "turret"))
    p.append(box((0.1, 0.12, 0.08), loc=(0, -0.45, z + 0.03), mat="iron", bevel=0.012, name="turret"))
    bz = z + 0.06
    head = 1.36 + 0.06 * (rank - 1)
    p.append(tube([(0, -0.4, bz), (0, head - 0.16, bz)], 0.028, "timber", 6, "turret"))
    p.append(spike((0, head - 0.2, bz), (0, head, bz), 0.055, "iron", 4, "turret"))
    p.append(lathe([(0.0, 0), (0.04, 0), (0.04, 0.05), (0.0, 0.05)], 6, "iron", "turret"))
    xform(p[-1], Matrix.Rotation(math.radians(-90), 4, "X"))
    xform(p[-1], Matrix.Translation((0, head - 0.24, bz)))
    for ang in (0, 120, 240):
        vane = prism([(0, 0), (0.24, 0), (0.2, 0.075), (0.04, 0.085)], 0.012, mat="feather_red", name="turret")
        xform(vane, Matrix.Rotation(math.radians(90), 4, "Z"))
        xform(vane, Matrix.Rotation(math.radians(ang + 180), 4, "Y"))
        xform(vane, Matrix.Translation((0, -0.36, bz)))
        p.append(vane)
    # the winch at the back
    wy = -0.7
    for sx in (-1, 1):
        p.append(box((0.05, 0.12, 0.2), loc=(sx * 0.12, wy, z - 0.2), base=True, mat=wood, bevel=0.01,
                     name="turret"))
    axle = lathe([(0, 0), (0.05, 0), (0.05, 0.42), (0, 0.42)], 8, "timber", "turret")
    xform(axle, Matrix.Rotation(math.radians(90), 4, "Y"))
    xform(axle, Matrix.Translation((-0.21, wy, z - 0.07)))
    p.append(axle)
    for sx in (-1, 1):
        for k in range(4):
            spoke = box((0.025, 0.025, 0.26), mat="iron", name="turret")
            xform(spoke, Matrix.Translation((sx * 0.2, wy, z - 0.07)) @ Matrix.Rotation(math.radians(45 * k + 20), 4, "X"))
            p.append(spoke)
    if rank >= 3:
        # an iron mantlet guarding the pivot, a skull on it
        shield = prism([(-0.3, 0), (0.3, 0), (0.3, 0.22), (0.0, 0.34), (-0.3, 0.22)], 0.05, mat="iron",
                       name="turret")
        xform(shield, Matrix.Rotation(math.radians(-12), 4, "X"))
        xform(shield, Matrix.Translation((0, 0.4, 0.02)))
        p.append(shield)
        p += skull((0, 0.44, 0.07), 0.15, mat="bone", pitch=-12)
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.6)
    return p, Vector((0, head, bz))


def post_tower(deck: float, top: float):
    """Rank 1: a flared timber post from a stone collar, iron-banded, with a heraldic plate and a corbelled
    timber capital the turret turns on. Returns (parts, pivot height)."""
    p = [box((0.78, 0.78, 0.16), loc=(0, 0, deck), base=True, bevel=0.03, mat="stone", name="collar"),
         box((0.62, 0.62, 0.1), loc=(0, 0, deck + 0.16), base=True, bevel=0.025, mat="stone", name="collar")]
    for part in p:
        uvbox(part, 2.0, 5)
    p.append(beam((0, 0, deck), (0, 0, top - 0.12), 0.44, 0.44, "timber", bev=0.045, seed=2, metres=1.5))
    for i in range(4):
        a = math.radians(45 + 90 * i)
        c, s = math.cos(a), math.sin(a)
        p.append(beam((c * 0.66, s * 0.66, deck - 0.02), (c * 0.2, s * 0.2, deck + 1.1), 0.15, 0.15, "timber",
                      seed=20 + i, extend=0.05, metres=1.5))
        p.append(box((0.22, 0.22, 0.07), loc=(c * 0.64, s * 0.64, deck), base=True, mat="iron", bevel=0.015,
                      name="iron"))
        rot_z(p[-1], 45 + 90 * i, (c * 0.64, s * 0.64, 0))
    for zz in (deck + 0.42, deck + 1.18):
        p.append(box((0.5, 0.5, 0.08), loc=(0, 0, zz), mat="iron", bevel=0.012, name="iron"))
    # the front plate: a pointed iron shield with a gilded cross
    sh = prism([(-0.17, 0), (0.17, 0), (0.17, 0.32), (0, 0.44), (-0.17, 0.32)], 0.04, mat="iron", name="iron")
    xform(sh, Matrix.Rotation(math.pi, 4, "X"))
    xform(sh, Matrix.Translation((0, 0.24, top - 0.42)))
    p.append(sh)
    p.append(box((0.045, 0.03, 0.28), loc=(0, 0.27, top - 0.64), mat="gold", name="iron"))
    p.append(box((0.18, 0.03, 0.045), loc=(0, 0.27, top - 0.58), mat="gold", name="iron"))
    # capital: four brackets carry a square cap board, iron at its corners
    for i in range(4):
        a = math.radians(90 * i)
        c, s = math.cos(a), math.sin(a)
        p.append(beam((c * 0.2, s * 0.2, top - 0.62), (c * 0.42, s * 0.42, top - 0.13), 0.12, 0.12, "timber",
                      seed=40 + i))
    p.append(box((0.92, 0.92, 0.14), loc=(0, 0, top - 0.14), base=True, mat="timber", bevel=0.025, name="cap"))
    uvbox(p[-1], 1.5, 9)
    for cx in (-1, 1):
        for cy in (-1, 1):
            p.append(box((0.2, 0.2, 0.18), loc=(cx * 0.4, cy * 0.4, top - 0.16), base=True, mat="iron", bevel=0.02,
                         name="iron"))
            p.append(spike((cx * 0.4, cy * 0.4, top + 0.02), (cx * 0.47, cy * 0.47, top + 0.24), 0.045, "iron", 4,
                           "iron"))
    return p, top


def trestle(deck: float, top: float, rank: int):
    """Ranks 2 and 3: four splayed legs, two tiers of cross-braces, a planked platform on joists."""
    p = []
    lo, hi = 0.58, 0.5
    plat = 1.6 if rank == 2 else 1.8
    legs = []
    for cx in (-1, 1):
        for cy in (-1, 1):
            a = (cx * lo, cy * lo, deck - 0.05)
            b = (cx * hi, cy * hi, top - 0.12)
            legs.append((Vector(a), Vector(b)))
            p.append(beam(a, b, 0.17, 0.17, "timber", seed=30 + 2 * cx + cy, extend=0.0, metres=1.2))
            p.append(box((0.26, 0.26, 0.08), loc=(a[0], a[1], deck), base=True, mat="iron", bevel=0.012,
                         name="iron"))
            if rank >= 3:
                for t in (0.15, 0.85):
                    q = Vector(a).lerp(Vector(b), t)
                    p.append(box((0.21, 0.21, 0.07), loc=q, mat="iron", bevel=0.01, name="iron"))
    # sides: a girt at each tier and an X of braces between
    order = [(0, 1), (1, 3), (3, 2), (2, 0)]
    tiers = [0.0, 0.5, 1.0]
    for i, j in order:
        (a0, b0), (a1, b1) = legs[i], legs[j]
        pts = [[a0.lerp(b0, t), a1.lerp(b1, t)] for t in tiers]
        for t in range(1, len(tiers)):
            p.append(beam(pts[t][0], pts[t][1], 0.12, 0.12, "timber", extend=0.06, seed=40 + t + i))
            p.append(beam(pts[t - 1][0], pts[t][1], 0.08, 0.08, "timber", extend=-0.04, seed=50 + i + t))
            p.append(beam(pts[t - 1][1], pts[t][0], 0.08, 0.08, "timber", extend=-0.04, seed=60 + i + t))
            mid = (pts[t - 1][0] + pts[t][1] + pts[t - 1][1] + pts[t][0]) / 4
            out = Vector((mid.x, mid.y, 0)).normalized()
            plate = box((0.1, 0.1, 0.1), loc=mid + out * 0.04, mat="iron", bevel=0.015, name="iron")
            p.append(plate)
    # joists, corbel struts and the planked platform
    for s in (-1, 1):
        p.append(beam((-plat / 2, s * hi, top - 0.13), (plat / 2, s * hi, top - 0.13), 0.12, 0.14, "timber", seed=70))
        p.append(beam((s * hi, -plat / 2, top - 0.27), (s * hi, plat / 2, top - 0.27), 0.12, 0.14, "timber", seed=71))
    for (a, b) in legs:
        out = Vector((b.x, b.y, 0)).normalized()
        knee = a.lerp(b, 0.82)
        p.append(beam(knee, Vector((b.x, b.y, top - 0.1)) + out * 0.32, 0.09, 0.09, "timber", seed=80))
    planks = box((plat, plat, 0.08), loc=(0, 0, top - 0.06), base=True, mat="planks", bevel=0.01, name="planks")
    uvbox(planks, 1.0)
    # mark the boards with shallow grooves: thin dark battens across the deck edge
    p.append(planks)
    edge = plat / 2
    for s in (-1, 1):
        p.append(beam((-edge - 0.02, s * edge, top - 0.04), (edge + 0.02, s * edge, top - 0.04), 0.08, 0.1, "timber",
                      seed=90))
        p.append(beam((s * edge, -edge, top - 0.04), (s * edge, edge, top - 0.04), 0.08, 0.1, "timber", seed=91))
    # red cloth skirts hung below the platform edge, cut into points, gathered in folds
    skirt_h = 0.6 if rank == 2 else 0.75
    for f in range(4):
        w = plat - 0.06
        sk = cloth(w, skirt_h, folds=5, amp=0.025, hem="points", n_points=4, flare=0.06, name="cloth")
        xform(sk, Matrix.Translation((0, edge + 0.07, top - 0.03)))
        rot_z(sk, -90 * f)
        p.append(sk)
        trim = box((w + 0.04, 0.035, 0.05), loc=(0, edge + 0.08, top - 0.07), mat="gold", name="cloth")
        rot_z(trim, -90 * f)
        p.append(trim)
    return p, top


def railing(top: float, plat: float, rank: int):
    """Rank 3's hoarding: a timber parapet with merlons, open on the front for the bolt."""
    p = []
    e = plat / 2 - 0.05
    h = 0.32
    for f in range(4):
        for k in range(5):
            x = -e + 2 * e * k / 4
            p.append(beam((x, e, top), (x, e, top + h + (0.1 if k % 2 == 0 else 0)), 0.07, 0.07, "timber", seed=k + f))
            rot_z(p[-1], -90 * f)
        p.append(beam((-e, e, top + h), (e, e, top + h), 0.06, 0.08, "timber", seed=f, extend=0.03))
        rot_z(p[-1], -90 * f)
        p.append(beam((-e, e, top + 0.12), (e, e, top + 0.12), 0.05, 0.06, "timber", seed=f + 4, extend=0.03))
        rot_z(p[-1], -90 * f)
    return p


def banner_pole(x: float, y: float, z: float, h: float, face: float):
    """An iron spear pole with a gilded tip and a swallow-tailed red banner hung from a crossbar, the banner
    facing `face` degrees from +Y."""
    p = [tube([(x, y, z), (x, y, z + h)], 0.03, "iron", 6, "pole")]
    p.append(spike((x, y, z + h), (x, y, z + h + 0.3), 0.05, "gold", 4, "pole"))
    p.append(lathe([(0, 0), (0.06, 0.02), (0.05, 0.07), (0, 0.08)], 8, "gold", "pole", loc=(x, y, z + h - 0.04)))
    bw, bh = 0.4, 1.0
    cross = beam((-bw / 2 - 0.06, 0, 0), (bw / 2 + 0.06, 0, 0), 0.035, 0.035, "iron", name="pole")
    ban = cloth(bw, bh, folds=2, amp=0.03, hem="swallow", name="banner", cols=10)
    emblem = lathe([(0, 0), (0.08, 0), (0.08, 0.012), (0, 0.012)], 10, "gold", "banner")
    xform(emblem, Matrix.Rotation(math.radians(-90), 4, "X"))
    xform(emblem, Matrix.Translation((0, 0.02, -bh * 0.4)))
    for part in (cross, ban, emblem):
        xform(part, Matrix.Translation((0, 0.05, z + h - 0.1)))
        rot_z(part, face)
        xform(part, Matrix.Translation((x, y, 0)))
        p.append(part)
    return p


def build(rank: int) -> None:
    reset()
    body_h = (0.92, 0.92, 1.08)[rank - 1]
    stat, deck = plinth(body_h=body_h, seed=rank)
    if rank == 1:
        more, pivot = post_tower(deck, 3.36)
    else:
        top = (0, 3.95, 4.55)[rank - 1]
        more, pivot = trestle(deck, top, rank)
        if rank == 3:
            more += railing(top, 1.8, rank)
            for cx in (-1, 1):
                more += banner_pole(cx * 0.85, -0.85, top - 0.35, 1.5, 90 * cx)
        # a round timber dais lifts the turret over the deck (and rank 3's parapet)
        dais = 0.12 if rank == 2 else 0.3
        more.append(lathe([(0, 0), (0.5, 0), (0.5, dais - 0.04), (0.46, dais), (0, dais)], 16, "planks", "dais",
                          loc=(0, 0, pivot), metres=1.0, smooth_angle=30))
        more.append(lathe([(0.51, dais * 0.25), (0.51, dais * 0.25 + 0.05), (0.49, dais * 0.25 + 0.05),
                           (0.49, dais * 0.25)], 16, "iron", "iron", loc=(0, 0, pivot)))
        pivot += dais
    for part in more:
        if part.data.uv_layers.active is None:
            uvbox(part, 1.0)
    tower = merge(stat + more, "tower")
    parts, muzzle = ballista(rank)
    if rank >= 2:
        for part in parts:
            xform(part, Matrix.Scale(1.2 if rank == 2 else 1.3, 4))
        muzzle = muzzle * (1.2 if rank == 2 else 1.3)
    turret = merge(parts, "turret")
    turret.location = (0, 0, pivot)
    empty("fx_muzzle", tuple(muzzle), parent=turret)
    tris = sum(len(p.vertices) - 2 for o in (tower, turret) for p in o.data.polygons)
    print(f"tower_arrow_{rank}: {tris} triangles, pivot {pivot:.2f}")
    export(f"tower_arrow_{rank}")
