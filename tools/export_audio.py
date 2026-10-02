"""Render every sound cue and every music track into the Godot client, through Hellward's own audio code.

    uv run python tools/export_audio.py [--music]

Writes godot/game/assets/audio/<stem>.wav for every take of every cue (hellward/audio/cues.py), and with
``--music`` every track (hellward/audio/music.py: the title, a battle per location, the boss) as
music_<name>.mp3 (this ffmpeg has no Vorbis encoder). The client picks a take at random (scripts/sfx.gd).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from hellward.audio.cues import files
from hellward.audio.music import PIECES
from sagaforge.synth import write_wav

OUT = Path(__file__).resolve().parent.parent / "godot" / "game" / "assets" / "audio"


def mp3(wav: Path, out: Path) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame", "-q:a", "2", str(out)],
                   check=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for stem, render in files().items():
        write_wav(OUT / f"{stem}.wav", render())
        print(f"cue {stem}", flush=True)
    if "--music" in sys.argv:
        with tempfile.TemporaryDirectory() as tmp:
            for name, piece in PIECES.items():
                wav = Path(tmp) / f"{name}.wav"
                write_wav(wav, piece.render())
                mp3(wav, OUT / f"music_{name}.mp3")
                print(f"music {name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
