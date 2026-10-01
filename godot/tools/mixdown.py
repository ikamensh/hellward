"""Mix a recording's soundtrack from the cues the game logged while it recorded (game/scripts/sfx.gd).

    uv run python tools/mixdown.py DIR FRAMES OUT.wav     # DIR/sound.log: "frame stem gain_db pan" lines

Every cue is placed at frame / 30 s with its gain and a constant-power pan. Music lines ("frame music_NAME gain
fade", or music_stop) follow the game's rule: a new track starts at once and loops, and the one before it fades
out over `fade` seconds. The mix is brought to -18 dBFS RMS with soft-limited peaks.
tools/record.sh runs this and muxes the result into the video.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

AUDIO = Path(__file__).resolve().parent.parent / "game" / "assets" / "audio"
RATE = 44100
FPS = 30


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getsampwidth() == 2 and w.getframerate() == RATE, path
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        return data.reshape(-1, w.getnchannels()).mean(axis=1) if w.getnchannels() > 1 else data


def read_mp3(path: Path) -> np.ndarray:
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "m.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(path), "-ac", "2", "-ar", str(RATE), str(wav)],
                       check=True)
        with wave.open(str(wav)) as w:
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
            return data.reshape(-1, 2)


def main() -> int:
    folder, frames, out = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    length = int(frames / FPS * RATE) + RATE
    mix = np.zeros((length, 2), dtype=np.float32)
    cache: dict[str, np.ndarray] = {}
    tracks: list[list] = []   # [start, stop or None, fade samples, music, amp]
    for line in (folder / "sound.log").read_text().splitlines():
        frame, stem, gain, last = line.split()
        start = int(int(frame) / FPS * RATE)
        amp = 10 ** (float(gain) / 20)
        if stem.startswith("music_"):
            if tracks and tracks[-1][1] is None:
                tracks[-1][1], tracks[-1][2] = start, max(1, int(float(last) * RATE))
            if stem != "music_stop":
                tracks.append([start, None, 0, read_mp3(AUDIO / f"{stem}.mp3"), amp])
            continue
        if stem not in cache:
            cache[stem] = read_wav(AUDIO / f"{stem}.wav")
        clip = cache[stem][: length - start] * amp
        angle = (float(last) + 1) * np.pi / 4
        mix[start:start + len(clip), 0] += clip * np.cos(angle)
        mix[start:start + len(clip), 1] += clip * np.sin(angle)
    for start, stop, fade, track, amp in tracks:
        end = length if stop is None else min(length, stop + fade)
        reps = (end - start) // len(track) + 1
        part = np.tile(track, (reps, 1))[: end - start] * amp
        if stop is not None:
            ramp = np.ones(end - start, dtype=np.float32)
            ramp[stop - start:] = np.linspace(1.0, 0.0, end - stop, dtype=np.float32)
            part *= ramp[:, None]
        mix[start:end] += part
    # to a listening level: -18 dBFS RMS, the peaks soft-limited
    rms = float(np.sqrt(np.mean(mix ** 2)))
    if rms > 0:
        mix *= 10 ** (-18 / 20) / rms
    mix = np.tanh(mix)
    peak = float(np.abs(mix).max())
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print(f"{out}: {len(mix) / RATE:.1f} s, peak {peak:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
