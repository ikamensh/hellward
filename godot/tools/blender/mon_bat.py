"""A Blood Bat: a giant crimson bat, wings spread, a flyer. The body is generated (art/gen/bat/, the concept from the 2D game's sheet:
art/concept/ref/); tools/blender/beast.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from beast import Beast, Flyer  # noqa: E402

Flyer(Beast("bat", 0.7, eyes=(1.0, 0.2, 0.12), beat=0.3)).finish()
