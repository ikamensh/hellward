"""Committed generated sound pieces: reading them and picking a take.

The WAVs under ``assets/pieces/`` are generated recordings (Stable Audio 3 Medium through
``sagaforge.foley``; ``manifest.json`` records each prompt, seed and hash, and ``tools/pieces.py``
remakes them).  :mod:`hellward.audio.cues` composes the game's cues from them by placing and
scaling takes; nothing here synthesises.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
import re

import numpy as np

from sagaforge.foley import mono, read_wav
from sagaforge.synth import level

ROOT = Path(__file__).resolve().parents[1] / "assets" / "pieces"


@cache
def paths(kind: str) -> tuple[Path, ...]:
    """The committed takes of *kind* (``door_hit``, ``fallen_cry``), in take order."""
    pattern = re.compile(rf"{re.escape(kind)}_(\d+)")
    found = sorted((int(m.group(1)), p) for p in ROOT.glob(f"{kind}_*.wav") if (m := pattern.fullmatch(p.stem)))
    if not found:
        raise FileNotFoundError(f"No {kind} pieces under {ROOT}; run tools/pieces.py refresh")
    return tuple(p for _, p in found)


def takes(kind: str) -> int:
    return len(paths(kind))


@cache
def _read(path: Path) -> np.ndarray:
    clip = mono(read_wav(path))
    clip.setflags(write=False)
    return clip


def take(kind: str, index: int, gain: float = 1.0) -> np.ndarray:
    """Take *index* of *kind* (wrapping round), levelled to peak *gain*."""
    options = paths(kind)
    return level(_read(options[index % len(options)]), gain)
