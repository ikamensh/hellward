"""A Goatman: a ram-headed demon warrior on goat legs with a long battle axe, strutting. The body and its weapon are generated (art/gen/goatman/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("goatman", 1.9, walk="Strutting", run=True, idle="Proud", hunch=6, eyes=(1.0, 0.5, 0.1),
            weapon=Weapon("goat_axe", 1.6, grip=0.25)))
