"""The bone altar in three ranks (tower_altar_1..3.glb, one run): a block of carved stone on the gothic plinth,
skulls and long bones heaped on it, an iron cauldron on its top whose brew glows a sickly green; the game lights
the fire at `fx_fire`. Rank 2 sets curved tusks at its corners, rank 3 a second tier of skulls and a bigger
cauldron on clawed iron legs."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Vector  # noqa: E402

from towers import box, empty, export, lathe, merge, plinth, reset, skull, spike, tube, uvbox  # noqa: E402


def build(rank: int) -> None:
    reset()
    rng = random.Random(50 + rank)
    stat, deck = plinth(body_h=0.92, seed=12)
    p = []
    # the altar block, a little narrower than the deck, with a moulded lip
    w, h = 1.05, 0.62 + 0.12 * (rank - 1)
    p.append(box((w, w, h), loc=(0, 0, deck), base=True, bevel=0.03, mat="stone", name="altar"))
    p.append(box((w + 0.1, w + 0.1, 0.08), loc=(0, 0, deck + h), base=True, bevel=0.02, mat="stone", name="altar"))
    top = deck + h + 0.08
    # skulls along its front and sides, long bones crossed between them
    ring = [(-0.32, 0.5), (0.0, 0.53), (0.32, 0.5), (0.5, 0.15), (-0.5, 0.15)] + ([(0.5, -0.25), (-0.5, -0.25)] if rank == 3 else [])
    for k, (x, y) in enumerate(ring):
        yaw = math.degrees(math.atan2(-x, y))
        p += skull((x, y, top), 0.28 + 0.03 * rng.random(), yaw=yaw + rng.uniform(-15, 15), mat="bone")
    for k in range(4 + rank):
        a = Vector((rng.uniform(-0.45, 0.45), rng.uniform(0.25, 0.5), top + 0.03))
        d = Vector((rng.uniform(-1, 1), rng.uniform(-0.3, 0.3), 0)).normalized() * 0.42
        p.append(tube([tuple(a - d / 2), tuple(a + d / 2)], 0.03, "bone", 6, "bone", radii=[0.045, 0.045], metres=0.4))
    if rank == 3:   # a second tier of skulls stacked behind the first
        for x in (-0.2, 0.2):
            p += skull((x, 0.3, top + 0.24), 0.26, yaw=rng.uniform(-10, 10), mat="bone")
    # tusks curving up from the corners
    if rank >= 2:
        for sx in (-1, 1):
            for sy in (-1, 1):
                base = Vector((sx * 0.55, sy * 0.55, top - 0.02))
                p.append(spike(base, base + Vector((sx * 0.12, sy * 0.12, 0.55 + 0.15 * (rank - 2))), 0.07, "bone", 7,
                               "tusk", bend=(sx * 0.18, sy * 0.18, 0.05)))
    # the cauldron: an iron bowl (on clawed legs at rank 3) brimming with glowing brew
    r = (0.38, 0.42, 0.5)[rank - 1]
    cz = top + (0.05 if rank < 3 else 0.2)
    if rank == 3:
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.4
            p.append(spike((math.cos(a) * r * 0.6, math.sin(a) * r * 0.6, cz + 0.12), (math.cos(a) * r * 0.9, math.sin(a) * r * 0.9, top),
                           0.05, "iron", 5, "leg", bend=(math.cos(a) * 0.08, math.sin(a) * 0.08, 0.04)))
    p.append(lathe([(0, 0), (r * 0.55, 0.02), (r * 0.92, 0.15), (r, 0.32), (r * 0.94, 0.48), (r * 1.02, 0.52),
                    (r * 0.9, 0.52), (r * 0.84, 0.46), (r * 0.88, 0.3), (0, 0.18)], 18, "iron", "cauldron", loc=(0, 0, cz)))
    p.append(lathe([(0, 0), (r * 0.86, 0), (0, 0)], 18, "glow_venom", "brew", loc=(0, 0, cz + 0.44)))
    for part in p:
        if part.data.uv_layers.active is None:
            uvbox(part, 0.8)
    tower = merge(stat + p, "tower")
    empty("fx_fire", (0, 0, cz + 0.46))
    empty("fx_muzzle", (0, 0, cz + 0.9))
    tris = sum(len(f.vertices) - 2 for f in tower.data.polygons)
    print(f"tower_altar_{rank}: {tris} triangles, brew at {cz + 0.44:.2f}")
    export(f"tower_altar_{rank}")


for r in (1, 2, 3):
    build(r)
