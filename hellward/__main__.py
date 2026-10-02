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
CACHE = Path(".godot") / "global_script_class_cache.cfg"   # in the project; rewritten by every import (godot-capture.sh)


def godot() -> str:
    found = os.environ.get("GODOT") or (str(MAC_GODOT) if MAC_GODOT.exists() else shutil.which("godot"))
    if not found:
        raise SystemExit("hellward: Godot 4.7 is needed (set GODOT, or install it: brew install --cask godot)")
    return found


def stale(project: Path = PROJECT) -> bool:
    """Whether the client needs importing: a game only runs imported assets, and a new class_name script is unknown
    (its users fail to compile) until the editor rescans."""
    cache = project / CACHE
    if not cache.is_file():
        return True
    since = cache.stat().st_mtime
    # a folder's own time moves when a file in it is added or removed
    return any(path.stat().st_mtime > since for folder in ("scripts", "assets", "shaders")
               for path in [project / folder, *(project / folder).rglob("*")] if path.suffix != ".import")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if stale():
        print("hellward: importing the client's new and changed files first", flush=True)
        subprocess.run([godot(), "--headless", "--path", str(PROJECT), "--import"], check=True,
                       stdout=subprocess.DEVNULL)
        (PROJECT / CACHE).touch()   # an import that changed no class leaves it as it was
    return subprocess.call([godot(), "--path", str(PROJECT), *args])


if __name__ == "__main__":
    sys.exit(main())
