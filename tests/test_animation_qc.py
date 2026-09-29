"""The animation art gate checks motion and anatomy against posed guides."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from tools.animation_qc import audit


CELL = (128, 128)
ORIGIN = (64, 90)
TOOL = Path(__file__).resolve().parents[1] / "tools" / "animation_qc.py"


def _figure(*, offset: int = 0, height: int = 0, raised_weapon: bool = False,
            broad_body: bool = False, spread_arms: bool = False) -> Image.Image:
    image = Image.new("RGBA", CELL)
    draw = ImageDraw.Draw(image)
    draw.ellipse((56 + offset, 30 - height, 72 + offset, 46 - height), fill="white")
    torso_left, torso_right = (49, 79) if broad_body else (55, 73)
    draw.rectangle((torso_left + offset, 46 - height, torso_right + offset, 76), fill="white")
    draw.line((60 + offset, 76, 60, 90), fill="white", width=5)
    draw.line((68 + offset, 76, 68, 90), fill="white", width=5)
    if raised_weapon:
        draw.line((72 + offset, 58, 91 + offset, 10), fill="white", width=3)
    if spread_arms:
        draw.line((55 + offset, 56, 30 + offset, 42), fill="white", width=4)
        draw.line((73 + offset, 56, 98 + offset, 42), fill="white", width=4)
    return image


def _frames() -> dict[str, Image.Image]:
    return {f"front/walk{i}": _figure() for i in range(1, 9)} | {
        f"front/hit{i}": _figure(raised_weapon=True) for i in range(1, 4)
    } | {
        "front/death1": _figure()
    }


def test_guide_matching_animation_passes_even_when_hit_weapon_extends() -> None:
    """An intended raised weapon changes the silhouette without changing body scale."""
    frames = _frames()
    assert audit("skeleton", frames, frames, CELL, ORIGIN) == []


def test_guide_authored_side_to_side_motion_is_not_a_registration_error() -> None:
    """The gate compares art to the intended gait instead of banning all torso sway."""
    frames = _frames() | {f"front/walk{i}": _figure(offset=8) for i in (2, 4, 6, 8)}
    assert audit("skeleton", frames, frames, CELL, ORIGIN) == []


def test_separately_painted_even_walk_frames_report_upper_body_vibration() -> None:
    """An alternating head position is a real loop defect when the guide stays still."""
    guide = _frames()
    painted = guide | {f"front/walk{i}": _figure(offset=8) for i in (2, 4, 6, 8)}
    issues = audit("skeleton", painted, guide, CELL, ORIGIN)
    assert any("skeleton/front walk" in str(issue) and "parity" in str(issue) for issue in issues), issues
    assert any(issue.severity == "error" for issue in issues)


def test_hit_with_enlarged_body_reports_scale_mismatch() -> None:
    """A raised weapon is permitted, but enlarging the painted body alone is not."""
    guide = _frames()
    painted = guide | {"front/hit1": _figure(height=24, raised_weapon=True)}
    issues = audit("skeleton", painted, guide, CELL, ORIGIN)
    assert any("skeleton/front/hit1" in str(issue) and "body scale" in str(issue) for issue in issues), issues
    assert all(issue.severity == "review" for issue in issues)


def test_single_displaced_walk_frame_reports_transition_jolt() -> None:
    """One bad frame must fail even when the four-frame parity median hides it."""
    guide = _frames()
    painted = guide | {"front/walk4": _figure(offset=12)}
    issues = audit("skeleton", painted, guide, CELL, ORIGIN)
    assert any("skeleton/front walk4→walk5" in str(issue) and "jolt" in str(issue) for issue in issues), issues
    assert all(issue.severity == "review" for issue in issues)


def test_death_entry_reports_broad_body_mass_growth_for_review_only() -> None:
    """A noticeably bulkier first death pose needs an artist's identity check."""
    guide = _frames()
    painted = guide | {"front/death1": _figure(broad_body=True)}
    issues = audit("zombie", painted, guide, CELL, ORIGIN)
    death = [issue for issue in issues if "death entry" in issue.message]
    assert len(death) == 1, issues
    assert death[0].severity == "review"
    assert "width" in death[0].message and "area" in death[0].message
    assert "area 1.39×" in death[0].message  # the width+area branch, below the area-only limit


def test_death_entry_reports_opaque_mass_growth_without_width_growth() -> None:
    """A much denser death torso needs review even when its width stays stable."""
    guide = _frames()
    painted = guide | {"front/death1": _figure(height=30)}
    issues = audit("fallen", painted, guide, CELL, ORIGIN)
    death = [issue for issue in issues if "death entry" in issue.message]
    assert len(death) == 1, issues
    assert death[0].severity == "review"
    assert "width 1.00×" in death[0].message  # the area-only branch


def test_death_entry_ignores_thin_raised_weapon() -> None:
    """A weapon can extend a silhouette without increasing body mass."""
    guide = _frames()
    painted = guide | {"front/death1": _figure(raised_weapon=True)}
    issues = audit("skeleton", painted, guide, CELL, ORIGIN)
    assert not any("death entry" in issue.message for issue in issues), issues


def test_death_entry_ignores_spread_arms_authored_in_guide() -> None:
    """Guide matching death poses can intentionally open the silhouette."""
    guide = _frames() | {"front/death1": _figure(spread_arms=True)}
    issues = audit("fallen", guide, guide, CELL, ORIGIN)
    assert not any("death entry" in issue.message for issue in issues), issues


def test_art_gate_command_is_executable() -> None:
    """Artists can invoke the gate before accepting a revised sheet."""
    result = subprocess.run([sys.executable, str(TOOL), "--help"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "painted monster animation" in result.stdout


def test_installed_first_three_monsters_clear_the_animation_gate() -> None:
    """The production paintings, including walk loops and hit entries, stay coherent."""
    result = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
