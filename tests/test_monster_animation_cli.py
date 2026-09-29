"""A complete painted walk strip can be cut to an approved set of contact poses.

The guide, cut, and merge commands are one production workflow: its manifest and ground
pivot must survive all three steps, and painted registration must affect the actual cut.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from PIL import Image
from sagaforge import restyle

from hellward.art import figures

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "monster_animation.py"


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOL), *(str(arg) for arg in args)], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)


def test_full_walk_can_register_to_painted_contacts_and_merge(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = _run("guide", "skeleton", "walk-full", work, "--facings", "back_left")
    assert result.returncode == 0, result.stderr

    guide = work / "mon-skeleton-walk-full-guide"
    sheet = restyle.Sheet.load(guide)
    assert [cell.key for cell in sheet.cells] == [f"back_left/walk{i}" for i in range(1, 9)]
    approved = work / "approved-contacts"
    contacts: dict[str, Image.Image] = {}
    for cell in sheet.cells:
        image = Image.new("RGBA", sheet.cell)
        image.alpha_composite(figures.render("skeleton", "back_left", cell.tags["frame"]), (0, 9))
        contacts[cell.key] = image
    sheet.save(approved, contacts)

    rendered = restyle.file(guide, "png")
    result = _run("cut", "skeleton", "walk-full", work, rendered, "--unpadded")
    assert result.returncode == 0, result.stderr
    cut = work / "mon-skeleton-walk-full-cut"
    _, unregistered = restyle.load_frames(cut)

    result = _run("cut", "skeleton", "walk-full", work, rendered, "--unpadded", "--register-to", approved)
    assert result.returncode == 0, result.stderr
    cut_sheet, registered = restyle.load_frames(cut)
    assert (cut_sheet.cell, cut_sheet.origin, cut_sheet.scale) == (sheet.cell, sheet.origin, sheet.scale)
    before = unregistered["back_left/walk1"].getchannel("A").getbbox()
    after = registered["back_left/walk1"].getchannel("A").getbbox()
    assert before is not None and after is not None
    assert 7 <= after[3] - before[3] <= 11

    install = tmp_path / "painted"
    result = _run("merge", "skeleton", "walk-full", work, "--install", install)
    assert result.returncode == 0, result.stderr
    installed_sheet, installed = restyle.load_frames(install / "mon-skeleton-bearings")
    assert set(installed) == {f"back_left/walk{i}" for i in range(1, 9)}
    assert (installed_sheet.cell, installed_sheet.origin, installed_sheet.scale) == (sheet.cell, sheet.origin, sheet.scale)


def test_painted_registration_rejects_a_different_ground_pivot(tmp_path: Path) -> None:
    work = tmp_path / "work"
    result = _run("guide", "skeleton", "walk-full", work, "--facings", "back_left")
    assert result.returncode == 0, result.stderr
    guide = work / "mon-skeleton-walk-full-guide"
    sheet = restyle.Sheet.load(guide)
    bad_reference = work / "wrong-pivot"
    shifted_origin = replace(sheet, origin=(sheet.origin[0], sheet.origin[1] + 1))
    shifted_origin.save(bad_reference, {cell.key: figures.render("skeleton", "back_left", cell.tags["frame"])
                                        for cell in sheet.cells})

    result = _run("cut", "skeleton", "walk-full", work, restyle.file(guide, "png"),
                  "--unpadded", "--register-to", bad_reference)
    assert result.returncode != 0
    assert "registration reference metadata" in result.stderr
    assert not restyle.file(work / "mon-skeleton-walk-full-cut", "png").exists()
