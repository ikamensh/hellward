"""Record Hellward through the real renderer: the scripted defender against the smart leaders.

    uv run python tools/showcase.py OUT                        # find the leaders' curses, film around them
    uv run python tools/showcase.py OUT --at 95,420 --seconds 7
    uv run python tools/showcase.py OUT --moments               # only list the moments worth filming

Writes ``clip.mp4`` (full size, 30 fps), ``clip.gif`` (smaller, for chat) and a still from the middle of every
shot. The fight is the one ``uv run hellward --demo --seed N`` plays: the same seed, the same defender, and
leaders that decide exactly as the game's worker would. The display must be awake (``caffeinate -u``).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def moments(seed: int, limit: float = 900.0) -> list[tuple[float, str]]:
    """Game times worth filming: a leader starting to curse, a gate breaking, the boss arriving."""
    from hellward.sim import planner
    from hellward.sim.autoplay import Defender
    from hellward.sim.model import SIM_DT, World

    world = World(seed=seed, planner=planner.smart)
    defender = Defender()
    found = []
    while world.outcome is None and world.time < limit:
        defender.act(world, SIM_DT)
        world.step(SIM_DT)
        for e in world.events:
            if e[0] == "chant":
                found.append((world.time, f"chant {world.monster(e[1]).kind.key if world.monster(e[1]) else '?'} wave {world.wave + 1}"))
            elif e[0] == "door_broken":
                found.append((world.time, f"gate {e[1]} broken"))
            elif e[0] == "wave" and e[1] == len(world.waves) - 1:
                found.append((world.time, "the boss wave"))
            elif e[0] in ("victory", "defeat"):
                found.append((world.time, e[0]))
        world.events.clear()
    return found


class Recorder:
    """Stands between the sound bank and the game's audio: remembers what would play, and at which frame."""

    def __init__(self, audio) -> None:
        self.audio = audio
        self.frame = -1          # frames are only counted while filming
        self.sounds: list[tuple[int, str, float, float]] = []
        self.music: list[tuple[int, str]] = []
        self._play_sound, self._play_music = audio.play_sound, audio.play_music
        audio.play_sound, audio.play_music = self.play_sound, self.play_music

    def play_sound(self, name: str, *, volume: float = 1.0, pitch: float = 1.0) -> None:
        if self.frame >= 0:
            self.sounds.append((self.frame, name, volume, pitch))
        self._play_sound(name, volume=volume, pitch=pitch)

    def play_music(self, name: str, *, loop: bool = True, fade: float = 0.0) -> None:
        self.music.append((max(self.frame, 0), name))
        self._play_music(name, loop=loop, fade=fade)


def soundtrack(recorder: Recorder, cache: Path, frames: int, fps: int, path: Path) -> None:
    """Mix what the bank played into one stereo track: the music under, every cue at its frame."""
    import numpy as np

    from sagaforge.foley import read_wav
    from sagaforge.synth import write_wav

    rate = 44_100
    length = int(frames / fps * rate) + rate
    mix = np.zeros((length, 2), dtype=np.float64)
    tracks = recorder.music or [(0, "battle")]
    for i, (start, name) in enumerate(tracks):
        end = tracks[i + 1][0] if i + 1 < len(tracks) else frames
        clip = _stereo(read_wav(cache / "music" / f"{name}.wav"))
        a, b = int(start / fps * rate), int(end / fps * rate)
        reps = np.resize(clip, (b - a, 2)) if b > a else clip[:0]
        mix[a:b] += reps * 0.45
    for frame, name, volume, pitch in recorder.sounds:
        clip = _stereo(read_wav(cache / "sounds" / f"{name}.wav"))
        if pitch != 1.0:
            idx = np.arange(0, len(clip) - 1, pitch)
            clip = np.stack([np.interp(idx, np.arange(len(clip)), clip[:, c]) for c in range(2)], axis=1)
        a = int(frame / fps * rate)
        b = min(length, a + len(clip))
        mix[a:b] += clip[: b - a] * volume * 0.8
    peak = np.abs(mix).max()
    if peak > 0.95:
        mix *= 0.95 / peak
    write_wav(path, mix[: int(frames / fps * rate)].astype(np.float32))


def _stereo(clip):
    import numpy as np

    return np.stack([clip, clip], axis=1) if clip.ndim == 1 else clip


def film(out: Path, seed: int, shots: list[float], seconds: float, fps: int, lead: float) -> None:
    import os

    os.environ.setdefault("SAGA2D_SILENT", "1")
    from saga2d import Game

    from hellward.__main__ import build
    from hellward.audio.bank import SoundBank
    from hellward.sim import planner
    from hellward.sim.autoplay import Defender
    from hellward.ui.battle import BattleScene

    frames_dir = out / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    cache = Path.home() / ".hellward" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    game = Game("Hellward", resolution=(1280, 800), backend="pyglet", visible=False, asset_path=cache)
    art = build(game, cache)
    SoundBank.prepare(cache, wait=True)   # the music too, before filming starts
    recorder = Recorder(game.audio)
    bank = SoundBank(game, clock=lambda: recorder.frame / fps)   # the voice budget keeps the film's time, not the wall's
    scene = BattleScene(art, seed=seed, planner=planner.smart, autopilot=Defender(), sound=bank)
    game.push(scene)
    index = 0
    dt = 1 / fps
    for shot in sorted(shots):
        start = max(0.0, shot - lead)
        scene.speed = 4.0
        while scene.world.time < start and scene.world.outcome is None:
            game.tick(1 / 30)
        scene.speed = 1.0
        taken = 0
        while taken < seconds * fps:
            recorder.frame = index
            game.tick(dt)
            image = game.backend.capture_frame().convert("RGB").resize((1280, 800))
            image.save(frames_dir / f"{index:05d}.png")
            if taken == int(lead * fps):
                image.save(out / f"still-{int(shot):04d}.png")
            index += 1
            taken += 1
        recorder.frame = -1
    game.close()
    soundtrack(recorder, cache, index, fps, frames_dir / "sound.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames_dir / "%05d.png"),
                    "-i", str(frames_dir / "sound.wav"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                    "-c:a", "aac", "-b:a", "160k", "-shortest", str(out / "clip.mp4")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / "clip.mp4"), "-vf",
                    "fps=12,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=3",
                    str(out / "clip.gif")], check=True)
    shutil.rmtree(frames_dir)
    print(f"wrote {out / 'clip.mp4'}, {out / 'clip.gif'} and {len(shots)} stills")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--at", type=lambda s: [float(x) for x in s.split(",")], default=None, help="game times to film")
    parser.add_argument("--seconds", type=float, default=6.0)
    parser.add_argument("--lead", type=float, default=2.0, help="seconds filmed before each moment")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--moments", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    shots = args.at
    if shots is None or args.moments:
        found = moments(args.seed)
        for t, what in found:
            print(f"{t:7.1f}s  {what}")
        if args.moments:
            return
        chants = [t for t, what in found if what.startswith("chant")]
        picks = [chants[len(chants) // 4], chants[len(chants) // 2], chants[3 * len(chants) // 4]] if len(chants) >= 3 else chants
        boss = [t for t, what in found if what == "the boss wave"]
        shots = picks + [b + 30 for b in boss[:1]]
    film(args.out, args.seed, shots, args.seconds, args.fps, args.lead)


if __name__ == "__main__":
    main()
