"""A Zealot of Zakarum: a hooded cultist bent forward with a flanged mace. The body and its weapon are generated (art/gen/zealot/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("zealot", 1.85, walk="BentForward", eyes=(1.0, 0.8, 0.35), weapon=Weapon("mace", 0.8, grip=0.15)))
