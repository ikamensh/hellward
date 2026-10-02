"""``uv run hellward`` imports the client before playing whenever a file changed since the last import: after a
pull brought a new class_name script, the game's scripts failed to compile and the window stayed blank."""

from __future__ import annotations

import os
from pathlib import Path

from hellward.__main__ import CACHE, PROJECT, stale


def _write(path: Path, when: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    for touched in (path, path.parent):   # as if both were written at that time
        os.utime(touched, (when, when))


def test_a_file_changed_since_the_last_import_needs_importing(tmp_path):
    record = tmp_path / "assets" / "tower_arrow_1.glb.import"
    _write(record, 100)
    _write(tmp_path / "shaders" / "ring.gdshader", 100)
    _write(tmp_path / "scripts" / "game.gd", 100)
    assert stale(tmp_path), "never imported"
    _write(tmp_path / CACHE, 200)
    assert not stale(tmp_path)
    os.utime(record, (300, 300))
    assert not stale(tmp_path), "Godot rewriting its own import record"
    _write(tmp_path / "scripts" / "flinch.gd", 400)
    assert stale(tmp_path), "a new script"
    _write(tmp_path / CACHE, 500)
    _write(tmp_path / "shaders" / "ring.gdshader", 600)
    assert stale(tmp_path), "a changed shader"
    _write(tmp_path / CACHE, 700)
    (tmp_path / "scripts" / "flinch.gd").unlink()
    assert stale(tmp_path), "a removed script"


def test_the_launcher_watches_the_real_client():
    assert (PROJECT / "project.godot").is_file()
    assert all((PROJECT / folder).is_dir() for folder in ("scripts", "assets", "shaders"))
