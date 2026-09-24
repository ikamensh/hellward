"""Hellward's music: three loops for a town under a cathedral, composed with
:mod:`hellward.audio.instruments` on :mod:`sagaforge.synth`.

The mood is the old Tristram and Cathedral one: slow, dark and sparse, a detuned twelve-string
arpeggio in a minor mode over a low drone, distant voices, a heartbeat for a drum, a great deal
of room and now and then a bell.  ``title`` is the night over the town, ``battle`` the same
world with a pulse under it, ``boss`` the last wave, with drums.

A piece is a :class:`Score` of 4/4 bars filled by layer functions (pedal, pad, arpeggio, line, ostinato,
drums, bells).  Everything that runs past the end wraps round to the start, the room's tail too,
so every loop is seamless.  The pattern follows Warband's ``music.py``, adapted here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
import random

import numpy as np

from hellward.audio import instruments as inst
from sagaforge.synth import SAMPLE_RATE, highpass, loop_add, pan, reverb, soft_clip

Voice = Callable[..., np.ndarray]
Motif = tuple[tuple[int, float], ...]  # (scale degree relative to the phrase centre, beats)
Progression = tuple[int, ...]  # chord root degrees, one per bar, cycling

MODES = {"aeolian": (0, 2, 3, 5, 7, 8, 10), "phrygian": (0, 1, 3, 5, 7, 8, 10)}
_NOTE_INDEX = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
SPREAD = (0, 2, 4, 7, 9, 11, 14)  # chord tones stacked in thirds: root, third, fifth, octave, tenth, twelfth, two octaves


class Key:
    """A root note and a mode; degrees count scale steps from the root (7 is the octave)."""

    def __init__(self, root: str, mode: str) -> None:
        self.root = 12 * (int(root[-1]) + 1) + _NOTE_INDEX[root[:-1]]
        self.steps = MODES[mode]

    def hz(self, degree: int, octave: int = 0) -> float:
        up, step = divmod(degree, 7)
        return 440.0 * 2 ** ((self.root + 12 * (up + octave) + self.steps[step] - 69) / 12)


def chord_at(progression: Progression, bar: int) -> int:
    return progression[bar % len(progression)]


class Score:
    """A stereo loop of *bars* 4/4 bars at *bpm*; whatever runs past the end wraps to the start."""

    def __init__(self, bpm: float, bars: int) -> None:
        self.bpm, self.bars = bpm, bars
        self.beat = 60 / bpm
        self.length = bars * 4 * self.beat
        self.out = np.zeros((int(round(self.length * SAMPLE_RATE)), 2))
        self._notes: dict[tuple, np.ndarray] = {}

    def add(self, clip: np.ndarray, beat: float, *, at: float = 0.0, gain: float = 1.0) -> None:
        """Place a mono clip at *beat* (0 is the first downbeat), panned to *at* (−1…1)."""
        loop_add(self.out, pan(clip * gain, at), beat * self.beat)

    def note(self, voice: Voice, hz: float, length: float, seed: int = 0) -> np.ndarray:
        """*voice* at *hz* for *length* seconds, memoised: an arpeggio's repeated notes are rendered once."""
        key = (voice, round(hz, 2), round(length, 3), seed)
        if key not in self._notes:
            self._notes[key] = voice(hz, length, seed=seed)
        return self._notes[key]

    def master(self, *, room: float, wet: float, damping: float, rms: float, seed: int) -> np.ndarray:
        """The room (wrapped round the loop), a common loudness judged above 200 Hz, soft limiting."""
        out = reverb(self.out, decay=room, mix=wet, damping=damping, wrap=True, seed=seed)
        heard = highpass(out.mean(axis=1), 200.0, order=2)
        out = soft_clip(out * (rms / math.sqrt(float(np.mean(heard ** 2)))))
        return out * min(1.0, 0.8 / float(np.abs(out).max()))


# -- Layers -------------------------------------------------------------------------


def pedal(score: Score, frequencies: tuple[float, ...], voice: Voice, *, gain: float, span: int = 4, overlap: float = 2.0,
          width: float = 0.3, seed: int = 0) -> None:
    """Hold *frequencies* through the whole loop in *span*-bar notes that crossfade over *overlap* seconds."""
    for bar in range(0, score.bars, span):
        for i, f in enumerate(frequencies):
            clip = voice(f, span * 4 * score.beat + overlap, attack=overlap, seed=seed + 10 * bar + i)
            at = width * (2 * i / max(1, len(frequencies) - 1) - 1) if len(frequencies) > 1 else 0.0
            score.add(clip, bar * 4 - overlap / 2 / score.beat, at=at, gain=gain)


def pad(score: Score, key: Key, progression: Progression, voice: Voice, *, bars: int, start: int = 0, gain: float,
        octave: int = 0, voicing: tuple[int, ...] = (0, 2, 4), width: float = 0.35, overlap: float = 1.2, seed: int = 0) -> None:
    """Hold each chord for as long as it lasts, one voice per tone spread across the field."""
    bar = start
    while bar < start + bars:
        root = chord_at(progression, bar)
        run = 1
        while bar + run < start + bars and chord_at(progression, bar + run) == root:
            run += 1
        for i, tone in enumerate(voicing):
            clip = score.note(voice, key.hz(root + tone, octave), run * 4 * score.beat + overlap, seed + i)
            score.add(clip, bar * 4 - 0.1, at=width * (2 * i / max(1, len(voicing) - 1) - 1), gain=gain)
        bar += run


def arpeggio(score: Score, key: Key, progression: Progression, voice: Voice, *, bars: int, start: int = 0, gain: float,
             at: float = 0.0, pattern: tuple[int, ...] = (0, 2, 3, 4, 3, 2), step: float = 0.5, octave: int = 0,
             ring: float = 2.0, width: float = 0.2, rest: tuple[int, ...] = (), seed: int = 0) -> None:
    """Chord tones in a repeating pattern every *step* beats; *pattern* indexes :data:`SPREAD`.
    Steps listed in *rest* (indexes within the bar) are left silent, which keeps a figure sparse."""
    rng = random.Random(seed)
    per_bar = int(round(4 / step))
    for bar in range(start, start + bars):
        root = chord_at(progression, bar)
        for i in range(per_bar):
            if i in rest:
                continue
            tone = SPREAD[pattern[i % len(pattern)]]
            clip = score.note(voice, key.hz(root + tone, octave), step * score.beat * ring, i % 3)
            score.add(clip, bar * 4 + i * step + rng.uniform(-0.015, 0.015), at=at + width * math.sin(i * 1.3),
                      gain=gain * rng.uniform(0.75, 1.0))


def line(score: Score, key: Key, progression: Progression, motif: Motif, voice: Voice, *, bars: int, start: int = 0, gain: float,
         at: float = 0.0, octave: int = 1, legato: float = 1.0, shapes: tuple[str, ...] = ("A", "A2", "B", "A_end"),
         phrase_bars: int = 2, seed: int = 0) -> None:
    """Sing *motif* in phrases: the plain shape, a sequence on the chord's third, its inversion on the
    fifth, then a version that comes to rest on the root."""
    rng = random.Random(seed)
    for index, phrase in enumerate(range(0, bars, phrase_bars)):
        bar = start + phrase
        root = chord_at(progression, bar)
        shape = shapes[index % len(shapes)]
        centre = {"A": root, "A2": root + 2, "B": root + 4, "A_end": root, "A_low": root - 7}[shape]
        notes = [(-degree, beats) for degree, beats in motif] if shape == "B" else list(motif)
        if shape == "A_end":
            notes[-1] = (0, notes[-1][1])
        beat = bar * 4
        for degree, beats in notes:
            clip = score.note(voice, key.hz(centre + degree, octave), beats * score.beat * legato, rng.randrange(3))
            score.add(clip, beat + rng.uniform(-0.02, 0.02), at=at + rng.uniform(-0.06, 0.06), gain=gain * rng.uniform(0.85, 1.0))
            beat += beats


def ostinato(score: Score, key: Key, progression: Progression, voice: Voice, *, bars: int, start: int = 0, gain: float,
             figure: tuple[int | None, ...], step: float = 0.25, octave: int = 0, ring: float = 0.9, at: float = 0.0, seed: int = 0) -> None:
    """A repeated figure of scale degrees above each bar's root (``None`` rests), every *step* beats."""
    rng = random.Random(seed)
    for bar in range(start, start + bars):
        root = chord_at(progression, bar)
        for i in range(int(round(4 / step))):
            degree = figure[i % len(figure)]
            if degree is None:
                continue
            clip = score.note(voice, key.hz(root + degree, octave), step * score.beat * ring, i % 2)
            score.add(clip, bar * 4 + i * step, at=at, gain=gain * (1.0 if i % 4 == 0 else rng.uniform(0.6, 0.8)))


def drums(score: Score, kit: dict[str, tuple[Callable[[int], np.ndarray], float, float]], patterns: dict[str, str], *, bars: int,
          start: int = 0, fill: dict[str, str] | None = None, every: int = 4, seed: int = 0) -> None:
    """Step patterns per drum, 16 characters a bar: ``X`` hard, ``x`` normal, ``o`` soft, ``.`` rest.
    *fill* replaces the pattern on the last bar of each *every* bars."""
    rng = random.Random(seed)
    clips = {name: [drum(seed + take) for take in range(3)] for name, (drum, _, _) in kit.items()}
    for bar in range(start, start + bars):
        filling = fill is not None and (bar + 1) % every == 0
        for name, (_, gain, at) in kit.items():
            pattern = (fill or {}).get(name, patterns.get(name, "")) if filling else patterns.get(name, "")
            step = 4 / len(pattern) if pattern else 0
            for i, mark in enumerate(pattern):
                if mark != ".":
                    velocity = {"X": 1.0, "x": 0.8, "o": 0.5}[mark] * rng.uniform(0.9, 1.0)
                    score.add(rng.choice(clips[name]), bar * 4 + i * step, at=at + rng.uniform(-0.03, 0.03), gain=gain * velocity)


def bells(score: Score, key: Key, strikes: tuple[tuple[float, int], ...], *, gain: float, length: float = 6.0, at: float = 0.3) -> None:
    """A church bell struck at each (beat, degree)."""
    for i, (beat, degree) in enumerate(strikes):
        score.add(inst.church_bell(key.hz(degree, 1), length, seed=i), beat, at=at * (-1) ** i, gain=gain)


# -- The pieces -----------------------------------------------------------------------------

TRISTRAM: Motif = ((4, 1.5), (3, 0.5), (2, 1.0), (1, 1.0), (0, 3.0), (-1, 1.0))
DESCENT: Motif = ((7, 1.0), (6, 0.5), (4, 0.5), (5, 2.0), (4, 1.0), (1, 1.0), (0, 2.0))
HEART_KIT = {"heart": (inst.heartbeat, 0.32, 0.0), "frame": (inst.frame_drum, 0.16, -0.3), "rattle": (inst.rattle, 0.06, 0.45)}
DOOM_KIT = {"war": (inst.war_drum, 0.28, 0.0), "taiko": (inst.taiko, 0.22, 0.2), "tom": (inst.tom, 0.2, -0.35),
            "heart": (inst.heartbeat, 0.25, 0.0), "rattle": (inst.rattle, 0.07, 0.5)}


def title(s: Score) -> np.ndarray:
    """Night over the town: a lone twelve-string over a drone, voices far off, a bell, a heart under it."""
    key, prog = Key("D2", "aeolian"), (0, 0, 5, 5, 6, 6, 0, 0, 3, 3, 5, 4)
    pedal(s, (key.hz(0, 0), key.hz(4, 0)), inst.drone, gain=0.16, span=6, seed=1)
    arpeggio(s, key, prog, inst.twelve_string, bars=12, gain=0.2, at=-0.2, pattern=(0, 2, 3, 4, 3, 2, 1, 2), octave=1, ring=3.0,
             rest=(7,), seed=2)
    line(s, key, prog, TRISTRAM, inst.twelve_string, bars=4, start=4, gain=0.13, at=0.3, octave=2, shapes=("A", "A_end"), seed=3)
    line(s, key, prog, TRISTRAM, inst.twelve_string, bars=4, start=8, gain=0.11, at=0.35, octave=2, shapes=("B", "A_end"), seed=4)
    pad(s, key, prog, inst.hollow_choir, bars=8, start=4, gain=0.07, octave=1, voicing=(0, 4, 7), seed=5)
    drums(s, HEART_KIT, {"heart": "x..............."}, bars=6, start=6, seed=6)
    bells(s, key, ((0.0, 0), (32.0, 4)), gain=0.1)
    return s.master(room=4.5, wet=0.45, damping=3800, rms=0.085, seed=11)


def battle(s: Score) -> np.ndarray:
    """The same night with a pulse: the heart on every half bar, the guitar quickening, monks and a low bow."""
    key, prog = Key("D2", "phrygian"), (0, 0, 5, 6, 0, 0, 1, 0)
    pedal(s, (key.hz(0, 0), key.hz(4, 0)), inst.drone, gain=0.15, span=8, seed=1)
    drums(s, HEART_KIT, {"heart": "x.......x......."}, bars=8, seed=2)
    drums(s, HEART_KIT, {"heart": "x.......x.......", "frame": "......o.......o.", "rattle": "....o.......o..."}, bars=8, start=8,
          fill={"frame": "......o...o.o.o.", "heart": "x.......x......."}, seed=3)
    drums(s, HEART_KIT, {"heart": "x.......x.......", "rattle": "....o.......o..."}, bars=8, start=16, seed=4)
    arpeggio(s, key, prog, inst.twelve_string, bars=8, gain=0.2, at=-0.2, pattern=(0, 2, 3, 2, 4, 2, 3, 1), octave=1, ring=2.6, seed=5)
    arpeggio(s, key, prog, inst.twelve_string, bars=8, start=8, gain=0.15, at=-0.25, pattern=(0, 2, 3, 4, 3, 2), step=0.25, octave=1,
             ring=2.2, seed=6)
    arpeggio(s, key, prog, inst.twelve_string, bars=8, start=16, gain=0.19, at=-0.2, pattern=(0, 2, 3, 4, 3, 2, 1, 2), octave=1,
             ring=2.6, rest=(7,), seed=7)
    ostinato(s, key, prog, inst.cello, bars=8, start=8, gain=0.09, figure=(0, None, 0, None, 0, None, 1, None), step=0.5, octave=0,
             ring=0.95, at=0.15, seed=8)
    pad(s, key, prog, inst.monks, bars=16, start=8, gain=0.06, octave=1, voicing=(0, 4), seed=9)
    pad(s, key, prog, inst.hollow_choir, bars=8, start=16, gain=0.05, octave=2, voicing=(0, 2, 4), seed=10)
    line(s, key, prog, DESCENT, inst.twelve_string, bars=8, start=4, gain=0.12, at=0.3, octave=2, seed=11)
    line(s, key, prog, TRISTRAM, inst.twelve_string, bars=4, start=18, gain=0.11, at=0.35, octave=2, shapes=("B", "A_end"), seed=12)
    bells(s, key, ((0.0, 0), (32.0, 4), (64.0, 0)), gain=0.09)
    s.add(inst.timpani(key.hz(0, -1), 1.6, seed=3), 32, gain=0.12)
    return s.master(room=4.0, wet=0.4, damping=4000, rms=0.095, seed=12)


def boss(s: Score) -> np.ndarray:
    """The last wave: war drums, a low bow hammering the flat second, an organ and monks in clusters, bells."""
    key, prog = Key("D2", "phrygian"), (0, 0, 1, 1, 0, 0, 6, 1)
    pedal(s, (key.hz(0, 0), key.hz(1, 0)), inst.drone, gain=0.07, span=4, seed=1)
    drums(s, DOOM_KIT, {"war": "x.....x...x.....", "heart": "........x......."}, bars=4, seed=2)
    drums(s, DOOM_KIT, {"war": "x.....x...x.....", "taiko": "....x.......x..x", "heart": "........x.......", "rattle": "..o...o...o...o."},
          bars=16, start=4, fill={"tom": "x.x.x.x.x.xxx.xx", "war": "x.....x...x....."}, seed=3)
    ostinato(s, key, prog, inst.cello, bars=20, gain=0.09, figure=(0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 4, 0, 1, 0), step=0.25, octave=1,
             ring=0.9, at=0.1, seed=4)
    arpeggio(s, key, prog, inst.twelve_string, bars=16, start=4, gain=0.14, at=-0.3, pattern=(0, 3, 2, 3, 4, 3, 2, 3), step=0.25, octave=1,
             ring=1.6, seed=5)
    pad(s, key, prog, inst.organ, bars=12, start=8, gain=0.06, octave=1, voicing=(0, 1, 4, 7), seed=6)
    pad(s, key, prog, inst.monks, bars=16, start=4, gain=0.07, octave=1, voicing=(0, 4), seed=7)
    line(s, key, prog, DESCENT, inst.hollow_choir, bars=8, start=12, gain=0.07, at=0.2, octave=2, phrase_bars=4, shapes=("A", "B"), seed=8)
    for bar in range(0, 20, 4):
        s.add(inst.timpani(key.hz(chord_at(prog, bar), -1), 1.4, seed=bar), bar * 4, gain=0.12)
    bells(s, key, tuple((bar * 4.0, (0, 1)[bar // 8 % 2]) for bar in range(0, 20, 8)), gain=0.08, length=5.0)
    return s.master(room=3.2, wet=0.32, damping=4200, rms=0.11, seed=13)


@dataclass(frozen=True)
class Piece:
    """A composition and the canvas it is written on."""

    compose: Callable[[Score], np.ndarray]
    bpm: float
    bars: int

    @property
    def seconds(self) -> float:
        return self.bars * 4 * 60 / self.bpm

    def render(self) -> np.ndarray:
        return self.compose(Score(self.bpm, self.bars))


PIECES: dict[str, Piece] = {"title": Piece(title, 64, 12), "battle": Piece(battle, 72, 24), "boss": Piece(boss, 88, 20)}
