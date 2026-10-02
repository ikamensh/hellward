"""A giant black spider with a blood-red hourglass, scuttling on eight legs. The body is generated (art/gen/spider/, the concept from the 2D game's sheet:
art/concept/ref/); tools/blender/beast.py fits, rigs and animates it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from beast import Beast, Spider  # noqa: E402

Spider(Beast("spider", 0.75, eyes=(1.0, 0.15, 0.1))).finish()
