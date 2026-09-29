"""Bake both animated 3D rigs into the RGBA sprite atlases used by Hellward.

    uv run python tools/bake_rigged_monsters.py

The game loads the finished PNG/JSON assets. It does not generate them on
launch. Run this after changing the Skeleton or Zombie rig or its poses.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.art import rigged  # noqa: E402


def main() -> None:
    for kind in rigged.KINDS:
        stem = rigged.bake(kind)
        print(f"baked {kind}: {len(rigged.sheet(kind).cells)} fixed-pivot RGBA frames in {stem}.png")


if __name__ == "__main__":
    main()
