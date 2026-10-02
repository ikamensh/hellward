"""A Thorned Hulk: a bark-hided jungle brute with long arms that slams with both fists. The body and its weapon are generated (art/gen/hulk/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

# an ape's build: arms to the knees, short legs, the head thrust forward under a crest of spikes. The fitter took
# an elbow's spike for the hand, set the hips at half the height and the head among the spikes; all read off
# tools/blender/views.py (art/gen/hulk/game.glb --stand 2.2 180 --focus 1.1 2.0, and 1.72 0.5 for the eyes)
JOINTS = {"hips": (0, -0.02, 1.0), "spine": (0, -0.03, 1.18), "chest": (0, 0.0, 1.36), "neck": (0, 0.06, 1.5),
          "skull": (0.008, 0.24, 1.6), "crown": (0.008, 0.3, 1.88)}
for s, side in ((1, "R"), (-1, "L")):
    JOINTS |= {f"shoulder.{side}": (s * 0.36, 0.0, 1.5), f"elbow.{side}": (s * 0.66, 0.12, 1.15),
               f"wrist.{side}": (s * 0.68, 0.2, 0.8), f"fingers.{side}": (s * 0.64, 0.25, 0.56),
               f"hip.{side}": (s * 0.21, 0.0, 0.97), f"knee.{side}": (s * 0.33, 0.04, 0.55)}

build(Spec("hulk", 2.2, walk="Heavyset", hunch=12, eyes=(1.0, 0.5, 0.1), arms=0.8, joints=JOINTS,
           eyes_at=((0.044, 1.699), (-0.031, 1.702))))
