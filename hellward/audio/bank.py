"""The sound bank: renders Hellward's cues and music into a cache the game's assets point at, and plays them.

::

    SoundBank.prepare(cache_dir)                 # effects now (a second or two), music in a background thread
    game = Game("Hellward", asset_path=cache_dir)
    bank = SoundBank(game)
    bank.play("door_hit")                        # a take, never the last one, a touch of pitch; within the voice budget
    bank.music("battle_cathedral")               # crossfades as soon as the track is composed

Every cue name is in :data:`hellward.audio.cues.CUES`, every track in :data:`hellward.audio.music.PIECES`.
A location's battle track is :func:`hellward.audio.music.track_for` of its key.
A new :data:`VERSION` discards the whole cache; bump it after changing a cue, a piece or the music.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import math
import os
from pathlib import Path
import random
import threading
import time
from typing import ClassVar

from hellward.audio.cues import CUES, files
from hellward.audio.music import BATTLE_FOR, PIECES
from saga2d import Game
from sagaforge.synth import write_wav

VERSION = "4"
SOUNDS, MUSIC = "sounds", "music"
#: The composer's order: the title plays first, then the dungeons in the campaign's order, the boss last.
COMPOSE_ORDER = ("title",) + tuple(BATTLE_FOR.values()) + ("boss",)
#: Seconds each track takes to fade in over whatever was playing.
FADE_IN = {"title": 2.5, "boss": 1.5, **{name: 2.0 for name in BATTLE_FOR.values()}}
#: The voice budget for ``battle`` cues: at most BURST in BURST_WINDOW seconds and CROWD in CROWD_WINDOW,
#: and the same cue not again within REPEAT_GAP.  A cue that ``yields`` stops short of the limits, so a
#: volley of casts cannot crowd out a death.  Interface cues, alerts and leaders always play.
BURST, BURST_WINDOW = 4, 0.12
CROWD, CROWD_WINDOW = 8, 0.5
REPEAT_GAP = 0.08


class SoundBank:
    """Plays cues by name and music by mood through ``game.audio``, from the cache under the game's asset path."""

    _composers: ClassVar[dict[Path, threading.Thread]] = {}
    _failures: ClassVar[dict[Path, BaseException]] = {}

    @classmethod
    def prepare(cls, cache_dir: Path | str, *, wait: bool = False) -> None:
        """Render every cue under ``cache_dir/sounds`` now and start composing the music under
        ``cache_dir/music`` in a background thread; *wait* blocks until it is done.  Only what is
        missing is rendered, and everything when :data:`VERSION` changed."""
        cache_dir = Path(cache_dir).expanduser().resolve()
        sounds = cache_dir / SOUNDS
        marker = sounds / "VERSION"
        if not (marker.exists() and marker.read_text() == VERSION):
            for folder in (SOUNDS, MUSIC):
                for stale in (cache_dir / folder).glob("*.wav"):
                    stale.unlink()
        for stem, render in files().items():
            path = sounds / f"{stem}.wav"
            if not path.exists():
                write_wav(path, render())
        marker.write_text(VERSION)
        pending = [name for name in COMPOSE_ORDER if not _track(cache_dir, name).exists()]
        running = cls._composers.get(cache_dir)
        if pending and (running is None or not running.is_alive()):
            cls._failures.pop(cache_dir, None)
            running = threading.Thread(target=cls._compose, args=(cache_dir, pending), name="hellward-music", daemon=True)
            cls._composers[cache_dir] = running
            running.start()
        if wait and running is not None:
            running.join()
            cls._raise(cache_dir)

    @classmethod
    def _compose(cls, cache_dir: Path, names: list[str]) -> None:
        try:
            for name in names:
                path = _track(cache_dir, name)
                partial = path.with_name(f"{name}.partial.wav")
                write_wav(partial, PIECES[name].render())
                os.replace(partial, path)  # a track is whole or absent
        except BaseException as exc:  # raised on the game thread by _raise
            cls._failures[cache_dir] = exc

    @classmethod
    def _raise(cls, cache_dir: Path) -> None:
        failure = cls._failures.pop(cache_dir, None)
        if failure is not None:
            raise RuntimeError("Composing Hellward's music failed in the background") from failure

    def __init__(self, game: Game, *, clock: Callable[[], float] = time.monotonic, seed: int | None = None) -> None:
        self.cache_dir = game.assets.base_path.expanduser().resolve()
        marker = self.cache_dir / SOUNDS / "VERSION"
        if not (marker.exists() and marker.read_text() == VERSION):
            raise RuntimeError(f"No version {VERSION} sounds under {self.cache_dir}: call SoundBank.prepare(asset_path) before the bank")
        self._audio = game.audio
        self._clock = clock
        self._rng = random.Random(seed)
        self._last_take: dict[str, int] = {}
        self._last_played: dict[str, float] = {}
        self._voices: deque[float] = deque()
        self._wanted: str | None = None
        game.every(0.25, self.poll)

    # -- Effects -----------------------------------------------------------------------------

    def play(self, cue: str, *, volume: float = 1.0, x: float | None = None) -> bool:
        """Play *cue*; ``False`` when the voice budget dropped it.  *x* (the world x in tiles) is taken for
        the day saga2d pans effects; it changes nothing yet."""
        spec = CUES.get(cue)
        if spec is None:
            raise KeyError(f"Unknown cue {cue!r}. Cues: {', '.join(CUES)}")
        now = self._clock()
        if spec.kind == "battle":
            if now - self._last_played.get(cue, -math.inf) < REPEAT_GAP:
                return False
            while self._voices and now - self._voices[0] >= CROWD_WINDOW:
                self._voices.popleft()
            burst = sum(now - t < BURST_WINDOW for t in self._voices)
            if len(self._voices) + spec.yields >= CROWD or burst + spec.yields >= BURST:
                return False
            self._voices.append(now)
        self._last_played[cue] = now
        stem = cue
        if spec.takes > 1:
            take = self._rng.choice([t for t in range(spec.takes) if t != self._last_take.get(cue)])
            self._last_take[cue] = take
            stem = f"{cue}_{take}"
        pitch = 1.0 + self._rng.uniform(-spec.pitch, spec.pitch) if spec.pitch else 1.0
        self._audio.play_sound(stem, volume=volume, pitch=pitch)
        return True

    # -- Music -------------------------------------------------------------------------------

    def ready(self, name: str) -> bool:
        """Whether track *name* is composed and on disk."""
        if name not in PIECES:
            raise KeyError(f"Unknown track {name!r}. Tracks: {', '.join(PIECES)}")
        return _track(self.cache_dir, name).exists()

    def music(self, mood: str) -> None:
        """Crossfade to *mood*'s track (``title``, a ``battle_<location>``, ``boss``) now, or the moment it is composed."""
        if mood not in PIECES:
            raise KeyError(f"Unknown track {mood!r}. Tracks: {', '.join(PIECES)}")
        self._wanted = None if self._audio.music_name == mood else mood
        self.poll()

    def stop_music(self, fade: float = 1.0) -> None:
        self._wanted = None
        self._audio.stop_music(fade=fade)

    def poll(self) -> None:
        """Start the wanted track once it is ready; the game calls this four times a second."""
        self._raise(self.cache_dir)
        if self._wanted is None:
            return
        if not self.ready(self._wanted):
            composer = self._composers.get(self.cache_dir)
            if composer is not None and composer.is_alive():
                return
            self._raise(self.cache_dir)
            if not self.ready(self._wanted):  # the composer may have finished it since the first look
                raise RuntimeError(f"Track {self._wanted!r} is not under {self.cache_dir} and nothing is composing it: call SoundBank.prepare")
        mood, self._wanted = self._wanted, None
        self._audio.play_music(mood, fade=FADE_IN[mood] if self._audio.music_name else 1.0)


def _track(cache_dir: Path, name: str) -> Path:
    return cache_dir / MUSIC / f"{name}.wav"
