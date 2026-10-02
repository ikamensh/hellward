"""A Gargoyle: a winged stone demon, a flyer. The body is generated (art/gen/gargoyle/, the concept from the 2D game's sheet:
art/concept/ref/); tools/blender/beast.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from beast import Beast, Flyer  # noqa: E402

Flyer(Beast("gargoyle", 1.7, eyes=(0.5, 1.0, 0.5), beat=0.55, rough=0.85)).finish()
