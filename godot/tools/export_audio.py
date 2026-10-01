"""Render the 2D game's sound cues and music for the 3D demo, through Hellward's own audio code.

    HELLWARD_INTERPRETED=1 uv run --project ../hellward python tools/export_audio.py

Writes game/assets/audio/<stem>.wav for every cue the demo plays (every take of each) and the
title and Tristram battle music as MP3 (this ffmpeg has no Vorbis encoder). The game picks a take at
random (game/scripts/sfx.gd).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from hellward.audio.cues import files
from hellward.audio.music import PIECES
from sagaforge.synth import write_wav

OUT = Path(__file__).resolve().parent.parent / "game" / "assets" / "audio"
CUES = ("arrow_cast", "arrow_hit", "fire_cast", "fire_hit", "fireball", "frost", "lightning", "ponder", "chant",
        "curse", "cleanse", "build", "sell", "upgrade", "gold", "wave", "cleared", "leak", "victory", "defeat",
        "click", "refuse", "death_fallen", "death_zombie", "death_shaman", "death_skeleton")
MUSIC = ("title", "battle_tristram")


def mp3(wav: Path, out: Path) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame", "-q:a", "2", str(out)],
                   check=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    stems = files()
    wanted = [s for s in stems if any(s == c or s.startswith(c + "_") and s[len(c) + 1:].isdigit() for c in CUES)]
    for stem in wanted:
        write_wav(OUT / f"{stem}.wav", stems[stem]())
        print(f"cue {stem}", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name in MUSIC:
            wav = Path(tmp) / f"{name}.wav"
            write_wav(wav, PIECES[name].render())
            mp3(wav, OUT / f"music_{name}.mp3")
            print(f"music {name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
