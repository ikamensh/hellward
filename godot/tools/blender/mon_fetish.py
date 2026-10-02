"""A Fetish Shaman: a tiny masked jungle leader that curses towers and raises flayers, its spear held as a staff. The body and its weapon are generated (art/gen/fetish/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("fetish", 1.0, walk="OnToesCrouched", eyes=(1.0, 0.75, 0.2), leader=True,
            weapon=Weapon("spear", 1.2, grip=0.3, staff=True, metal=None)))
