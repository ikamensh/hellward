"""A Thorned Hulk: a bark-hided jungle brute with long arms that slams with both fists. The body and its weapon are generated (art/gen/hulk/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("hulk", 2.2, walk="Heavyset", hunch=12, eyes=(1.0, 0.5, 0.1), arms=0.8))
