"""A gate pier for the gaps in the field walls: 1.2 m of dressed stone, square, on a broader plinth course,
four courses of two blocks each laid crosswise in turn (so no joint runs up the pier), under a drip-edged
cap slab and a pyramid weathering. The origin is at the centre of its base."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mathutils import Matrix, Vector  # noqa: E402

from drystone import KEYS, Grooves, Stone, lay  # noqa: E402
from village import Mesh, finish  # noqa: E402

grooves = Grooves()
m = Mesh("wall_post", seed=29)
r = random.Random(29)
W = 0.28           # half width of the shaft
PLINTH = (0.34, 0.16)
COURSES = (0.21, 0.2, 0.2, 0.19)
CAP = (0.35, 0.085)
TOP = 1.2


def dressed(lo, hi, jit=0.006, face=0.008) -> Stone:
    """A squared block between corners lo and hi, its faces a few millimetres out of true."""
    out = {}
    for key in KEYS:
        p = Vector([(lo[a] if key[a] < 0 else hi[a]) for a in range(3)])
        p += Vector((r.uniform(-jit, jit), r.uniform(-jit, jit), r.uniform(-jit * 0.5, jit * 0.5)))
        out[key] = p
    st = Stone(out)
    # set the block a touch proud or sunk, and a hair off square
    return st.transform(Matrix.Translation((r.uniform(-face, face), r.uniform(-face, face), 0))
                        @ Matrix.Rotation(math.radians(r.uniform(-1.2, 1.2)), 4, "Z"))


stones = []
# the plinth: two long blocks, bedded a little into the ground
pw, ph = PLINTH
split = r.uniform(-0.06, 0.06)
stones.append(dressed((-pw, -pw, -0.04), (split - 0.005, pw, ph)))
stones.append(dressed((split + 0.005, -pw, -0.04), (pw, pw, ph)))
z = ph
for i, h in enumerate(COURSES):
    cut = r.choice((-1, 1)) * r.uniform(0.04, 0.09)   # one block long, one short
    if i % 2 == 0:
        stones.append(dressed((-W, -W, z), (cut - 0.005, W, z + h)))
        stones.append(dressed((cut + 0.005, -W, z), (W, W, z + h)))
    else:
        stones.append(dressed((-W, -W, z), (W, cut - 0.005, z + h)))
        stones.append(dressed((-W, cut + 0.005, z), (W, W, z + h)))
    z += h
# the cap: a slab overhanging the shaft, then a pyramid weathering to the top
cw, ch = CAP
stones.append(dressed((-cw, -cw, z), (cw, cw, z + ch), jit=0.004, face=0.004))
z += ch
pyr = {}
for key in KEYS:
    half = cw - 0.035 if key[2] < 0 else 0.03
    pyr[key] = Vector((key[0] * half, key[1] * half, z if key[2] < 0 else TOP))
stones.append(Stone(pyr))

for st in stones:
    lay(m, st, grooves, r, bevel=0.012 if st is stones[-1] else 0.018, bottom=False)
finish("wall_post", [m])
