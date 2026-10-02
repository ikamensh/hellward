"""A Flayer: a small masked jungle hunter with a spear, in packs. The body and its weapon are generated
(art/gen/flayer/, the concept from the 2D game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and
animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

# its mask and crest are the top two fifths of it, as the Fetish's: the upper body's joints and the eyes are read off
# tools/blender/views.py (--focus 0.5 0.6)
JOINTS = {"hips": (0, 0.0, 0.4), "spine": (0, 0.0, 0.46), "chest": (0, 0.0, 0.52), "neck": (0, 0.0, 0.58),
          "skull": (0, 0.02, 0.62), "hip.R": (0.055, 0.0, 0.38), "hip.L": (-0.055, 0.0, 0.38),
          "knee.R": (0.095, 0.0, 0.22), "knee.L": (-0.09, 0.0, 0.22)}
for s, side in ((1, "R"), (-1, "L")):
    JOINTS |= {f"shoulder.{side}": (s * 0.08, 0.0, 0.572), f"elbow.{side}": (s * 0.14, 0.02, 0.482),
               f"wrist.{side}": (s * 0.183, 0.04, 0.415), f"fingers.{side}": (s * 0.22, 0.06, 0.345)}

build(Spec("flayer", 0.9, walk="OnToesCrouched", eyes=(1.0, 0.75, 0.2), eyes_at=(0.03, 0.7), joints=JOINTS,
           weapon=Weapon("spear", 1.1, grip=0.3, attack="thrust", metal=None)))
