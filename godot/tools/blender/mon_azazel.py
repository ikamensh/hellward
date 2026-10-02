"""Azazel the Flayer, Act I's boss: a winged demon lord in chitin armour with a molten greatsword; its eyes
and the cracks in its armour and blade burn. The body and its weapon are generated (art/gen/azazel/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

# its wings spread wider than its arms reach: the hands are searched under them, and the wings get their own bones
# (root at the shoulder blade, wrist at the top of the wing, tip at its outer fingers: read off tools/blender/views.py
# --stand 2.6 180)
build(Spec("azazel", 2.6, walk="Proud", hunch=4, eyes=(1.0, 0.5, 0.1), hot={"hues": (8, 45), "strength": 1.4},
           hands_below=0.47, hands_within=0.3, wings=((0.3, -0.12, 1.9), (0.62, -0.08, 2.35), (0.98, -0.04, 1.95)), wings_above=0.6,
            weapon=Weapon("flame_sword", 1.7, grip=0.12, glow={"hot": {"hues": (8, 45), "strength": 1.6}})))
