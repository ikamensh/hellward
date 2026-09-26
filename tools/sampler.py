"""Write Hellward's cues back to back into one file to listen to, and optionally the music.

    uv run python tools/sampler.py DIR            # DIR/cues.wav and DIR/cues.txt (when each cue starts)
    uv run python tools/sampler.py DIR --music    # also one WAV per track (title, battle_<location>, boss)

Every take of every cue, in the order of :data:`hellward.audio.cues.CUES`, 0.5 s apart; the
label list says where each starts.  The music is the same render the game caches.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hellward.audio.cues import files  # noqa: E402
from hellward.audio.music import PIECES  # noqa: E402
from sagaforge.synth import SAMPLE_RATE, mix, write_wav  # noqa: E402

GAP = 0.5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("--music", action="store_true", help="also render every track")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    layers, labels, cursor = [], [], 0.25
    for stem, render in files().items():
        clip = render()
        layers.append((cursor, clip))
        labels.append(f"{cursor:7.2f}s  {stem}\n")
        cursor += len(clip) / SAMPLE_RATE + GAP
    write_wav(args.out / "cues.wav", mix(*layers, (cursor, np.zeros((SAMPLE_RATE // 4, 2)))))
    (args.out / "cues.txt").write_text("".join(labels))
    print(f"{len(labels)} cues, {cursor:.0f} s: {args.out / 'cues.wav'}")
    if args.music:
        for name, piece in PIECES.items():
            write_wav(args.out / f"{name}.wav", piece.render())
            print(f"{name}: {piece.seconds:.0f} s loop")


if __name__ == "__main__":
    main()
