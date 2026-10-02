"""A Zealot of Zakarum: a hooded cultist bent forward with a flanged mace. The body and its weapon are generated (art/gen/zealot/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

# BentForward folds its long hood to the waist (the head's pitch on a 44 cm lever), and Old at 0.19 m/s
# cannot keep up with the rules; a plain walk stooped by hunch (which pitches the head back up) does both
# the search found nothing in the shadowed sockets (it lit the hood instead): read off views.py --focus
build(Spec("zealot", 1.85, walk="Neutral", hunch=10, eyes=(1.0, 0.8, 0.35),
           eyes_at=((0.035, 1.62), (-0.03, 1.62)), eyes_find="fixed",
           weapon=Weapon("mace", 0.8, grip=0.15)))
