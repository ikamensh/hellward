"""The frost tower: a cluster of tall ice crystals rising from a frosted gothic plinth. A glowing core runs
through the great crystal (seen through the ice); icicles hang from the cornice and rime crusts the deck.
`fx_glow` marks the crystal heart, `fx_muzzle` its tip."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from towers import PLINTH_W, empty, export, hull, lathe, merge, plinth, reset, spike, xform  # noqa: E402

def build(rank: int) -> None:
    reset()
    rng = random.Random(11)
    stat, deck = plinth(body_h=0.92, seed=6, skull_front=True)
    p = []


    def crystal(base, height, radius, tilt, yaw, mat="ice", sides=6, core=False, name="crystal"):
        """A hexagonal crystal standing at `base`, leaning `tilt` degrees towards `yaw`: a tapering prism with a
        faceted point, its foot sunk below the base."""
        prof = [(0, -0.25 * radius), (radius * 0.85, -0.2 * radius), (radius, 0.05 * height),
                (radius * 0.82, 0.72 * height), (0, height)]
        obj = lathe(prof, sides, mat, name, phase=rng.uniform(0, 60), smooth_angle=None)
        for v in obj.data.vertices:
            v.co.x *= rng.uniform(0.85, 1.12)
            v.co.y *= rng.uniform(0.85, 1.12)
        m = (Matrix.Translation(base) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
             @ Matrix.Rotation(math.radians(tilt), 4, "X"))
        xform(obj, m)
        parts = [obj]
        if core:
            c = lathe([(0, 0.05 * height), (radius * 0.45, 0.15 * height), (radius * 0.38, 0.72 * height), (0, 0.93 * height)],
                      6, "glow_frost", name, smooth_angle=None)
            xform(c, m)
            parts.append(c)
        return parts


    # the great crystal and its court: tall ones leaning out from its foot, small shards round the edge
    top = deck - 0.05
    great_h = (2.2, 2.75, 3.3)[rank - 1]
    p += crystal((0, 0, top), great_h, 0.29, 2, 20, core=True)
    court = [(1.75, 0.2, 13, 15), (1.35, 0.18, 19, 85), (1.95, 0.19, 11, 150), (1.2, 0.17, 22, 215), (1.6, 0.2, 16, 275),
             (1.05, 0.15, 25, 335)]
    for h, r, tilt, ang in court[: (3, 6, 6)[rank - 1]]:
        h *= (0.85, 1.0, 1.2)[rank - 1]
        a = math.radians(ang)
        base = (math.cos(a) * 0.2, math.sin(a) * 0.2, top)
        # tilting about X leans towards -Y: turn so it leans outwards along `ang`
        p += crystal(base, h, r, tilt, ang + 90, core=h > 1.5)
    for k in range(8):
        a = 2 * math.pi * k / 8 + rng.uniform(-0.25, 0.25)
        r = rng.uniform(0.42, 0.56)
        h = rng.uniform(0.35, 0.75)
        p += crystal((math.cos(a) * r, math.sin(a) * r, top), h, rng.uniform(0.07, 0.11), rng.uniform(25, 45),
                     math.degrees(a) + 90)

    # rime on the deck and ledges: flat faceted ice crusts
    half = (PLINTH_W - 0.36) / 2
    for k in range(14):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.2, half)
        cx, cy = math.cos(a) * r, math.sin(a) * r
        s = rng.uniform(0.12, 0.25)
        pts = [(cx + rng.uniform(-s, s), cy + rng.uniform(-s, s), deck + rng.uniform(-0.02, 0.05)) for _ in range(10)]
        p.append(hull(pts, "ice", "rime"))

    # icicles hanging from the cornice (top of the plinth's body) and the niche ledges
    cornice_z = deck - 0.15
    edge = half + 0.06
    for f in range(4):
        for k in range(9):
            x = -edge + 2 * edge * (k + rng.uniform(0.2, 0.8)) / 9
            L = rng.uniform(0.08, 0.32) * (1.0 if k % 3 else 1.4)
            base = Vector((x, edge - 0.01, cornice_z))
            ic = spike(base, base - Vector((0, -0.01, L)), rng.uniform(0.025, 0.04), "ice", 5, "icicle")
            xform(ic, Matrix.Rotation(math.radians(-90 * f), 4, "Z"))
            p.append(ic)
    # icicles under the niche ledges too
    for f in range(4):
        for k in range(4):
            x = -0.26 + 0.52 * (k + rng.uniform(0.2, 0.8)) / 4
            base = Vector((x, half + 0.06, 0.29 + 0.08))
            ic = spike(base, base - Vector((0, 0, rng.uniform(0.06, 0.14))), 0.02, "ice", 4, "icicle")
            xform(ic, Matrix.Rotation(math.radians(-90 * f), 4, "Z"))
            p.append(ic)

    tower = merge(stat + p, "tower")
    heart = (0, 0, top + great_h * 0.45)
    tip = Vector((0, 0, top + great_h))
    # the great crystal leans 3 degrees towards yaw 20: follow it to its tip
    lean = Matrix.Rotation(math.radians(20), 4, "Z") @ Matrix.Rotation(math.radians(3), 4, "X")
    tip = Vector((0, 0, top)) + lean @ Vector((0, 0, great_h))
    empty("fx_glow", heart)
    empty("fx_muzzle", tuple(tip))
    tris = sum(len(f.vertices) - 2 for f in tower.data.polygons)
    print(f"tower_frost_{rank}: {tris} triangles, tip {tuple(round(c, 2) for c in tip)}")
    export(f"tower_frost_{rank}")


for r in (1, 2, 3):
    build(r)
