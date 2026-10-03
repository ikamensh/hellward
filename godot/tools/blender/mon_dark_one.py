"""The Dark One: a broad near-black imp of the Fallen family with great curling horns, a spiked collar,
iron bracers and a dark blade. Hand-modelled (art/concept/dark_one.png; no generated sculpt) on
mon_carver.py's tier builder."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, build, h_cone, h_limb  # noqa: E402
from mon_carver import C, EYES_AT, LOOKS, build_imp, families_for  # noqa: E402


DARK_ONE = {n: C(*v) for n, v in {
    "hide": (0.15, 0.09, 0.09), "leather": (0.12, 0.09, 0.08), "horn": (0.09, 0.08, 0.09),
    "dark": (0.07, 0.06, 0.07), "steel": (0.45, 0.46, 0.50), "iron": (0.30, 0.29, 0.30),
    "eye": (1.0, 0.15, 0.12)}.items()}
DARK_ONE_HORNS = [((0.035, 0.005, 1.07), (0.075, -0.01, 1.13), 0.020),
                  ((0.075, -0.01, 1.125), (0.06, -0.045, 1.18), 0.013)]


def collar(parts, add, P):
    """A spiked iron collar round the neck."""
    add(h_limb("collar", (0, 0.005, 0.885), (0, 0.01, 0.935), 0.068, 0.062), "iron")
    for i, (base, tip) in enumerate((((0.062, 0.008, 0.91), (0.10, 0.008, 0.925)),
                                     ((-0.062, 0.008, 0.91), (-0.10, 0.008, 0.925)),
                                     ((0, 0.070, 0.91), (0, 0.105, 0.92)))):
        add(h_cone(f"collar.spike.{i}", base, tip, 0.012), "iron")


def make_dark_one():
    return build_imp("dark_one", 1.18, DARK_ONE, DARK_ONE_HORNS, extras=collar, bulk=1.12, iron_wraps=True)


build(Spec("dark_one", 1.18, hand=make_dark_one, eyes=(1.0, 0.12, 0.1), eyes_at=EYES_AT, eyes_find="fixed",
           families=families_for(DARK_ONE), looks=LOOKS,
           keyed={"k": 1.085, "stride": 0.16, "walk_s": 0.7, "idle_s": 3.0, "crouch": 0.1}))
