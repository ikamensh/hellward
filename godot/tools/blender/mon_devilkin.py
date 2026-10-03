"""The Devilkin: a lean ash-violet imp of the Fallen family with long swept horns, a bone necklace and a
jagged knife. Hand-modelled (art/concept/devilkin.png; no generated sculpt) on mon_carver.py's tier builder."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, build, h_ball, h_cone  # noqa: E402
from mon_carver import C, EYES_AT, LOOKS, build_imp, families_for  # noqa: E402


DEVILKIN = {n: C(*v) for n, v in {
    "hide": (0.38, 0.30, 0.44), "leather": (0.16, 0.12, 0.12), "horn": (0.16, 0.14, 0.16),
    "dark": (0.08, 0.07, 0.09), "steel": (0.50, 0.53, 0.60), "iron": (0.25, 0.24, 0.28),
    "eye": (0.65, 0.35, 1.0), "bone": (0.80, 0.76, 0.66)}.items()}
DEVILKIN_HORNS = [((0.030, 0.005, 1.075), (0.055, -0.075, 1.175), 0.014)]


def beads(parts, add, P):
    """A necklace of bone beads and a fang on the chest (half-sunk: worn, not floating)."""
    for i, x in enumerate((-0.04, 0.0, 0.04)):
        add(h_ball(f"bead.{i}", (x, 0.062, 0.78), 0.011), "bone")
    add(h_cone("fang", (0, 0.060, 0.762), (0, 0.064, 0.730), 0.009), "bone")


def make_devilkin():
    return build_imp("devilkin", 1.18, DEVILKIN, DEVILKIN_HORNS, extras=beads, bulk=0.9)


build(Spec("devilkin", 1.18, hand=make_devilkin, eyes=(0.6, 0.3, 1.0), eyes_at=EYES_AT, eyes_find="fixed",
           families=families_for(DEVILKIN), looks=LOOKS,
           keyed={"k": 1.085, "stride": 0.16, "walk_s": 0.7, "idle_s": 3.0, "crouch": 0.1}))
