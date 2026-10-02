"""Save files: one JSON envelope per slot in the save folder, the previous one kept as a backup.

The envelope is the one the 2D game wrote through Saga2D, so its saves load as they are::

    {"version": 1, "timestamp": ISO time, "scene_class": "Progress", "summary": {...}, "state": {...}}

A slot ``campaign`` is ``save_campaign.json``; a successful write first keeps the file it replaces as
``save_campaign.backup.json``. A damaged file is an error, never silently replaced.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SaveError(Exception):
    """A save cannot be read or written, or its envelope is not one this game wrote."""


class Saves:
    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)

    def path(self, slot: str) -> Path:
        if not slot.isidentifier():
            raise ValueError(f"a save slot is a simple word, not {slot!r}")
        return self.folder / f"save_{slot}.json"

    def load(self, slot: str) -> dict[str, Any] | None:
        """The slot's envelope, or None when it was never saved."""
        path = self.path(slot)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except ValueError as bad:
            raise SaveError(f"cannot read {path}: {bad}") from bad
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("state"), dict):
            raise SaveError(f"{path} is not a version 1 save")
        return data

    def save(self, slot: str, state: dict[str, Any], kind: str, summary: dict[str, Any]) -> None:
        path = self.path(slot)
        previous = self.load(slot)
        text = json.dumps({"version": 1, "timestamp": datetime.now(tz=timezone.utc).isoformat(), "scene_class": kind,
                           "summary": summary, "state": state}, indent=2, allow_nan=False)
        self.folder.mkdir(parents=True, exist_ok=True)
        if previous is not None:
            _replace(path.with_suffix(".backup.json"), json.dumps(previous, indent=2, allow_nan=False))
        _replace(path, text)

    def slots(self, prefix: str) -> list[str]:
        """The names of the saved slots that start with ``prefix``."""
        return [p.name[len("save_"):-len(".json")] for p in sorted(self.folder.glob(f"save_{prefix}*.json"))
                if not p.name.endswith(".backup.json")]


def _replace(path: Path, text: str) -> None:
    """Write beside the file, sync, then swap it in: a crash leaves the old file or the new, never half of one."""
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(text.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)
