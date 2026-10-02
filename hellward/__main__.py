"""``uv run hellward``: play, in the Godot client (``godot/game``), which starts the server itself.

Godot is found as ``$GODOT``, else ``/Applications/Godot.app/Contents/MacOS/Godot``, else ``godot`` on the PATH.
Arguments after ``--`` go to the client (e.g. ``-- screen=map``, ``-- demo film``).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent / "godot" / "game"
MAC_GODOT = Path("/Applications/Godot.app/Contents/MacOS/Godot")


def godot() -> str:
    found = os.environ.get("GODOT") or (str(MAC_GODOT) if MAC_GODOT.exists() else shutil.which("godot"))
    if not found:
        raise SystemExit("hellward: Godot 4.7 is needed (set GODOT, or install it: brew install --cask godot)")
    return found


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    return subprocess.call([godot(), "--path", str(PROJECT), *args])


if __name__ == "__main__":
    sys.exit(main())
