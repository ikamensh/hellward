"""A Fetish Shaman: a tiny masked jungle leader that curses towers and raises flayers, its spear held as a staff.
The body and its weapon are generated (art/gen/fetish/, the concept from the 2D game's sheet: art/concept/ref/);
tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

# its mask and feather crown are the top two fifths of it: the fitter takes the crown's sides for shoulders and
# the feathers for eyes, so the upper body's joints and the eyes are read off tools/blender/views.py (--focus 0.45 0.6;
# the eyes off art/gen/fetish/game.glb --stand 1.0 180 --focus 0.72 0.18: empty sockets, lit in their dark)
JOINTS = {"hips": (0, 0.0, 0.39), "spine": (0, 0.0, 0.46), "chest": (0, 0.01, 0.53), "neck": (0, -0.01, 0.6),
          "skull": (0, 0.0, 0.66), "hip.R": (0.055, 0.0, 0.37), "hip.L": (-0.055, 0.0, 0.37),
          "knee.R": (0.098, 0.0, 0.2), "knee.L": (-0.11, 0.01, 0.2)}
for s, side in ((1, "R"), (-1, "L")):
    JOINTS |= {f"shoulder.{side}": (s * 0.1, -0.02, 0.572), f"elbow.{side}": (s * 0.15, -0.04, 0.48),
               f"wrist.{side}": (s * 0.19, -0.035, 0.432), f"fingers.{side}": (s * 0.23, 0.0, 0.348)}
# read off with the body stood 1.0 m tall; built at the rules' size (size x 2.3 m), which its legs need to keep up
SCALE = 1.38 / 1.0
JOINTS = {name: tuple(SCALE * c for c in at) for name, at in JOINTS.items()}

build(Spec("fetish", 1.38, walk="OnToesCrouched", run=True, eyes=(1.0, 0.75, 0.2),
           eyes_at=tuple((SCALE * x, SCALE * z) for x, z in ((0.026, 0.728), (-0.021, 0.728))),
           eyes_find="dark", joints=JOINTS,
           leader=True, weapon=Weapon("spear", 1.65, grip=0.3, staff=True, metal=None)))
