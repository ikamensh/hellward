"""A shipping crate, 0.9 m: boarded faces with gaps, edge battens and a diagonal brace on each side, iron
corner plates, the lid knocked askew with straw spilling out."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, X, Y, Z, finish, rot  # noqa: E402

m = Mesh("crate", seed=9)
r = m.rng
S = 0.9
h = S / 2
m.box((-h + 0.03, -h + 0.03, 0.0), (h - 0.03, h - 0.03, S - 0.04), "charred", world=True)  # dark inside the gaps
faces = [(X, Y), (-X, -Y), (Y, -X), (-Y, X)]  # (outward normal, along)
for n, along in faces:
    centre = n * h + Z * (S / 2 - 0.02)
    for i in range(4):  # boards, horizontal
        zc = 0.05 + (S - 0.14) * (i + 0.5) / 4
        m.block(n * (h - 0.012) + Z * zc + along * r.uniform(-0.005, 0.005), (along, n, Z),
                (h - 0.01, 0.012, (S - 0.14) / 8 - 0.008), "planks", grain=0)
    # battens round the edge and a brace
    for zc in (0.06, S - 0.1):
        m.block(n * (h + 0.012) + Z * zc, (along, n, Z), (h - 0.07, 0.014, 0.05), "timber", grain=0)
    for s in (-1, 1):
        m.block(n * (h + 0.012) + along * s * (h - 0.05) + Z * (S / 2 - 0.02), (along, n, Z), (0.05, 0.015, S / 2 - 0.03),
                "timber", grain=2)
    a = n * (h + 0.01) + along * (-h + 0.1) + Z * 0.11
    b = n * (h + 0.01) + along * (h - 0.1) + Z * (S - 0.15)
    m.beam(a, b, 0.07, 0.022, "timber", n=n)
    for s in (-1, 1):  # iron corner plates
        for zc in (0.06, S - 0.1):
            m.block(n * (h + 0.022) + along * s * (h - 0.04) + Z * zc, (along, n, Z), (0.045, 0.004, 0.06), "iron",
                    metres=0.4, grain=0)
# straw inside, the lid shoved aside and resting on one edge
for _ in range(5):
    m.rock((r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.25), S - 0.1), (0.35, 0.3, 0.16), "thatch", metres=0.8,
           squash=0.8)
lid = rot(Z, 18) @ rot(Y, -9)
c = Vector((0.14, 0.08, S + 0.02))
for i in range(4):
    yc = -h + 0.02 + (S - 0.04) * (i + 0.5) / 4
    m.block(c + lid @ Vector((0, yc, 0)), (lid @ X, lid @ Y, lid @ Z), (h, (S - 0.04) / 8 - 0.007, 0.012), "planks",
            grain=0)
for xc in (-h + 0.08, h - 0.08):
    m.block(c + lid @ Vector((xc, 0, 0.022)), (lid @ X, lid @ Y, lid @ Z), (0.045, h - 0.03, 0.012), "timber", grain=1)
for _ in range(4):  # straw hanging over the rim
    a = r.uniform(0, 2 * math.pi)
    m.rock((math.cos(a) * (h - 0.05), math.sin(a) * (h - 0.05), S - 0.05), (0.25, 0.12, 0.08), "thatch", metres=0.8)
finish("crate", [m])
