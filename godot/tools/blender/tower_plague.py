"""The plague totem in three ranks (tower_plague_1..3.glb, one run): a timber pole rising from a pool of glowing
venom on the gothic plinth, skulls threaded on it (one more each rank), crowned by a horned ram's skull whose
sockets burn green; venom drips from the skulls from rank 2, and rank 3's crown spreads wider horns.
`fx_muzzle` is between the ram skull's horns, where its shots leave; `fx_glow` lights the pool."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Vector  # noqa: E402

from towers import (PLINTH_W, empty, export, hull, lathe, merge, plinth, reset, skull, spike, tube,  # noqa: E402
                    uvbox)


def build(rank: int) -> None:
    reset()
    rng = random.Random(30 + rank)
    stat, deck = plinth(body_h=0.92, seed=8)
    p = []
    half = (PLINTH_W - 0.36) / 2
    # the pool: a low rim of slimed stone round a disc of glowing venom
    p.append(lathe([(0.0, 0.0), (half * 0.92, 0.0), (half * 0.95, 0.06), (half * 0.86, 0.08), (0.0, 0.05)], 20,
                   "stone", "pool", loc=(0, 0, deck - 0.02)))
    p.append(lathe([(0.0, 0.0), (half * 0.86, 0.0), (0.0, 0.0)], 20, "venom_pool", "venom", loc=(0, 0, deck + 0.055)))
    # the pole: a crooked timber shaft, lashed
    height = (2.2, 2.65, 3.1)[rank - 1]
    pts = [(rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), deck + height * k / 6) for k in range(7)]
    p.append(tube(pts, 0.085, "timber", 8, "pole", radii=[0.11, 0.1, 0.095, 0.09, 0.085, 0.08, 0.075], metres=0.8))
    for k in range(rank + 1):
        z = deck + 0.25 + 0.5 * k
        p.append(lathe([(0.1, 0), (0.115, 0.02), (0.115, 0.07), (0.1, 0.09)], 8, "rope", "lashing", loc=(0, 0, z)))
    # skulls threaded on the pole, alternately turned, the last crowned with the ram's horns
    count = rank
    top = deck + height
    for k in range(count):
        z = deck + 0.75 + (height - 1.15) * k / max(count, 1)
        p += skull((0, 0.04, z), 0.34, yaw=(-18, 14, -8)[k % 3], mat="bone", dark="glow_venom", pitch=-4)
        if rank >= 2:   # venom dripping from the jaw
            for d in range(2):
                a = Vector((rng.uniform(-0.06, 0.06), 0.15, z + 0.03))
                p.append(spike(a, a - Vector((0, 0, rng.uniform(0.12, 0.26))), 0.025, "glow_venom", 5, "drip"))
    horns = (1.0, 1.25, 1.55)[rank - 1]
    p += skull((0, 0.05, top - 0.05), 0.5, mat="bone", dark="glow_venom", pitch=-8, horns=horns)
    # rotting rags and a few bones heaped round the pole's foot
    for k in range(5 + 2 * rank):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.2, half * 0.7)
        c = Vector((math.cos(a) * r, math.sin(a) * r, deck + 0.07))
        p.append(hull([tuple(c + Vector((rng.uniform(-0.09, 0.09), rng.uniform(-0.09, 0.09), rng.uniform(0, 0.06))))
                       for _ in range(8)], "bone" if k % 2 else "charred", "litter"))
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.8)
    tower = merge(stat + p, "tower")
    empty("fx_muzzle", (0, 0.2, top + 0.3))
    empty("fx_glow", (0, 0, deck + 0.3))
    tris = sum(len(f.vertices) - 2 for f in tower.data.polygons)
    print(f"tower_plague_{rank}: {tris} triangles, crown at {top:.2f}")
    export(f"tower_plague_{rank}")


for r in (1, 2, 3):
    build(r)
