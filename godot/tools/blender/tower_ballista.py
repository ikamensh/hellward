"""The ballista in three ranks (tower_ballista_1..3.glb, one run): a heavy siege crossbow on a stone turntable
over a round stone drum on the gothic plinth. Beside the Arrow Tower's tall timber ballista it reads squat and
heavy: an iron prod, an iron-clad stock, a windlass to span it and a bolt with an armour-piercing bodkin head.

Rank 1 sits on a low drum with a single steel prod and a crank; rank 2 raises the drum to a corbelled parapet,
doubles the prod into a leaf spring and spans it with two spoked wheels; rank 3 crenellates the drum, triples the
prod with spiked tips, sets a horned skull on the bridle and racks spare bolts against the drum. Each rank's
crossbow is larger. The crossbow and its turntable are the child `turret` (origin = yaw pivot) with `fx_muzzle`
at the bolt's point.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from towers import (beam, box, empty, export, lathe, merge, plinth, prism, reset, rot_z, shade, skull, spike,  # noqa: E402
                    tube, uvbox, xform)

DRUM_R = 0.6


def bolt(tail, head, r: float, vanes: str = "leather", head_mat: str = "iron"):
    """A heavy bolt from its tail to its point: a timber shaft, a long four-sided bodkin head on an iron socket,
    three stiff vanes at the tail."""
    tail, head = Vector(tail), Vector(head)
    d = (head - tail).normalized()
    hl = r * 7.0
    p = [tube([tail, head - d * hl * 0.8], r, "timber", 6, "bolt")]
    p.append(tube([head - d * (hl + r * 1.5), head - d * hl * 0.85], r * 1.45, "iron", 6, "bolt"))
    p.append(spike(head - d * hl, head, r * 1.9, head_mat, 4, "bolt"))
    for ang in (0, 120, 240):
        vane = prism([(0, 0), (r * 8, 0), (r * 6.5, r * 2.6), (r * 1.2, r * 2.8)], r * 0.35, mat=vanes, name="bolt")
        xform(vane, Matrix.Rotation(math.radians(90), 4, "Z"))
        xform(vane, Matrix.Rotation(math.radians(ang), 4, "Y"))
        rot = d.to_track_quat("Y", "Z").to_matrix().to_4x4()
        xform(vane, Matrix.Translation(tail + d * r * 0.5) @ rot)
        p.append(vane)
    return p


def wheel(c, axis_x: float, radius: float, spokes: int = 6):
    """A spoked windlass wheel turning about X at `c`: a timber rim bound in iron, a hub, its spokes."""
    c = Vector(c)
    pts = [c + Vector((0, radius * math.cos(2 * math.pi * k / 16), radius * math.sin(2 * math.pi * k / 16)))
           for k in range(16)]
    p = [tube(pts, radius * 0.11, "timber", 6, "wheel", closed=True, metres=0.6)]
    p.append(tube([q + Vector((axis_x * radius * 0.06, 0, 0)) for q in pts], radius * 0.07, "iron", 5, "wheel",
                  closed=True))
    hub = lathe([(0, 0), (radius * 0.2, 0), (radius * 0.2, radius * 0.3), (0, radius * 0.3)], 8, "iron", "wheel")
    xform(hub, Matrix.Translation(c) @ Matrix.Rotation(math.radians(90), 4, "Y")
          @ Matrix.Translation((0, 0, -radius * 0.15)))
    p.append(hub)
    for k in range(spokes):
        a = 2 * math.pi * (k + 0.5) / spokes
        tip = c + Vector((0, radius * math.cos(a), radius * math.sin(a)))
        p.append(beam(c, tip, radius * 0.1, radius * 0.1, "timber", name="wheel", seed=k))
        p.append(beam(tip, tip + (tip - c).normalized() * radius * 0.28, radius * 0.08, radius * 0.08, "timber",
                      name="wheel", taper=0.6, seed=k + 9))   # the handles out past the rim
    return p


def crossbow(rank: int):
    """The turret, built about its pivot (the origin), facing +Y. Returns (parts, muzzle)."""
    p = []
    # the stone turntable, iron-rimmed, and the timber carriage it carries
    p.append(lathe([(0, 0), (DRUM_R, 0), (DRUM_R, 0.1), (DRUM_R - 0.05, 0.14), (0, 0.14)], 20, "stone",
                   "turntable", metres=1.5, smooth_angle=30))
    p.append(lathe([(DRUM_R + 0.015, 0.02), (DRUM_R + 0.015, 0.08), (DRUM_R - 0.01, 0.08), (DRUM_R - 0.01, 0.02)], 20,
                   "iron", "turntable"))
    for k in range(8):   # the rim's rivets
        a = 2 * math.pi * k / 8
        p.append(box((0.06, 0.06, 0.06), loc=(math.cos(a) * (DRUM_R + 0.02), math.sin(a) * (DRUM_R + 0.02), 0.05),
                     mat="iron", bevel=0.01, name="turntable"))
    zs = 0.66 + 0.04 * (rank - 1)             # the stock's top
    span = (1.0, 1.15, 1.3)[rank - 1]         # half the prod's width
    yp = 0.78                                 # where the prod crosses the stock
    for sx in (-1, 1):
        cheek = prism([(-0.55, 0.0), (0.5, 0.0), (0.42, 0.2), (0.18, zs - 0.1), (-0.3, zs - 0.12), (-0.5, 0.22)], 0.12,
                      mat="timber", name="turret")
        xform(cheek, Matrix.Rotation(math.radians(90), 4, "Z"))
        xform(cheek, Matrix.Translation((sx * 0.22, 0.0, 0.14)))
        uvbox(cheek, 1.0, 3 + sx)
        p.append(shade(cheek, 40))
        for y, z in ((-0.4, 0.3), (0.32, 0.3), (0.0, zs - 0.08)):   # iron straps across the cheek
            p.append(box((0.15, 0.1, 0.12), loc=(sx * 0.22, y, z + 0.08), mat="iron", bevel=0.015, name="turret"))
    trunnion = lathe([(0, 0), (0.07, 0), (0.07, 0.62), (0, 0.62)], 8, "iron", "turret")
    xform(trunnion, Matrix.Translation((-0.31, 0.0, zs - 0.12)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    p.append(trunnion)
    # the stock, clad in iron plates down both sides
    p.append(beam((0, -1.0, zs - 0.1), (0, yp + 0.22, zs - 0.1), 0.26, 0.2, "timber", name="turret", seed=11))
    for sx in (-1, 1):
        p.append(box((0.025, 1.7, 0.13), loc=(sx * 0.135, -0.15, zs - 0.1), mat="iron", bevel=0.006, name="turret"))
    for y in (-0.85, -0.4, 0.1, 0.55):
        p.append(box((0.3, 0.07, 0.23), loc=(0, y, zs - 0.1), mat="iron", bevel=0.012, name="turret"))
    # the prod: a thick recurved steel bow; from rank 2 a leaf spring, shorter leaves laid behind the first
    tips = []
    leaves = rank
    r0 = (0.08, 0.085, 0.09)[rank - 1]
    gap = 1.05 * r0                          # one leaf pressed behind the next

    def bow_y(x: float) -> float:
        u = x / span
        back = u * u - 0.35 * (max(0.0, abs(u) - 0.75) / 0.25) ** 2   # swept back, the tips turned forward again
        return yp - 0.44 * back

    for leaf in range(leaves):
        s = span * (1.0 - 0.22 * leaf)
        rl = r0 * (1.0 - 0.08 * leaf)
        n = 16
        pts, radii = [], []
        for i in range(n + 1):
            u = -1 + 2 * i / n
            pts.append((u * s, bow_y(u * s) - gap * leaf, zs - 0.02))
            radii.append(rl * (1.0 - 0.45 * abs(u)))
        p.append(tube(pts, rl, "steel", 8, "prod", radii=radii, metres=0.5))
        if leaf == 0:
            tips = [Vector(pts[0]), Vector(pts[-1])]
    if leaves > 1:   # iron clamps binding the leaves together
        deep = gap * (leaves - 1) + 2.2 * r0
        for u in (-0.62, -0.32, 0.32, 0.62):
            x = u * span
            p.append(box((0.07, deep, 2.5 * r0), loc=(x, bow_y(x) - gap * (leaves - 1) / 2, zs - 0.02), mat="iron",
                         bevel=0.012, name="turret"))
    for t in tips:   # iron caps at the tips, spikes from rank 3
        sx = 1 if t.x > 0 else -1
        p.append(box((0.12, 0.15, 0.17), loc=t, mat="iron", bevel=0.02, name="turret"))
        if rank >= 3:
            p.append(spike(t + Vector((sx * 0.05, 0, 0)), t + Vector((sx * 0.34, 0.04, 0.05)), 0.05, "iron", 5,
                           "turret"))
    # the bridle clamping the prod to the stock's head
    bridle_d = 0.3 + gap * (leaves - 1)
    p.append(box((0.38, bridle_d, 0.34), loc=(0, yp - gap * (leaves - 1) / 2, zs - 0.02), mat="iron", bevel=0.03,
                 name="turret"))
    # the string drawn back to the nut, and the loaded bolt
    nut = Vector((0, -0.48, zs + 0.05))
    p.append(tube([tips[0] + Vector((0, -0.03, 0)), nut, tips[1] + Vector((0, -0.03, 0))], 0.022, "rope", 5, "turret"))
    p.append(box((0.16, 0.14, 0.12), loc=(0, -0.5, zs + 0.03), mat="iron", bevel=0.02, name="turret"))
    br = (0.045, 0.05, 0.055)[rank - 1]
    head = Vector((0, yp + 0.62 + 0.06 * rank, zs + 0.05))
    p += bolt((0, -0.46, zs + 0.05), head, br, head_mat="steel")
    # the windlass at the stock's tail: a crank at rank 1, two spoked wheels from rank 2
    wy, wz = -0.88, zs + 0.12
    for sx in (-1, 1):
        p.append(beam((sx * 0.16, wy, zs - 0.2), (sx * 0.16, wy, wz + 0.08), 0.08, 0.14, "timber", name="turret",
                      seed=20 + sx))
    reach = 0.33 if rank == 1 else 0.48
    axle = lathe([(0, 0), (0.055, 0), (0.055, 2 * reach), (0, 2 * reach)], 8, "timber", "turret")
    xform(axle, Matrix.Translation((-reach, wy, wz)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    p.append(axle)
    p.append(tube([(0, wy, wz), (0, -0.55, zs + 0.06)], 0.02, "rope", 5, "turret"))
    if rank == 1:
        for sx in (-1, 1):
            arm = Vector((sx * reach, wy, wz))
            elbow = arm + Vector((0, -0.05, 0.26))
            p.append(beam(arm, elbow, 0.05, 0.05, "iron", name="turret"))
            p.append(tube([elbow, elbow + Vector((sx * 0.14, 0, 0))], 0.025, "timber", 6, "turret"))
    else:
        for sx in (-1, 1):
            p += wheel((sx * (reach - 0.03), wy, wz), sx, (0.0, 0.3, 0.36)[rank - 1])
    if rank >= 2:   # a gilded band round the bridle
        p.append(box((0.4, bridle_d + 0.02, 0.05), loc=(0, yp - gap * (leaves - 1) / 2, zs + 0.1), mat="gold",
                     bevel=0.01, name="turret"))
    if rank >= 3:   # a horned skull glaring from under the bridle's face
        p += skull((0, yp + 0.06, zs - 0.34), 0.25, mat="bone", horns=1.2)
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.6)
    return p, head


def drum(deck: float, rank: int):
    """The fixed stone drum the turntable rides on: twelve battered faces, iron bands, arrow slits, a corbelled
    parapet from rank 2 (crenellated at rank 3). Returns (parts, pivot height)."""
    h = (0.5, 0.78, 1.02)[rank - 1]
    r = DRUM_R + 0.02
    p = [lathe([(0, 0), (r + 0.06, 0), (r + 0.02, 0.2), (r, h), (0, h)], 12, "stone", "drum", phase=15, metres=2.0,
               loc=(0, 0, deck - 0.02), smooth_angle=None)]
    uvbox(p[-1], 2.0, 3 + rank)
    for z in (0.2, h - 0.1):
        p.append(lathe([(r + 0.035, 0), (r + 0.035, 0.07), (0, 0.07)], 12, "iron", "band", phase=15,
                       loc=(0, 0, deck - 0.02 + z), smooth_angle=None))
    if rank >= 2:   # arrow slits on four faces, dark in the stone
        for f in range(4):
            a = math.radians(45 + 90 * f)
            slit = box((0.07, 0.03, 0.3), loc=(0, r - 0.005, deck + h * 0.55), mat="basalt", name="slit")
            rot_z(slit, math.degrees(a) - 90)
            p.append(slit)
    top = deck - 0.02 + h
    if rank >= 2:   # corbels and a parapet ring round the turntable
        for k in range(12):
            a = 2 * math.pi * (k + 0.5) / 12
            c = box((0.12, 0.16, 0.14), loc=(0, r + 0.04, top - 0.14), mat="stone", bevel=0.015, name="corbel")
            rot_z(c, math.degrees(a) - 90)
            p.append(c)
        p.append(lathe([(r + 0.13, 0), (r + 0.13, 0.12), (DRUM_R + 0.04, 0.12), (DRUM_R + 0.04, 0)], 24, "stone",
                       "parapet", loc=(0, 0, top - 0.02), metres=2.0, smooth_angle=30))
        if rank >= 3:
            for k in range(8):
                a = 2 * math.pi * (k + 0.5) / 8
                m = box((0.24, 0.13, 0.2), loc=(0, r + 0.08, top + 0.1), base=True, mat="stone", bevel=0.02,
                        name="merlon")
                rot_z(m, math.degrees(a) - 90)
                p.append(m)
    for part in p[1:]:
        if part.data.uv_layers.active is None:
            uvbox(part, 2.0, 7)
    return p, top


def rack(deck: float, br: float):
    """Rank 3's spare bolts leant against the drum's back, an iron hoop round their feet."""
    p = []
    for k, x in enumerate((-0.32, -0.1, 0.12, 0.34)):
        foot = Vector((x, -0.86, deck + 0.02))
        tip = Vector((x * 0.6, -0.66, deck + 1.2 + 0.05 * (k % 2)))
        p += bolt(foot, tip, br * 0.8)
    p.append(box((0.86, 0.06, 0.06), loc=(0.01, -0.84, deck + 0.3), mat="iron", bevel=0.01, name="rack"))
    return p


def build(rank: int) -> None:
    reset()
    stat, deck = plinth(body_h=(0.86, 0.92, 1.0)[rank - 1], seed=10 + rank)
    more, pivot = drum(deck, rank)
    if rank >= 3:
        more += rack(deck, 0.055)
    for part in more:
        if part.data.uv_layers.active is None:
            uvbox(part, 1.0)
    tower = merge(stat + more, "tower")
    parts, muzzle = crossbow(rank)
    grow = (1.15, 1.25, 1.35)[rank - 1]
    for part in parts:
        xform(part, Matrix.Scale(grow, 4))
    muzzle = muzzle * grow
    turret = merge(parts, "turret")
    turret.location = (0, 0, pivot)
    empty("fx_muzzle", tuple(muzzle), parent=turret)
    tris = sum(len(f.vertices) - 2 for o in (tower, turret) for f in o.data.polygons)
    print(f"tower_ballista_{rank}: {tris} triangles, pivot {pivot:.2f}")
    export(f"tower_ballista_{rank}")


if __name__ == "__main__":
    for r in (1, 2, 3):
        build(r)
