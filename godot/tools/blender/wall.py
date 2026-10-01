"""A 4 m length of dry-stone field wall along X, about 0.9 m high: four courses of rough through-stones
breaking joint, battered from 0.62 m deep at the foot to 0.42 m under a coping of stones set on edge. Its
ends are flush, so lengths of wall abut."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drystone import Grooves, Wall  # noqa: E402
from village import Mesh, finish  # noqa: E402

grooves = Grooves()
m = Mesh("wall", seed=11)
Wall(seed=11).build(m, grooves, m.rng)
finish("wall", [m])
