"""A Flayer: a tiny masked jungle imp darting on its toes with a bone spear. The body and its weapon are generated (art/gen/flayer/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("flayer", 0.9, walk="OnToesCrouched", eyes=(1.0, 0.75, 0.2), weapon=Weapon("spear", 1.1, grip=0.3, attack="thrust", metal=None)))
