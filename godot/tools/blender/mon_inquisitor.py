"""A Zakarum Inquisitor: a tall priest in white and gold who marks towers for a curse with his crozier. The body and its weapon are generated (art/gen/inquisitor/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

# the eye search took the mitre's gilt for eyes: they are read off tools/blender/views.py (art/gen/inquisitor/game.glb
# --stand 2.0 180 --focus 1.66 0.24), shadowed sockets under the brow, lit where they are
build(Spec("inquisitor", 2.0, walk="Proud", eyes=(1.0, 0.8, 0.35), leader=True,
           eyes_at=((0.02, 1.716), (-0.024, 1.716)), eyes_find="fixed",
            weapon=Weapon("crozier", 2.1, grip=0.4, staff=True)))
