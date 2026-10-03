"""Hellward's music: a loop for the town and a five-minute score for each dungeon, composed with
:mod:`hellward.audio.instruments` on :mod:`sagaforge.synth`.

The mood is the old Tristram and Cathedral one: slow, dark and sparse, a detuned twelve-string
arpeggio in a minor mode over a low drone, distant voices, a heartbeat for a drum, a great deal
of room and now and then a bell.  ``title`` is the night over the town; each ``battle_<location>``
is the same world heard from one dungeon down the descent, with its own key, pulse and consort;
``boss`` is the last-wave suite, with drums: Azazel's at the gate, the Bone Priest's at the temple.

A dungeon is a sequence of eight-bar chapters with a distinct harmonic route and changing
orchestration.  Chapters overlap in the room; the complete score fades to silence and is played once.
The town cue remains a short loop; the boss has its own one-shot suite. The instruments follow
Warband's ``music.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
import math
import random

import numpy as np

from hellward.audio import instruments as inst
from sagaforge.synth import SAMPLE_RATE, highpass, loop_add, noise, pan, reverb, soft_clip

Voice = Callable[..., np.ndarray]
Motif = tuple[tuple[int, float], ...]  # (scale degree relative to the phrase centre, beats)
Progression = tuple[int, ...]  # chord root degrees, one per bar, cycling

MODES = {
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian_dominant": (0, 1, 4, 5, 7, 8, 10),
}
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
BONE_KIT = {"heart": (inst.heartbeat, 0.22, 0.0), "frame": (inst.frame_drum, 0.12, -0.3), "rattle": (inst.rattle, 0.12, 0.45)}
LAVA_KIT = {"war": (inst.war_drum, 0.22, -0.1), "taiko": (inst.taiko, 0.22, 0.25), "tom": (inst.tom, 0.16, -0.35),
            "heart": (inst.heartbeat, 0.2, 0.0), "rattle": (inst.rattle, 0.08, 0.5)}
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


# -- The dungeon suites --------------------------------------------------------------------

CHAPTER_BARS = 8
OVERLAP = 2.0


@dataclass(frozen=True)
class Dungeon:
    """The themes and acoustic space of one descent. Progressions are alternate eight-bar journeys."""

    root: str
    mode: str
    bpm: float
    progressions: tuple[Progression, ...]
    motif: Motif
    lead: Voice
    harmony: Voice
    pulse: dict[str, tuple[Callable[[int], np.ndarray], float, float]]
    pattern: dict[str, str]
    arpeggio_pattern: tuple[int, ...]
    atmosphere: str
    arc: tuple[int, ...]
    room: float
    wet: float
    rms: float
    blurb: str = ""   # what plays, in a line: the story walk's music note (docs/audio.md says more)


DUNGEONS: dict[str, Dungeon] = {
    "tristram": Dungeon("D2", "aeolian", 68,
        ((0, 0, 5, 5, 6, 6, 3, 4), (0, 3, 5, 4, 6, 5, 3, 0), (0, 0, 6, 5, 3, 3, 4, 0)),
        TRISTRAM, inst.twelve_string, inst.hollow_choir, HEART_KIT,
        {"heart": "x.......x.......", "frame": "......o.......o."},
        (0, 2, 3, 4, 3, 2, 1, 2), "embers",
        (0, 1, 1, 2, 2, 1, 2, 3, 2, 3, 4, 3, 2, 0), 4.5, 0.43, 0.08,
        blurb="D aeolian: a solitary twelve-string, the heart and a village lament as the fire grows"),
    "graveyard": Dungeon("E2", "dorian", 60,
        ((0, 0, 3, 3, 4, 4, 3, 2), (0, 5, 4, 3, 2, 3, 0, 0), (0, 0, 2, 3, 5, 4, 2, 0)),
        ((7, 2), (5, 1), (4, 1), (3, 1), (2, 1), (0, 2)),
        inst.hollow_choir, inst.organ, BONE_KIT,
        {"heart": "x...............", "rattle": "..o...o...o...o."},
        (0, 3, 4, 3, 2, 1, 0, 2), "wind_drips",
        (0, 1, 1, 2, 1, 2, 2, 3, 1, 2, 3, 0), 5.0, 0.5, 0.075,
        blurb="E dorian: wind, grave drops, a distant choral lament, organ and funeral bells"),
    "cathedral": Dungeon("D2", "phrygian", 72,
        ((0, 0, 5, 6, 0, 0, 1, 0), (0, 3, 5, 6, 1, 0, 6, 0), (0, 0, 1, 5, 3, 3, 1, 0)),
        DESCENT, inst.twelve_string, inst.monks, HEART_KIT,
        {"heart": "x.......x.......", "frame": "......o.......o.", "rattle": "....o.......o..."},
        (0, 2, 3, 2, 4, 2, 3, 1), "nave_drips",
        (0, 1, 2, 2, 3, 1, 2, 3, 3, 4, 2, 3, 2, 0), 4.0, 0.43, 0.085,
        blurb="D phrygian: a torchlit procession, monks, frame drum and bells gathering in the nave"),
    "catacombs": Dungeon("C2", "phrygian", 66,
        ((0, 0, 1, 1, 0, 6, 1, 1), (0, 1, 0, 6, 1, 3, 1, 0), (0, 0, 6, 1, 3, 1, 6, 0)),
        ((0, 1), (1, 0.5), (0, 0.5), (-1, 1), (0, 1), (4, 1), (1, 1), (0, 2)),
        inst.cello, inst.organ, {"heart": HEART_KIT["heart"], "tom": (inst.tom, 0.13, -0.3)},
        {"heart": "x...............", "tom": "....x.......x..."},
        (0, 1, 2, 1, 0, 1, 3, 1), "crypt_drips",
        (0, 1, 2, 2, 1, 2, 3, 2, 3, 4, 3, 2, 0), 2.7, 0.3, 0.08,
        blurb="C phrygian: close dripping stone, a bowed flat second, organ and toms in the bone halls"),
    "caves": Dungeon("F2", "phrygian_dominant", 92,
        ((0, 0, 5, 4, 0, 6, 5, 4), (0, 1, 5, 6, 4, 5, 1, 0), (0, 0, 4, 5, 6, 5, 4, 0)),
        ((0, 0.5), (1, 0.5), (4, 0.5), (5, 1), (7, 0.5), (5, 1), (4, 1), (1, 1), (0, 2)),
        inst.twelve_string, inst.cello, LAVA_KIT,
        {"war": "x.....x...x.....", "taiko": "....x.......x..x", "rattle": "..o...o...o...o."},
        (0, 3, 2, 3, 4, 3, 2, 3), "lava",
        (0, 1, 2, 2, 3, 2, 3, 4, 3, 2, 4, 3, 4, 4, 3, 1, 0), 3.5, 0.36, 0.085,
        blurb="F phrygian-dominant: lava breaths, racing guitar, a rising ember melody and war drums"),
    "hells_gate": Dungeon("D2", "phrygian", 84,
        ((0, 0, 1, 1, 0, 0, 6, 5), (0, 1, 3, 1, 6, 5, 1, 0), (0, 0, 6, 1, 3, 1, 6, 0)),
        ((7, 1), (6, 0.5), (4, 0.5), (1, 1), (0, 1), (-1, 1), (1, 1), (0, 2)),
        inst.hollow_choir, inst.monks, DOOM_KIT,
        {"war": "x.....x...x.....", "taiko": "....x.......x..x", "heart": "........x......."},
        (0, 3, 2, 3, 4, 3, 2, 3), "abyss",
        (0, 1, 2, 3, 2, 3, 4, 3, 2, 4, 3, 4, 4, 3, 2, 0), 3.2, 0.37, 0.09,
        blurb="D phrygian: infernal air, a falling choir and the village melody back in a darker form"),
}

# Act II, the Drowned Temples: the same night heard across the sea, in Kurast's jungle and its drowned city.
DUNGEONS.update({
    "docks": Dungeon("G2", "aeolian", 64,
        ((0, 0, 3, 3, 5, 5, 4, 4), (0, 5, 3, 4, 0, 6, 5, 0), (0, 0, 5, 3, 4, 4, 6, 0)),
        ((0, 1), (2, 1), (4, 2), (3, 1), (2, 1), (0, 2)),
        inst.chime, inst.hollow_choir, {"heart": (inst.heartbeat, 0.2, 0.0), "frame": (inst.frame_drum, 0.12, -0.3)},
        {"heart": "x.......x.......", "frame": "....o.......o..."},
        (0, 2, 4, 2, 3, 2, 1, 2), "harbour",
        (0, 1, 1, 2, 2, 1, 2, 3, 2, 3, 3, 2, 1, 0), 5.0, 0.48, 0.08,
        blurb="G aeolian: a harbour swell, chimes over a hollow choir, a slow heart and frame drum"),
    "spider_forest": Dungeon("A2", "dorian", 76,
        ((0, 0, 1, 1, 3, 3, 1, 0), (0, 3, 1, 0, 4, 3, 1, 0), (0, 1, 3, 4, 3, 1, 0, 0)),
        ((4, 0.5), (5, 0.5), (4, 0.5), (2, 0.5), (1, 1), (0, 1), (-1, 1), (0, 3)),
        inst.twelve_string, inst.choir, {"rattle": (inst.rattle, 0.14, 0.45), "tom": (inst.tom, 0.12, -0.3)},
        {"rattle": "o.o...o.o...o...", "tom": "....x.......x..."},
        (0, 1, 3, 1, 4, 1, 3, 1), "insects",
        (0, 1, 2, 1, 2, 3, 2, 3, 3, 2, 1, 0), 4.2, 0.4, 0.08,
        blurb="A dorian: skittering twelve-string over rattles and toms, insects in the dark"),
    "jungle": Dungeon("E2", "phrygian", 96,
        ((0, 0, 1, 0, 6, 6, 1, 0), (0, 1, 3, 1, 0, 6, 1, 0), (0, 0, 6, 1, 3, 1, 0, 0)),
        ((0, 0.5), (0, 0.5), (3, 0.5), (1, 0.5), (0, 1), (-2, 1), (0, 2)),
        inst.cello, inst.monks,
        {"taiko": (inst.taiko, 0.22, 0.25), "tom": (inst.tom, 0.18, -0.35), "frame": (inst.frame_drum, 0.12, 0.1)},
        {"taiko": "x..x..x...x..x..", "tom": "..x...x...x...x.", "frame": "o.o.o.o.o.o.o.o."},
        (0, 3, 2, 3, 4, 3, 2, 3), "insects",
        (0, 1, 2, 3, 2, 3, 4, 3, 4, 4, 3, 2, 0), 3.2, 0.34, 0.085,
        blurb="E phrygian: hunting drums (taiko, toms, a running frame drum), a cello and monks"),
    "drowned_city": Dungeon("C#2", "aeolian", 56,
        ((0, 0, 5, 5, 3, 3, 6, 6), (0, 6, 5, 3, 4, 5, 6, 0)),
        ((4, 2), (3, 1), (1, 1), (0, 2), (-1, 1), (-3, 1)),
        inst.hollow_choir, inst.organ, {"heart": (inst.heartbeat, 0.26, 0.0)},
        {"heart": "x..............."},
        (0, 2, 1, 2, 0, 2, 1, 2), "canal",
        (0, 1, 1, 2, 1, 2, 2, 3, 2, 1, 2, 0), 6.0, 0.55, 0.075,
        blurb="C# aeolian: sunk and slow, a hollow choir over organ, a lone heart, water dripping"),
    "travincal": Dungeon("D#2", "phrygian", 80,
        ((0, 0, 1, 1, 3, 3, 1, 0), (0, 1, 6, 5, 1, 0, 1, 0), (0, 3, 1, 6, 0, 1, 6, 0)),
        ((0, 1), (1, 1), (3, 1), (4, 1), (3, 0.5), (1, 0.5), (0, 2)),
        inst.monks, inst.organ, DOOM_KIT,
        {"war": "x.......x.......", "taiko": "....x.......x...", "heart": "x...x...x...x..."},
        (0, 3, 2, 3, 4, 3, 2, 3), "terrace",
        (0, 1, 2, 3, 2, 3, 4, 3, 4, 4, 3, 4, 4, 3, 1, 0), 3.8, 0.4, 0.09,
        blurb="D# phrygian: the council's procession, monks and organ over war drums"),
    "temple": Dungeon("B1", "phrygian_dominant", 72,
        ((0, 0, 4, 4, 5, 5, 1, 0), (0, 1, 4, 5, 4, 1, 0, 0), (0, 0, 5, 4, 1, 1, 4, 0)),
        ((7, 2), (4, 1), (5, 1), (4, 1), (1, 1), (0, 2)),
        inst.choir, inst.organ, HEART_KIT,
        {"heart": "x.......x.......", "frame": "......o.......o."},
        (0, 2, 4, 2, 4, 2, 3, 1), "temple_hum",
        (0, 1, 1, 2, 2, 3, 3, 4, 3, 4, 4, 3, 2, 0), 5.5, 0.5, 0.085,
        blurb="B phrygian-dominant: the mother lamp's hall, choir and organ, the heart rising to the last fight"),
})

BOSS = replace(DUNGEONS["hells_gate"], bpm=88, motif=DESCENT,
               progressions=((0, 0, 1, 1, 0, 0, 6, 1), (0, 1, 6, 1, 3, 1, 6, 0)),
               arc=(2, 3, 4, 3, 4, 4, 3, 4, 4, 2, 0), rms=0.095,
               blurb="Azazel's last wave: the gate's music driven harder, then emptied out at the end")

#: What the walk says over each boss's entrance, by monster kind: one suite, two hearings.
BOSS_BLURBS: dict[str, str] = {
    "azazel": BOSS.blurb,
    "bone_priest": "The Bone Priest's last wave: drums over the temple's music, then emptied out at the end",
}

TITLE_BLURB = ("D aeolian over a D–A drone: a lone twelve-string arpeggio, a slow falling melody, "
               "distant voices, a bell, a heart under the second half")


def _atmosphere(s: Score, kind: str, chapter: int) -> None:
    """Place distinct, quiet environmental sounds throughout a chapter, behind the score."""
    rng = random.Random(7919 * chapter + sum(map(ord, kind)))
    bands = {
        "embers": (180, 1300), "wind_drips": (80, 700), "nave_drips": (100, 750), "crypt_drips": (65, 480),
        "lava": (45, 450), "abyss": (35, 350),
        "harbour": (40, 400), "insects": (1500, 6500), "canal": (60, 520), "terrace": (35, 350), "temple_hum": (50, 500),
    }
    low, high = bands[kind]
    for i in range(4):
        length = rng.uniform(5.0, 8.0)
        breath = noise(length, low, high, attack=1.3, tau=length * 2, seed=chapter * 100 + i)
        breath[-int(1.2 * SAMPLE_RATE):] *= np.linspace(1, 0, int(1.2 * SAMPLE_RATE))
        s.add(breath, (i * s.length / 4 + rng.uniform(-0.7, 0.7)) / s.beat,
              at=rng.uniform(-0.7, 0.7), gain=0.025 if kind != "lava" else 0.04)
    for i in range(7):
        beat = rng.uniform(0.5, CHAPTER_BARS * 4 - 1)
        if kind in ("wind_drips", "nave_drips", "crypt_drips", "harbour", "canal"):
            clip = inst.drip(rng.uniform(520, 1050), seed=chapter * 100 + i)
            gain = 0.035 if kind == "wind_drips" else 0.045
        elif kind in ("embers", "insects"):
            clip = noise(0.16, 1200, 5800, tau=0.045, seed=chapter * 100 + i)
            gain = 0.012
        else:
            clip = noise(0.8, 55, 1100, attack=0.15, tau=0.24, seed=chapter * 100 + i)
            gain = 0.035 if kind == "lava" else 0.05
        s.add(clip, beat, at=rng.uniform(-0.8, 0.8), gain=gain)


def _chapter(spec: Dungeon, index: int, total: int) -> np.ndarray:
    s = Score(spec.bpm, CHAPTER_BARS)
    key = Key(spec.root, spec.mode)
    progression = spec.progressions[index % len(spec.progressions)]
    strength = spec.arc[round(index * (len(spec.arc) - 1) / (total - 1))]
    root = progression[0]
    low = (key.hz(root), key.hz(root + (1 if spec.mode == "phrygian" else 4)))
    pedal(s, low, inst.drone, gain=0.09 + strength * 0.008, span=4, seed=1000 + index)
    _atmosphere(s, spec.atmosphere, index)

    if strength >= 1:
        pad(s, key, progression, spec.harmony, bars=8, gain=0.022 + 0.008 * strength,
            octave=1 if spec.atmosphere != "crypt_drips" else 0,
            voicing=(0, 4) if strength < 3 else (0, 2, 4), seed=2000 + index)
        arpeggio(s, key, progression, inst.twelve_string if spec.atmosphere != "crypt_drips" else inst.cello,
                 bars=8, gain=0.09 + 0.012 * strength, at=-0.28, pattern=spec.arpeggio_pattern,
                 step=0.5 if strength < 3 else 0.25, octave=1, ring=2.1,
                 rest=(1, 3, 5, 7) if strength == 1 else (), seed=3000 + index)
    motif = TRISTRAM if spec.atmosphere == "abyss" and index >= total // 2 and index % 3 == 1 else spec.motif
    if strength == 0:
        line(s, key, progression, motif, spec.lead, bars=2, start=2 if index == 0 else 0,
             gain=0.045, at=0.3, octave=0 if spec.atmosphere == "crypt_drips" else 2,
             shapes=("A_end",), seed=4000 + index)
    elif strength == 1:
        line(s, key, progression, motif, spec.lead, bars=2, start=4 if index % 2 else 0,
             gain=0.06, at=0.3, octave=0 if spec.atmosphere == "crypt_drips" else 2,
             shapes=("A",), seed=4000 + index)
    else:
        line(s, key, progression, motif, spec.lead, bars=4, start=4 if index % 3 == 0 else 0,
             gain=0.07 + strength * 0.01, at=0.3, octave=0 if spec.atmosphere == "crypt_drips" else 2,
             shapes=("A", "A_end") if index % 2 else ("B", "A2"), seed=4000 + index)
    if strength >= 3:
        drums(s, spec.pulse, spec.pattern, bars=8, fill={name: value.replace(".", "o", 1) for name, value in spec.pattern.items()},
              every=4, seed=5000 + index)
        ostinato(s, key, progression, inst.cello, bars=8, gain=0.045 + 0.01 * strength,
                 figure=(0, None, 4, None, 0, None, 1, None), step=0.5, octave=0, at=0.12,
                 seed=6000 + index)
    elif strength == 2:
        drums(s, spec.pulse, {name: pattern if name in ("heart", "war") else "." * 16
                              for name, pattern in spec.pattern.items()}, bars=8, seed=5000 + index)
    if index % 4 == 0 and spec.atmosphere not in ("lava", "crypt_drips"):
        bells(s, key, ((2.0, root),), gain=0.04 + 0.008 * strength, length=7)
    if strength == 4:
        s.add(inst.timpani(key.hz(root, -1), 1.7, seed=index), 0, gain=0.09)
    return s.master(room=spec.room, wet=spec.wet, damping=3500, rms=spec.rms * (0.35 + strength * 0.17),
                    seed=7000 + index).astype(np.float32)


@dataclass(frozen=True)
class DungeonPiece:
    """A through-composed dungeon score. The soundtrack never repeats or wraps at playback."""

    spec: Dungeon
    target: float = 300.0

    @property
    def chapters(self) -> int:
        chapter_seconds = CHAPTER_BARS * 4 * 60 / self.spec.bpm
        return math.ceil((self.target - OVERLAP) / (chapter_seconds - OVERLAP))

    @property
    def seconds(self) -> float:
        return self.chapters * CHAPTER_BARS * 4 * 60 / self.spec.bpm - (self.chapters - 1) * OVERLAP

    def render(self) -> np.ndarray:
        length = int(round(self.seconds * SAMPLE_RATE))
        out = np.zeros((length, 2), dtype=np.float32)
        overlap = int(OVERLAP * SAMPLE_RATE)
        cursor = 0
        for index in range(self.chapters):
            chapter = _chapter(self.spec, index, self.chapters)
            if index:
                chapter[:overlap] *= np.linspace(0, 1, overlap, dtype=np.float32)[:, None]
            if index < self.chapters - 1:
                chapter[-overlap:] *= np.linspace(1, 0, overlap, dtype=np.float32)[:, None]
            end = min(length, cursor + len(chapter))
            out[cursor:end] += chapter[:end - cursor]
            cursor += len(chapter) - overlap
        out[:SAMPLE_RATE // 2] *= np.linspace(0, 1, SAMPLE_RATE // 2, dtype=np.float32)[:, None]
        out[-3 * SAMPLE_RATE:] *= np.linspace(1, 0, 3 * SAMPLE_RATE, dtype=np.float32)[:, None]
        return out


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


PIECES: dict[str, Piece | DungeonPiece] = {
    "title": Piece(title, 64, 12),
    **{f"battle_{name}": DungeonPiece(spec) for name, spec in DUNGEONS.items()},
    "boss": DungeonPiece(BOSS, 240),
}

#: Every location's battle track, in the campaign's order.
BATTLE_FOR: dict[str, str] = {name: f"battle_{name}" for name in DUNGEONS}


def track_for(location_key: str) -> str:
    """The battle track for a location's key (``"tristram"`` → ``"battle_tristram"``)."""
    return BATTLE_FOR[location_key]
