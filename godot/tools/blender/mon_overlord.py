"""An Overlord: a huge fat horned brute with a spiked club, lumbering. The body and its weapon are generated (art/gen/overlord/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("overlord", 2.2, walk="Heavyset", hunch=8, eyes=(1.0, 0.75, 0.2), weapon=Weapon("club", 1.3, grip=0.12)))
