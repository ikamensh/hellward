"""Azazel the Flayer, Act I's boss: a winged demon lord in chitin armour with a molten greatsword; its eyes
and the cracks in its armour and blade burn. The body and its weapon are generated (art/gen/azazel/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("azazel", 2.6, walk="Proud", hunch=4, eyes=(1.0, 0.5, 0.1), hot={"hues": (8, 45), "strength": 1.4},
            weapon=Weapon("flame_sword", 1.7, grip=0.12, glow={"hot": {"hues": (8, 45), "strength": 1.6}})))
