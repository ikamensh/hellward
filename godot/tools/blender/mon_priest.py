"""A Bone Acolyte: a hooded undead priest who curses towers with a staff whose orb burns green. The body and its weapon are generated (art/gen/priest/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("priest", 1.85, walk="Old", hunch=8, eyes=(0.4, 1.0, 0.3), leader=True,
            weapon=Weapon("green_staff", 1.9, grip=0.45, staff=True, metal=None,
                          glow={"hot": {"hues": (80, 160), "strength": 1.5}})))
