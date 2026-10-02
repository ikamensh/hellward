"""tools/visual_check.py's frame checks: what they catch and what they pass."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import visual_check  # noqa: E402


def frame(tmp_path: Path, pixels: np.ndarray) -> Path:
    path = tmp_path / "f.png"
    Image.fromarray(pixels.astype(np.uint8)).save(path)
    return path


def test_a_lit_scene_passes(tmp_path):
    rng = np.random.default_rng(1)
    assert visual_check.checks(frame(tmp_path, rng.integers(20, 200, (90, 160, 3)))) == []


def test_blank_black_and_missing_texture_frames_fail(tmp_path):
    assert any("blank" in p for p in visual_check.checks(frame(tmp_path, np.full((90, 160, 3), 120))))
    assert any("black" in p for p in visual_check.checks(frame(tmp_path, np.zeros((90, 160, 3)))))
    rng = np.random.default_rng(2)
    img = rng.integers(20, 200, (90, 160, 3))
    img[10:30, 10:40] = (255, 0, 255)
    assert any("magenta" in p for p in visual_check.checks(frame(tmp_path, img)))
    assert visual_check.checks(tmp_path / "missing.png") == ["no frame was saved"]
