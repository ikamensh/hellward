"""A street lamp: a squared post on a stone footing, a braced arm, and an iron lantern hanging from a hook
with a flame inside."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, Y, Z, finish, lantern  # noqa: E402

m = Mesh("lamppost", seed=23)
r = m.rng
m.box((-0.24, -0.24, -0.1), (0.24, 0.24, 0.22), "stone", metres=1.2)
m.box((-0.18, -0.18, 0.22), (0.18, 0.18, 0.3), "stone", metres=1.2)
m.beam((0, 0, 0.2), (0.015, 0, 3.3), 0.15, 0.15, n=Y, taper=0.85)
m.lathe([(0.1, 3.28), (0.1, 3.36), (0.0, 3.46)], 4, "timber", smooth=False)
arm = 0.8
m.beam((-0.05, 0, 3.05), (arm, 0, 3.08), 0.09, 0.1, n=Z)
m.beam((0.03, 0, 2.55), (0.5, 0, 3.04), 0.07, 0.07, n=Y)
m.beam((arm - 0.06, 0, 3.08), (arm - 0.06, 0, 2.92), 0.02, 0.02, "iron")
m.tube([(arm - 0.06, 0.0, 2.92), (arm - 0.06, 0.03, 2.89), (arm - 0.06, 0.0, 2.86), (arm - 0.06, -0.03, 2.89),
        (arm - 0.06, 0.0, 2.92)], 0.008, 4, "iron", smooth=False, caps=(False, False))
# the lantern
c = Vector((arm - 0.06, 0, 2.45))
lantern(m, c)
m.tube([c + Z * 0.42, c + Z * 0.5], 0.025, 6, "iron")
finish("lamppost", [m], fx=[("fx_light", c + Z * 0.0)])
