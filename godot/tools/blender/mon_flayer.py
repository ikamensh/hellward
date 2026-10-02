"""A Flayer: a small masked jungle hunter with a spear, in packs. The body and its weapon are generated
(art/gen/flayer/, the concept from the 2D game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and
animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

# its mask and crest are the top two fifths of it, as the Fetish's: the upper body's joints and the eyes are read off
# tools/blender/views.py (--focus 0.5 0.6; the eyes off art/gen/flayer/game.glb --stand 0.9 180 --focus 0.68 0.16)
JOINTS = {"hips": (0, 0.0, 0.4), "spine": (0, 0.0, 0.46), "chest": (0, 0.0, 0.52), "neck": (0, 0.0, 0.58),
          "skull": (0, 0.02, 0.62), "hip.R": (0.055, 0.0, 0.38), "hip.L": (-0.055, 0.0, 0.38),
          "knee.R": (0.095, 0.0, 0.22), "knee.L": (-0.09, 0.0, 0.22)}
for s, side in ((1, "R"), (-1, "L")):
    JOINTS |= {f"shoulder.{side}": (s * 0.08, 0.0, 0.572), f"elbow.{side}": (s * 0.14, 0.02, 0.482),
               f"wrist.{side}": (s * 0.183, 0.04, 0.415), f"fingers.{side}": (s * 0.22, 0.06, 0.345)}
# read off with the body stood 0.9 m tall; built at the rules' size (size x 2.3 m), which its legs need to keep up
SCALE = 1.15 / 0.9
JOINTS = {name: tuple(SCALE * c for c in at) for name, at in JOINTS.items()}

# on its toes through the run, its peel outlasts the default lock: the toe stays a pivot 2 cm up
build(Spec("flayer", 1.15, walk="OnToesCrouched", run=True, eyes=(1.0, 0.75, 0.2),
           eyes_at=tuple((SCALE * x, SCALE * z) for x, z in ((0.016, 0.663), (-0.041, 0.663))), joints=JOINTS,
           touch=0.02, weapon=Weapon("spear", 1.4, grip=0.3, attack="thrust", metal=None)))
