"""The Drowned: a bloated waterlogged corpse from the harbour, dragging a leg, slamming with both claws. The body and its weapon are generated (art/gen/drowned/, the concept from the 2D
game's sheet: art/concept/ref/); tools/blender/biped.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from biped import Spec, Weapon, build  # noqa: E402

build(Spec("drowned", 1.9, walk="DragLeftLeg", idle="Zombie", hunch=6, eyes=(0.6, 0.75, 0.65), rough=0.55))
