"""The Hook Tower in three ranks (tower_hook_1..3.glb, one run): a Kurast dockhand's slewing crane on the gothic
plinth. A tarred timber mast turns in a stone socket; its jib reaches out over the lane with a sheave at the tip,
a hoist rope runs from the winch on the mast, and a chain lets down a great iron hook, its bowl opening back
toward the tower: it gaffs a monster and drags it back.

Rank 1 is a short braced jib, a single hook and a lantern on the mast; rank 2 a taller mast whose head carries
stays to a longer jib, a counterweight slung at the jib's tail, a barbed hook and the lantern hung from the jib;
rank 3 the longest jib on two braces, an iron-shod tip, a double hook and a swallow-tailed banner at the
masthead. Coiled rope, bollards and a crate clutter the deck.

The mast and jib are the child `turret` (origin = yaw pivot, the socket's top); the chain and hook hanging from
the tip are its child `hook` (origin at the sheave, so it can swing), with `fx_muzzle` in the hook's bowl.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from docks import bollard, coil, crate, lantern, lashing  # noqa: E402
from towers import (beam, box, chain, cloth, empty, export, lathe, merge, plinth, reset, rot_z, spike,  # noqa: E402
                    tube, uvbox, xform)

TURN = 40.0   # the hook hangs turned off the jib's plane, so its J reads from most sides


def hook(s: float, barbed: bool, double: bool):
    """The hook hanging from its eye's top at the origin, its bowl opening toward -Y: an eye, a swivel, the
    shank, the bowl and its point (a barb from rank 2; a second bowl back to back at rank 3). Returns (parts,
    the bowl's centre)."""
    p = []
    eye_r = 0.075 * s
    ring = [Vector((eye_r * math.cos(2 * math.pi * k / 10), 0, -eye_r + eye_r * math.sin(2 * math.pi * k / 10)))
            for k in range(10)]
    p.append(tube(ring, 0.022 * s, "iron", 6, "hook", closed=True))
    p.append(lathe([(0, 0), (0.06 * s, 0), (0.07 * s, 0.05 * s), (0.06 * s, 0.1 * s), (0, 0.1 * s)], 8, "iron", "hook",
                   loc=(0, 0, -0.25 * s)))
    top, bend = -0.15 * s, -0.55 * s
    r = 0.2 * s
    for side in ((-1, 1) if double else (-1,)):
        pts, radii = [Vector((0, 0, top)), Vector((0, 0, bend))], [0.05 * s, 0.055 * s]
        n = 10
        for i in range(1, n + 1):
            a = -math.pi * i / n
            pts.append(Vector((0, side * r * (1 - math.cos(a)), bend + r * math.sin(a))))
            radii.append(0.055 * s + 0.018 * s * math.sin(-a))
        tip = Vector((0, side * 2 * r - side * 0.03 * s, bend + 0.3 * s))
        pts += [Vector((0, side * 2.06 * r, bend + 0.12 * s)), tip]
        radii += [0.04 * s, 0.006]
        p.append(tube(pts, 0.05 * s, "steel", 8, "hook", radii=radii, metres=0.4))
        if barbed:
            barb_root = Vector((0, side * 2.02 * r, bend + 0.2 * s))
            p.append(spike(barb_root, barb_root + Vector((0, side * 0.1 * s, -0.12 * s)), 0.025 * s, "steel", 4,
                           "hook"))
    return p, Vector((0, -r if not double else 0.0, bend))


def winch(z: float, rank: int):
    """The winch on the mast's back: a rope drum across two iron brackets, cranks at both ends."""
    p = []
    y = -0.3
    w = 0.22 + 0.04 * rank
    drum = lathe([(0, 0), (0.12, 0), (0.12, 0.03), (0.09, 0.04), (0.09, 2 * w - 0.04), (0.12, 2 * w - 0.03),
                  (0.12, 2 * w), (0, 2 * w)], 12, "timber", "winch")
    xform(drum, Matrix.Translation((-w, y, z)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    p.append(drum)
    wraps = [Vector((-w + 0.06 + (2 * w - 0.12) * k / 40, y + 0.1 * math.cos(k * 1.1), z + 0.1 * math.sin(k * 1.1)))
             for k in range(41)]
    p.append(tube(wraps, 0.022, "rope", 5, "winch", metres=0.3))
    for sx in (-1, 1):
        p.append(beam((sx * (w + 0.03), -0.12, z - 0.18), (sx * (w + 0.03), y, z), 0.05, 0.05, "iron", name="winch"))
        p.append(beam((sx * (w + 0.03), -0.12, z + 0.18), (sx * (w + 0.03), y, z), 0.05, 0.05, "iron", name="winch"))
        hub = Vector((sx * (w + 0.06), y, z))
        elbow = hub + Vector((0, -0.04, 0.24))
        p.append(beam(hub, elbow, 0.045, 0.045, "iron", name="winch"))
        p.append(tube([elbow, elbow + Vector((sx * 0.12, 0, 0))], 0.022, "timber", 6, "winch"))
    return p


def crane(rank: int):
    """The turret about its pivot (the origin): the mast, jib, braces, winch and hoist. Returns (parts, the tip
    sheave's bottom, where the hook hangs from)."""
    p = []
    zj = (1.95, 2.2, 2.45)[rank - 1]            # the jib's root on the mast
    head = (0.25, 0.65, 0.8)[rank - 1]          # the mast's head above the jib
    reach = (1.3, 1.65, 1.95)[rank - 1]         # the jib's reach
    tail = (0.25, 0.7, 0.8)[rank - 1]
    mw = 0.26 + 0.02 * rank
    p.append(beam((0, 0, -0.2), (0, 0, zj + head), mw, mw, "timber", bev=0.03, metres=1.5, seed=3))
    for z in [0.3, zj - 0.95] + ([zj + head - 0.12] if rank >= 2 else []):
        p.append(box((mw + 0.05, mw + 0.05, 0.07), loc=(0, 0, z), mat="iron", bevel=0.01, name="band"))
    if rank >= 2:   # an iron cap on the masthead
        p.append(lathe([(0, 0), (mw * 0.75, 0), (mw * 0.75, 0.06), (0.04, 0.16), (0, 0.16)], 8, "iron", "cap",
                       loc=(0, 0, zj + head), smooth_angle=None))
    # the jib, a little raised at its tip, iron at the joint
    root = Vector((0, -tail, zj))
    tip = Vector((0, reach, zj + 0.14))
    p.append(beam(root, tip, 0.18, 0.22, "timber", bev=0.02, seed=5, metres=1.2))
    p.append(box((mw + 0.08, 0.36, 0.34), loc=(0, 0, zj), mat="iron", bevel=0.02, name="joint"))
    p += lashing((0, 0, zj - 0.32), mw * 0.72, 0.1)
    braces = (0.0,) if rank < 3 else (-0.07, 0.07)
    for bx in braces:
        a = Vector((bx, mw / 2, zj - 0.85 - 0.1 * rank))
        b = Vector((bx, reach * 0.55, zj + 0.06))
        p.append(beam(a, b, 0.11, 0.11, "timber", seed=7, extend=0.04))
        p.append(box((0.14, 0.1, 0.14), loc=a, mat="iron", bevel=0.01, name="brace"))
    if rank >= 2:   # stays from the masthead to the tip and the tail
        mh = Vector((0, 0, zj + head - 0.05))
        p.append(tube([mh, tip + Vector((0, -0.08, 0.1))], 0.018, "rope", 5, "stay"))
        p.append(tube([mh, root + Vector((0, 0.1, 0.1))], 0.018, "rope", 5, "stay"))
        # the counterweight: a stone block slung in iron straps under the tail
        cw = root + Vector((0, 0.12, -0.42))
        p.append(box((0.36, 0.3, 0.32), loc=cw, mat="stone", bevel=0.03, name="weight"))
        uvbox(p[-1], 1.0, 4)
        for dx in (-0.1, 0.1):
            p.append(box((0.04, 0.34, 0.36), loc=cw + Vector((dx, 0, 0)), mat="iron", name="weight"))
        for dx in (-0.12, 0.12):
            p.append(tube([cw + Vector((dx, 0, 0.16)), root + Vector((dx * 0.6, 0.12, -0.08))], 0.016, "iron", 4,
                          "weight"))
    if rank >= 3:   # an iron-shod tip with a spike, and gilded straps on the jib
        p.append(box((0.22, 0.2, 0.26), loc=tip + Vector((0, 0.02, 0)), mat="iron", bevel=0.02, name="shoe"))
        p.append(spike(tip + Vector((0, 0.1, 0.04)), tip + Vector((0, 0.42, 0.12)), 0.06, "iron", 5, "shoe"))
        for t in (0.3, 0.65):
            q = root.lerp(tip, t)
            p.append(box((0.22, 0.06, 0.26), loc=q, mat="gold", bevel=0.008, name="strap"))
    # the sheave at the tip, in a timber block
    sheave_c = tip + Vector((0, -0.04, -0.16))
    for sx in (-1, 1):
        p.append(box((0.03, 0.3, 0.32), loc=sheave_c + Vector((sx * 0.065, 0, 0.04)), mat="timber", bevel=0.008,
                     name="block"))
    wheel = lathe([(0, 0), (0.12, 0), (0.12, 0.012), (0.1, 0.03), (0.12, 0.048), (0.12, 0.06), (0, 0.06)], 12,
                  "iron", "sheave")
    xform(wheel, Matrix.Translation(sheave_c + Vector((-0.03, 0, 0))) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    p.append(wheel)
    # the winch and the hoist rope up the mast's back, along the jib's top, over the sheave
    wz = 0.62
    p += winch(wz, rank)
    p.append(tube([(0, -0.3, wz + 0.1), (0, -mw / 2 - 0.03, zj - 0.25), (0, -0.05, zj + 0.17),
                   tip + Vector((0, -0.1, 0.12)), sheave_c + Vector((0, 0.1, 0.1)), sheave_c + Vector((0, 0.12, -0.04))],
                  0.02, "rope", 5, "hoist"))
    # a ship's lantern: on a bracket from the mast at rank 1, hung from the jib after
    if rank == 1:
        arm = Vector((mw / 2, 0, zj - 0.45))
        end = arm + Vector((0.3, 0, 0.05))
        p.append(beam(arm, end, 0.035, 0.035, "iron", name="bracket"))
        p.append(beam(arm + Vector((0, 0, -0.18)), end + Vector((-0.04, 0, 0)), 0.025, 0.025, "iron", name="bracket"))
        p += lantern(end + Vector((0, 0, -0.32)), 0.13)
    else:
        at = root.lerp(tip, 0.72) + Vector((0, 0, -0.11))
        p.append(beam(at, at + Vector((0, 0, -0.18)), 0.02, 0.02, "iron", name="bracket"))
        p += lantern(at + Vector((0, 0, -0.46)), 0.14 + 0.01 * rank)
    if rank >= 3:   # a swallow-tailed banner on a small yard at the masthead
        yard_z = zj + head - 0.22
        p.append(beam((-0.35, 0, yard_z), (0.35, 0, yard_z), 0.05, 0.05, "timber", name="yard"))
        ban = cloth(0.6, 0.85, folds=2, amp=0.03, hem="swallow", name="banner", cols=10)
        xform(ban, Matrix.Translation((0, 0.05, yard_z - 0.03)))
        rot_z(ban, 180)
        p.append(ban)
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.8)
    return p, sheave_c + Vector((0, 0, -0.12))


def deck_clutter(deck: float, rank: int):
    """Coiled rope, bollards and a crate round the socket."""
    p = coil((-0.44, 0.12, deck), 0.17, 3 + rank // 2)
    if rank >= 2:
        p += bollard((0.46, -0.16, deck)) + bollard((0.46, 0.2, deck))
    if rank >= 3:
        p += crate((-0.4, -0.42, deck), 0.3, 20)
        p += coil((0.12, -0.5, deck), 0.12, 3, 0.03, "iron")   # a heap of spare chain
    return p


def build(rank: int) -> None:
    reset()
    stat, deck = plinth(body_h=0.92, seed=20 + rank)
    sock = [lathe([(0, 0), (0.4, 0), (0.4, 0.12), (0.34, 0.2), (0, 0.2)], 12, "stone", "socket", loc=(0, 0, deck),
                  smooth_angle=None),
            lathe([(0.35, 0.2), (0.35, 0.24), (0.2, 0.24), (0.2, 0.2)], 12, "iron", "socket", loc=(0, 0, deck))]
    uvbox(sock[0], 1.5, 2)
    more = sock + deck_clutter(deck, rank)
    for part in more:
        if part.data.uv_layers.active is None:
            uvbox(part, 1.0)
    tower = merge(stat + more, "tower")
    pivot = deck + 0.24
    parts, hang = crane(rank)
    turret = merge(parts, "turret")
    turret.location = (0, 0, pivot)
    # the chain and the hook, about the sheave so the game can swing them
    s = (1.2, 1.35, 1.5)[rank - 1]
    drop = (0.7, 0.8, 0.9)[rank - 1]
    hp = chain((0, 0, 0), (0, 0, -drop), sag=0.0, pitch=0.085, link_w=0.07)
    hk, bowl = hook(s, rank >= 2, rank >= 3)
    turn = Matrix.Translation((0, 0, -drop)) @ Matrix.Rotation(math.radians(TURN), 4, "Z")
    for part in hk:
        xform(part, turn)
    hp += hk
    for part in hp:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.5)
    hanging = merge(hp, "hook")
    hanging.location = tuple(hang)
    hanging.parent = turret
    empty("fx_muzzle", tuple(turn @ bowl), parent=hanging)
    tris = sum(len(f.vertices) - 2 for o in (tower, turret, hanging) for f in o.data.polygons)
    print(f"tower_hook_{rank}: {tris} triangles, pivot {pivot:.2f}")
    export(f"tower_hook_{rank}")


if __name__ == "__main__":
    for r in (1, 2, 3):
        build(r)
