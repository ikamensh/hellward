"""A two-wheeled hand cart, broken down: one wheel came off and lies against it, so the cart has tipped
onto its axle and pitched forward onto its shafts; sacks have slid out."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, X, Y, Z, finish, rot, sack, wheel  # noqa: E402

m = Mesh("cart", seed=13)
r = m.rng
R = 0.55                   # wheel radius: the axle stands this high
L, Wd = 2.0, 1.15          # bed
zb = R + 0.12              # bed floor
# bed: floor boards on two runners, raved sides, a tailboard
for y in (-0.42, 0.42):
    m.beam((-L / 2, y, zb - 0.06), (L / 2 + 1.75, y * 0.55, zb - 0.06), 0.09, 0.1, n=Z)  # runner running on as a shaft
for i in range(7):
    y = -Wd / 2 + Wd * (i + 0.5) / 7
    m.block((0, y, zb + 0.015), (X, Y, Z), (L / 2, Wd / 14 - 0.006, 0.02), "planks", grain=0)
for s in (-1, 1):
    for zc in (zb + 0.17, zb + 0.4):
        m.block((0, s * (Wd / 2 + 0.02), zc), (X, Y, Z), (L / 2, 0.02, 0.09), "planks", grain=0)
    for x in (-L / 2 + 0.06, -0.3, 0.35, L / 2 - 0.06):
        m.beam((x, s * (Wd / 2 + 0.05), zb - 0.08), (x, s * (Wd / 2 + 0.05), zb + 0.52), 0.06, 0.05, n=Y * s)
m.block((-L / 2 - 0.02, 0, zb + 0.24), (X, Y, Z), (0.02, Wd / 2, 0.2), "planks", grain=1)
m.block((L / 2 + 0.02, 0, zb + 0.14), (X, Y, Z), (0.02, Wd / 2, 0.12), "planks", grain=1)
m.beam((0, -Wd / 2 - 0.25, R), (0, Wd / 2 + 0.25, R), 0.09, 0.09, n=Z)  # axle
m.beam((L / 2 + 1.75, -0.32, zb - 0.06), (L / 2 + 1.75, 0.32, zb - 0.06), 0.06, 0.06, n=Z)  # swingletree bar
wheel(m, (0, Wd / 2 + 0.17, R), Y, R, spokes=10, seed=2)
# tip it: forward onto the shafts (about the axle), then over onto the axle end that lost its wheel
pitch = rot(Y, 11.5)
roll = rot(X, 15.5)
pivot_axle = Vector((0, 0, R))
pivot_wheel = Vector((0, Wd / 2 + 0.17, 0))
m.warp(lambda p: pivot_wheel + roll @ ((pivot_axle + pitch @ (p - pivot_axle)) - pivot_wheel))
# the lost wheel lies against the cart, a sack and a burst one spilled
wheel(m, (-0.35, -Wd / 2 - 0.75, 0.06), rot(X, 8) @ Z, R, spokes=10, broken=2, seed=3)
sack(m, (0.6, -Wd / 2 - 0.55, 0), 0.6, squash=0.6, lean=(0.2, -0.1), seed=1)
sack(m, (1.15, -Wd / 2 - 0.2, 0), 0.5, squash=0.45, lean=(-0.1, 0.2), seed=2)
for _ in range(6):
    m.rock((r.uniform(1.0, 1.6), r.uniform(-Wd / 2 - 0.6, -Wd / 2 + 0.1), 0.02), (0.3, 0.2, 0.05), "thatch",
           metres=0.8)
finish("cart", [m], warp=lambda p: p + Vector((-0.87, 0.55, 0.0)))  # origin to the footprint centre
