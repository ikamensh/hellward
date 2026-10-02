"""A Blood Witch: a pale sorceress in a crimson gown who curses towers with a blood-crystal staff. The body and its weapon are generated (art/gen/witch/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

# the search took the horn bases for eyes (they outshine the dark-lined eyes): read off views.py --focus
build(Spec("witch", 1.8, walk="Proud", eyes=(1.0, 0.2, 0.12), leader=True,
           eyes_at=((0.04, 1.62), (-0.04, 1.62)), eyes_find="fixed",
           weapon=Weapon("blood_staff", 1.7, grip=0.45, staff=True, metal=None,
                         glow={"hot": {"hues": (340, 15), "strength": 1.5}})))
