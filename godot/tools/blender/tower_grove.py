"""The druid grove in three ranks (tower_grove_1..3.glb, one run): on a mound of mossy earth a ring of standing
stones cut with glowing runes round a gnarled, twisting tree; rank 1's tree is bare but for a few sprigs, rank 2
leafs out, rank 3 spreads a full crown and its ring has more stones. `fx_glow` is in the tree's heart,
`fx_muzzle` in its crown."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Vector  # noqa: E402

from towers import box, empty, export, hull, lathe, merge, reset, tube, uvbox  # noqa: E402


def branch(p, rng, start: Vector, direction: Vector, length: float, radius: float, depth: int, tips: list):
    """A crooked branch from `start`, splitting `depth` more times; its tips gathered in `tips`."""
    pts, r = [start], []
    d = direction.normalized()
    for k in range(1, 5):
        d = (d + Vector((rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), rng.uniform(-0.1, 0.25)))).normalized()
        pts.append(pts[-1] + d * length / 4)
    radii = [radius * (1 - 0.55 * k / 4) for k in range(5)]
    p.append(tube([tuple(q) for q in pts], radius, "timber", 7, "tree", radii=radii, metres=0.6))
    if depth == 0:
        tips.append(pts[-1])
        return
    for k in range(2 + (depth > 1)):
        a = rng.uniform(0, 2 * math.pi)
        out = Vector((math.cos(a), math.sin(a), rng.uniform(0.4, 1.1)))
        branch(p, rng, pts[-1 - k % 2], out, length * 0.62, radii[-1 - k % 2] * 0.9, depth - 1, tips)


def build(rank: int) -> None:
    reset()
    rng = random.Random(70 + rank)
    p = []
    # the mound: a low dome of earth with a mossy skin
    p.append(lathe([(0, 0.32), (0.45, 0.3), (0.8, 0.2), (0.95, 0.08), (1.0, 0.0), (0, 0)], 20, "earth", "mound"))
    p.append(lathe([(0, 0.335), (0.42, 0.315), (0.72, 0.22), (0.0, 0.0)], 20, "mossy", "mound"))
    # the ring of standing stones, each a rough slab leaning a little, a rune glowing on its face
    n = 6 + (rank == 3) * 2
    for k in range(n):
        a = 2 * math.pi * (k + 0.5) / n
        r = 0.72
        c = Vector((math.cos(a) * r, math.sin(a) * r, 0.05))
        hgt = rng.uniform(0.75, 1.05) * (1 + 0.1 * (rank - 1))
        wid = rng.uniform(0.24, 0.32)
        tang = Vector((-math.sin(a), math.cos(a), 0))
        out = Vector((math.cos(a), math.sin(a), 0))
        pts = []
        for zf in (0.0, 0.5, 1.0):
            z = c.z + hgt * zf
            ww = wid * (1 - 0.25 * zf)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    pts.append(tuple(c + tang * (sx * ww / 2 + rng.uniform(-0.02, 0.02)) + out * (sy * 0.08 + 0.04 * zf)
                                     + Vector((0, 0, z - c.z + rng.uniform(-0.03, 0.03)))))
        p.append(hull(pts, "mossy", "stone"))
        rune = c + out * -0.1 + Vector((0, 0, hgt * 0.55))
        glyph = box((0.06, 0.012, 0.16), loc=tuple(rune), mat="glow_venom", name="rune")
        glyph.rotation_euler = (0, 0, a + math.pi / 2)
        p.append(glyph)
    # the tree: a twisting trunk out of the mound, its branches splitting to the canopy
    tips: list = []
    trunk_h = (1.6, 2.0, 2.35)[rank - 1]
    pts = []
    for k in range(7):
        t = k / 6
        pts.append(Vector((0.12 * math.sin(t * 5.5), 0.12 * math.cos(t * 4.2) - 0.06, 0.3 + trunk_h * t)))
    p.append(tube([tuple(q) for q in pts], 0.2, "timber", 9, "tree", radii=[0.26, 0.2, 0.17, 0.15, 0.13, 0.11, 0.1],
                  metres=0.8))
    for k in range(4):   # roots gripping the mound
        a = 2 * math.pi * k / 4 + 0.6
        p.append(tube([(0, 0, 0.45), (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.32), (math.cos(a) * 0.55, math.sin(a) * 0.55, 0.12)],
                      0.08, "timber", 6, "root", radii=[0.1, 0.07, 0.03], metres=0.5))
    for k in range(3 + rank):
        a = 2 * math.pi * k / (3 + rank) + rng.uniform(-0.3, 0.3)
        branch(p, rng, pts[-1 - k % 2], Vector((math.cos(a), math.sin(a), 0.8)), 0.9 + 0.15 * rank, 0.085, 1 + (rank > 1), tips)
    # leaves: clumps at the branch tips, more and fuller each rank
    for tip in tips[: (4, 14, 40)[rank - 1]]:
        size = (0.12, 0.24, 0.32)[rank - 1]
        for _ in range(1 if rank == 1 else 2):
            c = tip + Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), rng.uniform(0, 0.1)))
            p.append(hull([tuple(c + Vector((rng.uniform(-size, size), rng.uniform(-size, size), rng.uniform(-size, size) * 0.6)))
                           for _ in range(12)], "leaves", "leaves"))
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.8)
    tower = merge(p, "tower")
    crown = max((t.z for t in tips), default=trunk_h + 0.3)
    empty("fx_glow", (0, 0, 0.3 + trunk_h * 0.45))
    empty("fx_muzzle", (0, 0, crown))
    tris = sum(len(f.vertices) - 2 for f in tower.data.polygons)
    print(f"tower_grove_{rank}: {tris} triangles, crown at {crown:.2f}")
    export(f"tower_grove_{rank}")


for r in (1, 2, 3):
    build(r)
