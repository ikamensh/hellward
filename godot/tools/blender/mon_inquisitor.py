"""A Zakarum Inquisitor: a tall priest in white and gold who marks towers for a curse with his crozier. The body and its weapon are generated (art/gen/inquisitor/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("inquisitor", 2.0, walk="Proud", eyes=(1.0, 0.8, 0.35), leader=True,
            weapon=Weapon("crozier", 2.1, grip=0.4, staff=True)))
