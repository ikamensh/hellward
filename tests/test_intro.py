"""The intro's timeline (tools/intro.py): shots follow one another without gaps, every line is said while
its picture is on screen, and a line marked to run over a cut is split at its pause, so the next picture
arrives on the words it shows."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import intro  # noqa: E402


def take(*pieces: float) -> np.ndarray:
    """Alternating sound and silence, in seconds, as a stereo take."""
    parts = []
    for i, length in enumerate(pieces):
        t = np.arange(int(length * intro.RATE)) / intro.RATE
        parts.append(0.3 * np.sin(2 * np.pi * 180 * t) if i % 2 == 0 else np.zeros_like(t))
    mono = np.concatenate(parts).astype(np.float32)
    return np.stack([mono, mono], axis=1)


def test_timeline_tiles_the_shots_and_cuts_at_the_pause(tmp_path: Path) -> None:
    for shot in intro.SHOTS:
        if shot.line:   # a long pause in the middle of the line that runs over its cut, short ones elsewhere
            intro.write_wav(tmp_path / "voice" / f"{shot.key}-dry.wav",
                            take(1.5, 0.8, 1.2) if " / " in shot.line else take(0.6, 0.2, 0.7))
    plan = intro.timeline(tmp_path)
    shots, words = plan["shots"], plan["words"]

    for one, next_ in zip(shots, shots[1:]):
        assert abs(one["start"] + one["length"] - next_["start"]) < 0.01
    for shot, row in zip(intro.SHOTS, shots):
        assert row["length"] >= shot.least - 1e-6
    for one, next_ in zip(words, words[1:]):
        assert one["at"] + one["length"] <= next_["at"] + 0.01

    starts = {row["key"]: row["start"] for row in shots}
    split = next(i for i, shot in enumerate(intro.SHOTS) if " / " in shot.line)
    before, after = intro.SHOTS[split], intro.SHOTS[split + 1]
    first = next(i for i, w in enumerate(words) if w.get("voice") == before.key)
    rest = words[first + 1]
    assert rest["text"] == intro.plain(before.line).split(" / ")[1]
    assert abs(rest["at"] - starts[after.key]) < 0.01                  # the second half starts on the cut
    assert words[first]["at"] + words[first]["length"] < starts[after.key]   # the first half is over by then
