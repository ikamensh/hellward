"""The field wall of wall.py with its +X end fallen: the courses step down to the footing course (about 0.3 m
with the stones lying on it), the last cope has keeled over, and the fallen stones lie spilled at the foot,
most of them on the +Y side."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix  # noqa: E402

from drystone import LENGTH, TOP, Ground, Grooves, Stone, Wall, lay, tumbled  # noqa: E402
from village import Mesh, finish  # noqa: E402

grooves = Grooves()
m = Mesh("wall_broken", seed=11)
wall = Wall(seed=11)        # the same wall as wall.py
r = random.Random(5)

# where each course now ends: the footing runs the whole length, the courses above step back from the break
ENDS = (LENGTH, 1.2, 0.6, 0.1)
loose = []   # stones out of the wall's bond: laid whole, undersides and all
for ci, end in enumerate(ENDS):
    row = [st for st in wall.courses[ci] if st.centre.x < end]
    # the stone at the break has worked loose
    if ci and row:
        last = max(row, key=lambda st: st.centre.x)
        tilt = (Matrix.Rotation(math.radians(r.uniform(-6, 6)), 4, "Z")
                @ Matrix.Rotation(math.radians(r.uniform(2, 6)), 4, "Y"))
        row.remove(last)
        loose.append(last.transform(tilt).transform(Matrix.Translation((r.uniform(0.01, 0.03), r.uniform(-0.04, 0.05), 0))))
    wall.courses[ci] = row
copes = [st for st in wall.copes if st.centre.x < ENDS[3] - 0.08]
# the last cope standing has keeled over
lean = copes.pop()
foot = max(v.x for v in lean.c.values())
copes.append(lean.transform(Matrix.Rotation(math.radians(28), 4, "Y"), pivot=(foot, 0, TOP - 0.03)))
wall.copes = copes

ground = Ground()
for row in wall.courses:
    for st in row:
        if st.centre.x > -0.5:
            ground.add(st)
for st in wall.copes[-4:] + loose:
    ground.add(st)

# a cope fallen flat across the stepped break, then the spill: face stones and copes heaped at the foot
fallen = Stone.box((0.11, 0.23, 0.06), r, jit=0.015)
fallen = fallen.transform(Matrix.Rotation(math.radians(-8), 4, "X") @ Matrix.Rotation(math.radians(70), 4, "Z"))
loose.append(ground.settle(lambda: fallen.transform(Matrix.Translation((0.42, 0.05, 1.5))), tries=1))
spots = ([(r.uniform(0.9, 1.9), r.uniform(-0.12, 0.12)) for _ in range(3)]
         + [(r.uniform(0.3, 2.5), 0.4 + abs(r.gauss(0, 0.38))) for _ in range(11)]
         + [(r.uniform(0.6, 2.3), -0.38 - abs(r.gauss(0, 0.2))) for _ in range(4)])
spots.sort(key=lambda p: abs(p[1]))   # those nearest the wall first: the rest heap against and on them
for n, (x, y) in enumerate(spots):
    if n % 4 == 3:   # a cope, lying on its side
        half = (r.uniform(0.045, 0.075), r.uniform(0.2, 0.24), r.uniform(0.1, 0.13))

        def make(x=x, y=y, half=half):
            st = Stone.box(half, r, jit=0.015)
            st = st.transform(Matrix.Rotation(r.uniform(0, 2 * math.pi), 4, "Z")
                              @ Matrix.Rotation(math.radians(90 + r.uniform(-12, 12)), 4, "Y"), pivot=(0, 0, 0))
            return st.transform(Matrix.Translation((x + r.uniform(-0.12, 0.12), y + r.uniform(-0.12, 0.12), 1.5)))
    else:
        half = (r.uniform(0.11, 0.23), r.uniform(0.09, 0.22), r.uniform(0.055, 0.1))

        def make(x=x, y=y, half=half):
            return tumbled(r, half, (x + r.uniform(-0.12, 0.12), y + r.uniform(-0.12, 0.12)), tilt=16)
    loose.append(ground.settle(make))
# grit: chips knocked off in the fall
chips = []
for _ in range(8):
    half, at = (r.uniform(0.04, 0.07), r.uniform(0.03, 0.06), r.uniform(0.025, 0.04)), (r.uniform(0.4, 2.6), r.uniform(-0.6, 1.3))
    chips.append(ground.settle(lambda half=half, at=at: tumbled(r, half, at, tilt=30), tries=6, sink=0.01))

wall.build(m, grooves, m.rng, extra=loose)
for st in chips:
    lay(m, st, grooves, m.rng, bevel=0.0)
finish("wall_broken", [m])
