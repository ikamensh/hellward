"""Hellward's music: a loop for the town and one for each dungeon on the way down, composed with
:mod:`hellward.audio.instruments` on :mod:`sagaforge.synth`.

The mood is the old Tristram and Cathedral one: slow, dark and sparse, a detuned twelve-string
arpeggio in a minor mode over a low drone, distant voices, a heartbeat for a drum, a great deal
of room and now and then a bell.  ``title`` is the night over the town; each ``battle_<location>``
is the same world heard from one dungeon down the descent, with its own key, pulse and consort;
``boss`` is Azazel's last wave, with drums.

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

MODES = {
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian_dominant": (0, 1, 4, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
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
LAMENT: Motif = ((7, 2.0), (5, 1.0), (4, 2.0), (3, 1.0), (2, 3.0), (0, 2.0))
EMBER: Motif = ((0, 0.5), (1, 0.5), (4, 0.5), (5, 1.0), (4, 0.5), (1, 0.5), (0, 2.0))
TIDE: Motif = ((0, 1.0), (2, 0.5), (4, 1.0), (5, 0.5), (4, 1.0), (2, 0.5), (0, 2.0))
SKITTER: Motif = ((0, 0.25), (2, 0.25), (4, 0.25), (6, 0.25), (8, 0.5), (6, 0.25), (4, 0.25), (2, 0.25), (0, 1.0))
HUNT: Motif = ((0, 0.5), (0, 0.5), (3, 0.5), (5, 1.0), (3, 0.5), (0, 1.0), (-3, 0.5), (-5, 1.0))
SIGH: Motif = ((0, 3.0), (2, 1.5), (1, 1.5), (0, 4.0))
PROCESSION: Motif = ((0, 1.0), (2, 1.0), (4, 2.0), (5, 1.0), (4, 1.0), (2, 0.5), (0, 2.0))
GOLDEN: Motif = ((0, 1.5), (4, 1.0), (6, 0.5), (4, 1.0), (2, 1.0), (0, 2.0), (-3, 1.0), (0, 3.0))
HEART_KIT = {"heart": (inst.heartbeat, 0.32, 0.0), "frame": (inst.frame_drum, 0.16, -0.3), "rattle": (inst.rattle, 0.06, 0.45)}
BONE_KIT = {"heart": (inst.heartbeat, 0.22, 0.0), "frame": (inst.frame_drum, 0.12, -0.3), "rattle": (inst.rattle, 0.12, 0.45)}
LAVA_KIT = {"war": (inst.war_drum, 0.22, -0.1), "taiko": (inst.taiko, 0.22, 0.25), "tom": (inst.tom, 0.16, -0.35),
            "heart": (inst.heartbeat, 0.2, 0.0), "rattle": (inst.rattle, 0.08, 0.5)}
DOOM_KIT = {"war": (inst.war_drum, 0.28, 0.0), "taiko": (inst.taiko, 0.22, 0.2), "tom": (inst.tom, 0.2, -0.35),
            "heart": (inst.heartbeat, 0.25, 0.0), "rattle": (inst.rattle, 0.07, 0.5)}
SWAMP_KIT = {"heart": (inst.heartbeat, 0.18, 0.0), "frame": (inst.frame_drum, 0.1, -0.2), "click": (inst.rattle, 0.08, 0.3), "water": (inst.rattle, 0.04, 0.5)}
SPIDER_KIT = {"click": (inst.rattle, 0.12, -0.4), "tick": (inst.rattle, 0.08, 0.4), "frame": (inst.frame_drum, 0.06, 0.0)}
JUNGLE_KIT = {"frame": (inst.frame_drum, 0.2, -0.3), "log": (inst.tom, 0.22, 0.25), "heart": (inst.heartbeat, 0.15, 0.0), "rattle": (inst.rattle, 0.1, 0.4)}
DROWNED_KIT = {"sub": (inst.heartbeat, 0.12, 0.0)}
TRAVINCAL_KIT = {"heart": (inst.heartbeat, 0.25, 0.0), "frame": (inst.frame_drum, 0.14, -0.3), "tom": (inst.tom, 0.12, -0.2)}
TEMPLE_KIT = {"heart": (inst.heartbeat, 0.28, 0.0), "frame": (inst.frame_drum, 0.1, -0.2)}


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


def battle_tristram(s: Score) -> np.ndarray:
    """The burning village: the familiar night, sad and open, embers in the air. A lone twelve-string
    over a D-A drone, the heart under it, a low bow and far voices joining for the second half."""
    key, prog = Key("D2", "aeolian"), (0, 0, 5, 5, 6, 6, 3, 4)
    pedal(s, (key.hz(0, 0), key.hz(4, 0)), inst.drone, gain=0.16, span=8, seed=1)
    drums(s, HEART_KIT, {"heart": "x.......x......."}, bars=16, seed=2)
    drums(s, HEART_KIT, {"frame": "......o.......o.", "rattle": "....o.......o..."}, bars=8, start=8, seed=3)
    arpeggio(s, key, prog, inst.twelve_string, bars=16, gain=0.2, at=-0.2, pattern=(0, 2, 3, 4, 3, 2, 1, 2), octave=1, ring=3.0,
             rest=(7,), seed=4)
    arpeggio(s, key, prog, inst.twelve_string, bars=8, start=8, gain=0.11, at=-0.25, pattern=(0, 2, 3, 4, 3, 2), step=0.25,
             octave=1, ring=2.2, seed=5)
    ostinato(s, key, prog, inst.cello, bars=8, start=8, gain=0.07, figure=(0, None, 0, None, 0, None, 4, None), step=0.5, octave=0,
             ring=0.95, at=0.15, seed=6)
    pad(s, key, prog, inst.hollow_choir, bars=8, start=8, gain=0.06, octave=1, voicing=(0, 4, 7), seed=7)
    line(s, key, prog, TRISTRAM, inst.twelve_string, bars=4, start=4, gain=0.13, at=0.3, octave=2, shapes=("A", "A_end"), seed=8)
    line(s, key, prog, TRISTRAM, inst.twelve_string, bars=4, start=12, gain=0.11, at=0.35, octave=2, shapes=("B", "A_end"), seed=9)
    bells(s, key, ((0.0, 0), (32.0, 4)), gain=0.1)
    s.add(inst.timpani(key.hz(0, -1), 1.6, seed=3), 32, gain=0.1)
    return s.master(room=4.5, wet=0.45, damping=3800, rms=0.09, seed=21)


def battle_graveyard(s: Score) -> np.ndarray:
    """Moon over open graves: cold mist, wet turf, bones in the earth. An E dorian lament on high strings
    and far voices over an organ, dry bones for drums, funeral bells through the biggest room of the descent."""
    key, prog = Key("E2", "dorian"), (0, 0, 3, 3, 4, 4, 3, 2)
    pedal(s, (key.hz(0, 0), key.hz(4, 0)), inst.drone, gain=0.15, span=6, seed=1)
    drums(s, BONE_KIT, {"heart": "x..............."}, bars=12, seed=2)
    drums(s, BONE_KIT, {"frame": "......o.........", "rattle": "..o...o...o...o."}, bars=6, start=6, seed=3)
    arpeggio(s, key, prog, inst.twelve_string, bars=12, gain=0.13, at=-0.2, pattern=(0, 3, 4, 3, 2, 1, 0, 2), octave=2, ring=3.2,
             rest=(1, 3, 5, 6, 7), seed=4)
    pad(s, key, prog, inst.organ, bars=12, gain=0.05, octave=1, voicing=(0, 2, 4, 7), seed=5)
    pad(s, key, prog, inst.hollow_choir, bars=6, start=6, gain=0.05, octave=2, voicing=(0, 4), seed=6)
    line(s, key, prog, LAMENT, inst.hollow_choir, bars=6, start=4, gain=0.06, at=0.2, octave=2, legato=1.2, phrase_bars=3,
         shapes=("A", "A_end"), seed=7)
    bells(s, key, ((0.0, 0), (16.0, 2), (32.0, 0)), gain=0.1, length=7.0)
    return s.master(room=5.0, wet=0.5, damping=3200, rms=0.08, seed=22)


def battle_cathedral(s: Score) -> np.ndarray:
    """The desecrated nave: a liturgical procession under torchlight. D phrygian, the heart on every half
    bar, the guitar quickening to sixteenths in the second half with frame drum, rattles and a low bow;
    monks and far voices; bells every eight bars."""
    key, prog = Key("D2", "phrygian"), (0, 0, 5, 6, 0, 0, 1, 0)
    pedal(s, (key.hz(0, 0), key.hz(4, 0)), inst.drone, gain=0.15, span=8, seed=1)
    drums(s, HEART_KIT, {"heart": "x.......x......."}, bars=8, seed=2)
    drums(s, HEART_KIT, {"heart": "x.......x.......", "frame": "......o.......o.", "rattle": "....o.......o..."}, bars=8, start=8,
          fill={"frame": "......o...o.o.o.", "heart": "x.......x......."}, every=8, seed=3)
    arpeggio(s, key, prog, inst.twelve_string, bars=8, gain=0.2, at=-0.2, pattern=(0, 2, 3, 2, 4, 2, 3, 1), octave=1, ring=2.6, seed=4)
    arpeggio(s, key, prog, inst.twelve_string, bars=8, start=8, gain=0.15, at=-0.25, pattern=(0, 2, 3, 4, 3, 2), step=0.25, octave=1,
             ring=2.2, seed=5)
    ostinato(s, key, prog, inst.cello, bars=8, start=8, gain=0.09, figure=(0, None, 0, None, 0, None, 1, None), step=0.5, octave=0,
             ring=0.95, at=0.15, seed=6)
    pad(s, key, prog, inst.monks, bars=8, start=8, gain=0.06, octave=1, voicing=(0, 4), seed=7)
    pad(s, key, prog, inst.hollow_choir, bars=4, start=12, gain=0.05, octave=2, voicing=(0, 2, 4), seed=8)
    line(s, key, prog, DESCENT, inst.twelve_string, bars=4, start=4, gain=0.12, at=0.3, octave=2, seed=9)
    line(s, key, prog, TRISTRAM, inst.twelve_string, bars=4, start=12, gain=0.11, at=0.35, octave=2, shapes=("B", "A_end"), seed=10)
    bells(s, key, ((0.0, 0), (32.0, 4)), gain=0.09)
    s.add(inst.timpani(key.hz(0, -1), 1.6, seed=3), 32, gain=0.12)
    return s.master(room=4.0, wet=0.4, damping=4000, rms=0.095, seed=23)


def battle_catacombs(s: Score) -> np.ndarray:
    """The bone halls: narrow, low and close, torchlight on stacked skulls. A C-Db drone under a cello
    hammering the flat second, toms and a heart in the walls, low monks and organ, one deep bell. No
    high strings: nothing sparkles down here. The driest room of the descent."""
    key, prog = Key("C2", "phrygian"), (0, 0, 1, 1, 0, 6, 1, 1)
    pedal(s, (key.hz(0, 0), key.hz(1, 0)), inst.drone, gain=0.08, span=6, seed=1)
    drums(s, HEART_KIT, {"heart": "x...............", "tom": "....x.......x..."}, bars=12, seed=2)
    drums(s, HEART_KIT, {"frame": "......o.......o."}, bars=6, start=6, seed=3)
    ostinato(s, key, prog, inst.cello, bars=12, gain=0.1, figure=(0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 6, 0, 1, 0), step=0.25, octave=0,
             ring=0.9, at=0.1, seed=4)
    pad(s, key, prog, inst.organ, bars=12, gain=0.05, octave=1, voicing=(0, 1), seed=5)
    pad(s, key, prog, inst.monks, bars=6, start=6, gain=0.07, octave=0, voicing=(0, 1, 4), seed=6)
    line(s, key, prog, DESCENT, inst.cello, bars=4, start=4, gain=0.1, at=0.15, octave=0, shapes=("A", "B"), seed=7)
    for bar in range(0, 12, 4):
        s.add(inst.timpani(key.hz(chord_at(prog, bar), -1), 1.4, seed=bar), bar * 4, gain=0.12)
    bells(s, key, ((0.0, 0),), gain=0.06, length=7.0)
    return s.master(room=2.8, wet=0.3, damping=4600, rms=0.09, seed=24)


def battle_caves(s: Score) -> np.ndarray:
    """Lava light: a primal vault of rock and fire, wings overhead. F phrygian-dominant, restless taiko
    and war drums under a bright sixteenth-note guitar and a driving bow, a rising ember of a melody.
    No church bells this deep: only timpani and stone."""
    key, prog = Key("F2", "phrygian_dominant"), (0, 0, 5, 4, 0, 6, 5, 4)
    pedal(s, (key.hz(0, 0), key.hz(4, 0)), inst.drone, gain=0.12, span=8, seed=1)
    drums(s, LAVA_KIT, {"taiko": "....x.......x...", "heart": "........x......."}, bars=4, seed=2)
    drums(s, LAVA_KIT, {"war": "x.....x...x.....", "taiko": "....x.......x..x", "heart": "........x.......", "rattle": "..o...o...o...o."},
          bars=12, start=4, fill={"tom": "x.x.x.x.x.xxx.xx", "war": "x.....x...x....."}, seed=3)
    arpeggio(s, key, prog, inst.twelve_string, bars=12, start=4, gain=0.14, at=-0.3, pattern=(0, 3, 2, 3, 4, 3, 2, 3), step=0.25, octave=1,
             ring=1.6, seed=4)
    ostinato(s, key, prog, inst.cello, bars=12, start=4, gain=0.09, figure=(0, None, 4, None, 5, None, 4, None), step=0.5, octave=0,
             ring=0.9, at=0.1, seed=5)
    pad(s, key, prog, inst.hollow_choir, bars=8, start=8, gain=0.045, octave=2, voicing=(0, 2, 4), seed=6)
    line(s, key, prog, EMBER, inst.twelve_string, bars=4, start=8, gain=0.11, at=0.3, octave=2, seed=7)
    for bar in (0, 8):
        s.add(inst.timpani(key.hz(chord_at(prog, bar), -1), 1.4, seed=bar), bar * 4, gain=0.1)
    return s.master(room=3.5, wet=0.35, damping=5000, rms=0.095, seed=25)


def battle_hells_gate(s: Score) -> np.ndarray:
    """The gate opens: everything at once, an apocalyptic march on brimstone. D phrygian over a D-Eb
    drone: war drums and taiko, a low bow on the flat second, organ clusters and monks, a falling choir
    line, and the village's own melody returning corrupted on the guitar. The boss takes it from here."""
    key, prog = Key("D2", "phrygian"), (0, 0, 1, 1, 0, 0, 6, 5)
    pedal(s, (key.hz(0, 0), key.hz(1, 0)), inst.drone, gain=0.07, span=4, seed=1)
    drums(s, DOOM_KIT, {"war": "x.....x...x.....", "heart": "........x......."}, bars=4, seed=2)
    drums(s, DOOM_KIT, {"war": "x.....x...x.....", "taiko": "....x.......x..x", "heart": "........x.......", "rattle": "..o...o...o...o."},
          bars=12, start=4, fill={"tom": "x.x.x.x.x.xxx.xx", "war": "x.....x...x....."}, seed=3)
    ostinato(s, key, prog, inst.cello, bars=16, gain=0.09, figure=(0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 4, 0, 1, 0), step=0.25, octave=0,
             ring=0.9, at=0.1, seed=4)
    arpeggio(s, key, prog, inst.twelve_string, bars=12, start=4, gain=0.13, at=-0.3, pattern=(0, 3, 2, 3, 4, 3, 2, 3), step=0.25, octave=1,
             ring=1.6, seed=5)
    pad(s, key, prog, inst.organ, bars=8, start=8, gain=0.06, octave=1, voicing=(0, 1, 4, 7), seed=6)
    pad(s, key, prog, inst.monks, bars=12, start=4, gain=0.07, octave=1, voicing=(0, 4), seed=7)
    line(s, key, prog, DESCENT, inst.hollow_choir, bars=8, start=8, gain=0.07, at=0.2, octave=2, phrase_bars=4, shapes=("A", "B"), seed=8)
    line(s, key, prog, TRISTRAM, inst.twelve_string, bars=4, start=12, gain=0.1, at=0.3, octave=2, shapes=("B", "A_end"), seed=9)
    for bar in range(0, 16, 4):
        s.add(inst.timpani(key.hz(chord_at(prog, bar), -1), 1.4, seed=bar), bar * 4, gain=0.12)
    bells(s, key, ((0.0, 0), (32.0, 1)), gain=0.08, length=5.0)
    return s.master(room=3.2, wet=0.32, damping=4200, rms=0.1, seed=26)


def battle_docks(s: Score) -> np.ndarray:
    """Kurast Docks: a harbour at night. Slow swell, low marimba ostinato, a bamboo flute, lapping water pulse."""
    key, prog = Key("G2", "aeolian"), (0, 0, 3, 3, 5, 5, 0, 4)
    pedal(s, (key.hz(0, 0), key.hz(4, 0)), inst.drone, gain=0.14, span=8, seed=1)
    drums(s, SWAMP_KIT, {"heart": "x...............", "water": "....o.......o..."}, bars=12, seed=2)
    drums(s, SWAMP_KIT, {"frame": "......o.......o.", "click": "..o...o...o...o."}, bars=6, start=6, seed=3)
    ostinato(s, key, prog, inst.twelve_string, bars=12, gain=0.12, figure=(0, None, 0, None, 4, None, 0, None), step=0.5, octave=0,
             ring=1.2, at=-0.2, seed=4)
    arpeggio(s, key, prog, inst.twelve_string, bars=6, start=6, gain=0.1, at=0.3, pattern=(0, 2, 4, 3, 2, 0), step=0.5, octave=2,
             ring=2.5, width=0.15, seed=5)
    pad(s, key, prog, inst.hollow_choir, bars=6, start=6, gain=0.05, octave=1, voicing=(0, 4, 7), width=0.4, seed=6)
    line(s, key, prog, TIDE, inst.twelve_string, bars=4, start=4, gain=0.11, at=0.25, octave=1, shapes=("A", "A_end"), seed=7)
    bells(s, key, ((0.0, 0), (24.0, 4)), gain=0.07, length=8.0)
    return s.master(room=5.5, wet=0.5, damping=3000, rms=0.08, seed=31)


def battle_spider_forest(s: Score) -> np.ndarray:
    """The Spider Forest: skittering. Plucked high strings in a whole-tone figure, dry clicking percussion."""
    key, prog = Key("B2", "phrygian_dominant"), (0, 0, 1, 1, 5, 4, 1, 0)
    pedal(s, (key.hz(0, 0), key.hz(1, 0)), inst.drone, gain=0.08, span=4, seed=1)
    drums(s, SPIDER_KIT, {"click": "x.x.x.x.x.x.x.x.", "tick": ".x.x.x.x.x.x.x.x"}, bars=16, seed=2)
    drums(s, SPIDER_KIT, {"frame": "....o.......o...", "tick": "..x...x...x...x."}, bars=8, start=8, seed=3)
    ostinato(s, key, prog, inst.twelve_string, bars=16, gain=0.18, at=-0.3, figure=(0, 2, 4, 6, 4, 2, 0, 2), step=0.25, octave=2,
             ring=1.0, seed=4)
    ostinato(s, key, prog, inst.twelve_string, bars=8, start=8, gain=0.09, figure=(0, 2, 4, 6, 4, 2, 0, 2), step=0.25, octave=2,
             ring=0.8, at=0.25, seed=5)
    pad(s, key, prog, inst.organ, bars=8, start=8, gain=0.04, octave=1, voicing=(0, 2, 4, 6), seed=6)
    line(s, key, prog, SKITTER, inst.twelve_string, bars=4, start=4, gain=0.1, at=0.3, octave=3, legato=0.5, shapes=("A", "A_end"), seed=7)
    bells(s, key, ((0.0, 0), (16.0, 2), (32.0, 4), (48.0, 1)), gain=0.05, length=4.0)
    return s.master(room=2.5, wet=0.25, damping=5500, rms=0.09, seed=32)


def battle_jungle(s: Score) -> np.ndarray:
    """The Flayer Jungle: hunting drums. Fast frame drums and log drums, a chanting low voice-like drone."""
    key, prog = Key("A2", "dorian"), (0, 0, 3, 3, 4, 4, 5, 5)
    pedal(s, (key.hz(0, 0), key.hz(4, 0)), inst.drone, gain=0.15, span=8, seed=1)
    drums(s, JUNGLE_KIT, {"frame": "x.x.x.x.x.x.x.x.", "heart": "........x......."}, bars=16, seed=2)
    drums(s, JUNGLE_KIT, {"log": "x...x...x...x...", "frame": "x.x.x.x.x.x.x.x.", "rattle": "..o...o...o...o."}, bars=8, start=8,
          fill={"log": "x.x.x.x.x.x.x.x.", "frame": "x.x.x.x.x.x.x.x."}, every=8, seed=3)
    ostinato(s, key, prog, inst.cello, bars=16, gain=0.1, figure=(0, 0, 4, 0, 0, 0, 5, 0, 0, 0, 4, 0, 0, 0, 5, 0), step=0.25, octave=0,
             ring=0.9, at=0.1, seed=4)
    pad(s, key, prog, inst.monks, bars=8, start=8, gain=0.08, octave=0, voicing=(0, 4, 7), width=0.3, seed=5)
    pad(s, key, prog, inst.hollow_choir, bars=8, start=8, gain=0.05, octave=1, voicing=(0, 2, 4), seed=6)
    line(s, key, prog, HUNT, inst.cello, bars=4, start=4, gain=0.12, at=0.2, octave=0, phrase_bars=2, shapes=("A", "B"), seed=7)
    arpeggio(s, key, prog, inst.twelve_string, bars=8, start=8, gain=0.08, at=-0.35, pattern=(0, 2, 3, 5, 4, 3), step=0.5, octave=1,
             ring=1.8, seed=8)
    for bar in range(0, 16, 4):
        s.add(inst.timpani(key.hz(chord_at(prog, bar), -1), 1.2, seed=bar), bar * 4, gain=0.1)
    return s.master(room=3.8, wet=0.35, damping=4500, rms=0.095, seed=33)


def battle_drowned_city(s: Score) -> np.ndarray:
    """The Drowned City: submerged. Detuned slow bells, a deep sub pulse, a sighing pad."""
    key, prog = Key("F#2", "phrygian"), (0, 0, 1, 6, 0, 0, 5, 4)
    pedal(s, (key.hz(0, 0), key.hz(1, 0)), inst.drone, gain=0.1, span=6, seed=1)
    drums(s, DROWNED_KIT, {"sub": "x..............."}, bars=12, seed=2)
    pad(s, key, prog, inst.organ, bars=12, gain=0.06, octave=0, voicing=(0, 1, 3, 7), overlap=2.5, seed=3)
    pad(s, key, prog, inst.hollow_choir, bars=12, gain=0.05, octave=1, voicing=(0, 3, 7), overlap=3.0, width=0.5, seed=4)
    for bar in range(12):
        if bar % 8 == 0:
            s.add(inst.church_bell(key.hz(0, 1), 10.0, seed=bar), bar * 4, at=0.3, gain=0.07)
        elif bar % 8 == 4:
            s.add(inst.church_bell(key.hz(1, 1), 10.0, seed=bar + 20), bar * 4, at=-0.3, gain=0.06)
    line(s, key, prog, SIGH, inst.hollow_choir, bars=6, start=6, gain=0.08, at=0.0, octave=1, legato=1.5, phrase_bars=3, shapes=("A", "A_end"), seed=7)
    bells(s, key, ((0.0, 0), (48.0, 1)), gain=0.06, length=10.0)
    return s.master(room=6.5, wet=0.55, damping=2500, rms=0.075, seed=34)


def battle_travincal(s: Score) -> np.ndarray:
    """Travincal: the council's terrace. A ceremonial processional, gongs, brass-like chords in phrygian, rising tension."""
    key, prog = Key("E2", "phrygian"), (0, 0, 5, 6, 0, 0, 1, 5)
    pedal(s, (key.hz(0, 0), key.hz(1, 0)), inst.drone, gain=0.12, span=8, seed=1)
    drums(s, TRAVINCAL_KIT, {"heart": "x.......x......."}, bars=16, seed=2)
    drums(s, TRAVINCAL_KIT, {"frame": "......o.......o."}, bars=8, start=8,
          fill={"frame": "......o...o.o.o."}, every=8, seed=3)
    pad(s, key, prog, inst.organ, bars=16, gain=0.08, octave=1, voicing=(0, 4, 7, 10, 14), overlap=1.5, seed=4)
    pad(s, key, prog, inst.monks, bars=8, start=8, gain=0.06, octave=1, voicing=(0, 4), seed=5)
    ostinato(s, key, prog, inst.cello, bars=8, start=8, gain=0.08, figure=(0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 4, 0, 1, 0), step=0.25, octave=0,
             ring=0.9, at=0.1, seed=6)
    arpeggio(s, key, prog, inst.twelve_string, bars=8, start=8, gain=0.1, at=-0.3, pattern=(0, 3, 2, 3, 4, 3, 2, 3), step=0.25, octave=1,
             ring=1.6, seed=7)
    line(s, key, prog, PROCESSION, inst.twelve_string, bars=8, start=8, gain=0.12, at=0.3, octave=2, phrase_bars=4, shapes=("A", "B"), seed=8)
    line(s, key, prog, PROCESSION, inst.organ, bars=4, start=12, gain=0.08, at=0.0, octave=1, phrase_bars=2, shapes=("A_end",), seed=9)
    bells(s, key, ((0.0, 0), (32.0, 4), (64.0, 1), (16.0, 1), (48.0, 1)), gain=0.08, length=6.0)
    for bar in (0, 8):
        s.add(inst.timpani(key.hz(chord_at(prog, bar), -1), 1.6, seed=bar), bar * 4, gain=0.12)
    return s.master(room=4.2, wet=0.4, damping=3800, rms=0.095, seed=35)


def battle_temple(s: Score) -> np.ndarray:
    """The Temple of Light: the last fight's approach. An organ-like drone with a golden major-minor shift, choir pad, a heartbeat pulse."""
    key, prog = Key("D2", "dorian"), (0, 0, 2, 2, 4, 4, 5, 5, 0, 0, 2, 2, 4, 4, 5, 5)
    pedal(s, (key.hz(0, 0), key.hz(4, 0), key.hz(6, 0)), inst.organ, gain=0.1, span=8, overlap=3.0, seed=1)
    drums(s, TEMPLE_KIT, {"heart": "x.......x......."}, bars=16, seed=2)
    drums(s, TEMPLE_KIT, {"frame": "......o.......o."}, bars=8, start=8, seed=3)
    pad(s, key, prog, inst.hollow_choir, bars=16, gain=0.07, octave=1, voicing=(0, 2, 4, 7, 9), overlap=2.0, width=0.4, seed=4)
    pad(s, key, prog, inst.organ, bars=8, start=8, gain=0.05, octave=1, voicing=(0, 4, 7, 11), seed=5)
    ostinato(s, key, prog, inst.twelve_string, bars=8, start=8, gain=0.08, figure=(0, None, 4, None, 6, None, 4, None), step=0.5, octave=1,
             ring=2.0, at=-0.2, seed=6)
    line(s, key, prog, GOLDEN, inst.hollow_choir, bars=8, start=8, gain=0.1, at=0.25, octave=2, legato=1.3, phrase_bars=4, shapes=("A", "B"), seed=7)
    line(s, key, prog, GOLDEN, inst.twelve_string, bars=4, start=12, gain=0.12, at=0.3, octave=2, shapes=("A_end",), seed=8)
    bells(s, key, ((0.0, 0), (32.0, 4), (64.0, 0)), gain=0.07, length=7.0)
    for bar in range(0, 16, 4):
        s.add(inst.timpani(key.hz(chord_at(prog, bar), -1), 1.4, seed=bar), bar * 4, gain=0.1)
    return s.master(room=5.0, wet=0.45, damping=3500, rms=0.095, seed=36)


def boss(s: Score) -> np.ndarray:
    """Azazel the Flayer: the last wave of Hell's Gate. War drums, a low bow hammering the flat second,
    an organ and monks in clusters, bells."""
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


PIECES: dict[str, Piece] = {
    "title": Piece(title, 64, 12),
    "battle_tristram": Piece(battle_tristram, 68, 16),
    "battle_graveyard": Piece(battle_graveyard, 60, 12),
    "battle_cathedral": Piece(battle_cathedral, 72, 16),
    "battle_catacombs": Piece(battle_catacombs, 66, 12),
    "battle_caves": Piece(battle_caves, 92, 16),
    "battle_hells_gate": Piece(battle_hells_gate, 84, 16),
    "battle_docks": Piece(battle_docks, 60, 12),
    "battle_spider_forest": Piece(battle_spider_forest, 100, 16),
    "battle_jungle": Piece(battle_jungle, 95, 16),
    "battle_drowned_city": Piece(battle_drowned_city, 50, 12),
    "battle_travincal": Piece(battle_travincal, 72, 16),
    "battle_temple": Piece(battle_temple, 65, 16),
    "boss": Piece(boss, 88, 20),
}

#: Every location's battle track, in the campaign's order.
BATTLE_FOR: dict[str, str] = {
    "tristram": "battle_tristram",
    "graveyard": "battle_graveyard",
    "cathedral": "battle_cathedral",
    "catacombs": "battle_catacombs",
    "caves": "battle_caves",
    "hells_gate": "battle_hells_gate",
    "docks": "battle_docks",
    "spider_forest": "battle_spider_forest",
    "jungle": "battle_jungle",
    "drowned_city": "battle_drowned_city",
    "travincal": "battle_travincal",
    "temple": "battle_temple",
}


def track_for(location_key: str) -> str:
    """The battle track for a location's key (``"tristram"`` → ``"battle_tristram"``)."""
    return BATTLE_FOR[location_key]
