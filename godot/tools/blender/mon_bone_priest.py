"""The Bone Priest, Act II's boss: a towering undead high priest whose skull and staff burn green. The body and its weapon are generated (art/gen/bone_priest/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("bone_priest", 2.5, walk="Old", hunch=6, eyes=(0.4, 1.0, 0.3), leader=True,
            weapon=Weapon("bone_staff", 2.4, grip=0.4, staff=True, metal=None,
                          glow={"hot": {"hues": (80, 160), "strength": 1.6}})))
