"""The arrow tower, rank 2 (tower_arrow.py builds it)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tower_arrow import build  # noqa: E402

build(2)
