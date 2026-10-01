"""A banded wooden barrel, 1 m tall."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from lib import *  # noqa: F401,F403

reset()
staves = cylinder(0.36, 1.0, mat="planks", verts=20, base=True, name="staves")
# bulge the middle
for v in staves.data.vertices:
    t = v.co.z
    k = 1.0 + 0.12 * (1 - ((t - 0.5) / 0.5) ** 2)
    v.co.x *= k
    v.co.y *= k
uv_cube(staves, 1.0)
parts = [staves]
for z in (0.12, 0.88, 0.38, 0.62):
    r = 0.36 * (1.0 + 0.12 * (1 - ((z - 0.5) / 0.5) ** 2)) + 0.012
    band = cylinder(r, 0.05, loc=(0, 0, z), mat="iron", verts=20, cap=False, name="band")
    parts.append(band)
lid = cylinder(0.33, 0.03, loc=(0, 0, 0.97), mat="planks", verts=20, name="lid")
uv_cube(lid, 1.0)
parts.append(lid)
for p in parts:
    smooth(p, 50)
join(parts, "barrel")
export("barrel")
