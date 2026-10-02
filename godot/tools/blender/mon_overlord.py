"""An Overlord: a huge fat horned brute with a spiked club, lumbering. The body and its weapon are generated (art/gen/overlord/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

# the eyes sit below the search's skull-crown window (it took brow spikes): read off views.py --focus,
# small dark slits under the brow, lit where they are
build(Spec("overlord", 2.2, walk="Heavyset", hunch=8, eyes=(1.0, 0.75, 0.2),
           eyes_at=((0.05, 1.86), (-0.05, 1.86)), eyes_find="fixed",
           weapon=Weapon("club", 1.3, grip=0.12)))
