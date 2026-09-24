"""Hellward's consort: a detuned twelve-string, drones, distant voices, an organ, bells and low drums.

Pitched voices take a note name or a frequency and a length in seconds and return a mono clip
whose peak is near one; the score sets the gain.  Drums take only a seed.  Every function is
deterministic for a given *seed*, so a cached track is reproducible.  The choir, cello and drums
are adapted from Warband's orchestra; the twelve-string, the church bell and the heartbeat are
Hellward's own.
"""

from __future__ import annotations

import numpy as np

from sagaforge.synth import AH, OH, OO, formant, hz, level, lowpass, mix, noise, pluck, seconds, sustained, thump, tone

SAW = tuple((k, 1 / k) for k in range(1, 13))
REED = tuple((k, 1 / k) for k in range(1, 14, 2))  # odd harmonics: a stopped organ pipe
#: A cast bell's partials (hum, prime, minor-third tierce, quint, nominal, superquint, octave nominal)
#: as (ratio to the strike note, level, share of the decay time).
CHURCH_BELL = ((0.5, 0.55, 1.0), (1.0, 0.7, 0.55), (1.19, 0.5, 0.4), (1.5, 0.3, 0.3), (2.0, 0.45, 0.3), (2.66, 0.18, 0.18), (4.0, 0.08, 0.1))

Note = str | float


def _freq(note: Note) -> float:
    return hz(note) if isinstance(note, str) else float(note)


# -- Plucked ---------------------------------------------------------------------


def twelve_string(note: Note, length: float, *, seed: int = 0) -> np.ndarray:
    """A worn twelve-string: each course a pair a few cents apart, the lower ones with an octave
    string above, a dull pick and a long ring; the Tristram guitar."""
    f = _freq(note)
    course = mix(pluck(f, length, brightness=0.45, tau=1.4, seed=seed),
                 pluck(f * 2 ** (7 / 1200), length, brightness=0.4, tau=1.2, seed=seed + 1) * 0.7)
    if f < 330:  # the four low courses carry an octave string
        course = mix(course, pluck(2 * f * 2 ** (-5 / 1200), length, brightness=0.35, tau=0.9, seed=seed + 2) * 0.35)
    pick = noise(0.015, 1500, 6000, attack=0.001, tau=0.004, seed=seed + 3) * 0.08
    return level(lowpass(mix(course, pick), 5200), 1.0)


# -- Held -----------------------------------------------------------------------


def drone(note: Note, length: float, *, attack: float = 2.0, seed: int = 0) -> np.ndarray:
    """A bowed low drone: two detuned saws, very slow swell, darkened; the floor of every piece."""
    voice = sustained(note, length, partials=SAW, attack=attack, release=attack, vibrato=(0.2, 0.002), voices=3, detune=0.003, seed=seed)
    return lowpass(voice, 900)


def cello(note: Note, length: float, *, attack: float = 0.3, seed: int = 0) -> np.ndarray:
    voice = sustained(note, length, partials=SAW, attack=attack, release=0.4, vibrato=(4.6, 0.004), voices=2, detune=0.003, seed=seed)
    return lowpass(voice, 1500)


def organ(note: Note, length: float, *, attack: float = 0.12, seed: int = 0) -> np.ndarray:
    """A church organ: a stopped flute rank and an octave above it, no vibrato, a slow wind attack."""
    voice = mix(sustained(note, length, partials=REED, attack=attack, release=0.3, voices=2, detune=0.0015, seed=seed),
                sustained(2 * _freq(note), length, partials=((1, 1.0), (2, 0.3)), attack=attack, release=0.3, seed=seed + 1) * 0.35)
    return lowpass(voice, 3000) + noise(length, 800, 3000, attack=attack, tau=length, seed=seed + 2) * 0.01


def choir(note: Note, length: float, *, vowel=AH, attack: float = 0.6, seed: int = 0) -> np.ndarray:
    """Voices on a vowel: four detuned singers shaped by formants, soft and far."""
    voice = sustained(note, length, partials=SAW[:10], attack=attack, release=0.8, vibrato=(4.2, 0.005), voices=4, detune=0.007, seed=seed)
    return lowpass(formant(voice, vowel), 3500)


def monks(note: Note, length: float, *, seed: int = 0) -> np.ndarray:
    return choir(note, length, vowel=OH, attack=0.8, seed=seed)


def hollow_choir(note: Note, length: float, *, seed: int = 0) -> np.ndarray:
    """The distant voices of the cathedral pads: an ``oo`` with breath in it."""
    return choir(note, length, vowel=OO, attack=1.2, seed=seed) + noise(length, 500, 2500, attack=1.0, tau=length, seed=seed + 7) * 0.02


# -- Struck -----------------------------------------------------------------------


def church_bell(note: Note, length: float, *, seed: int = 0) -> np.ndarray:
    """A cast bronze bell: a hum an octave under the strike, a minor-third tierce, a clang on top."""
    f = _freq(note)
    t = seconds(length)
    rng = np.random.default_rng(seed)
    out = np.zeros_like(t)
    for ratio, amp, share in CHURCH_BELL:
        if f * ratio < 18000:
            beat = 1 + 0.08 * np.sin(2 * np.pi * rng.uniform(0.6, 1.8) * t + rng.uniform(0, 6.3))  # a real bell's partials beat slowly
            out += amp * beat * np.exp(-t / (length * share * 0.45)) * np.sin(2 * np.pi * f * ratio * t + rng.uniform(0, 6.3))
    strike = noise(0.03, 1500, 8000, attack=0.001, tau=0.008, seed=seed) * 0.25
    attack = np.minimum(1.0, t / 0.002)
    tail = min(len(t), 220)
    out[-tail:] *= np.linspace(1.0, 0.0, tail)
    return level(mix(out * attack, strike), 1.0)


def chime(note: Note, length: float, *, seed: int = 0) -> np.ndarray:
    return tone(note, length, attack=0.003, tau=length * 0.35, partials=((1, 1.0), (2.76, 0.4), (5.4, 0.2), (8.9, 0.08)))


# -- Drums -----------------------------------------------------------------------


def heartbeat(seed: int = 0) -> np.ndarray:
    """Lub-dub: a deep felt thump and a softer one a quarter-second later."""
    lub = mix(thump(70, 38, 0.35, attack=0.006, tau=0.09), noise(0.05, 60, 400, attack=0.004, tau=0.02, seed=seed) * 0.3)
    dub = mix(thump(62, 36, 0.3, attack=0.006, tau=0.07), noise(0.04, 60, 350, attack=0.004, tau=0.015, seed=seed + 1) * 0.25)
    return level(mix(lub, (0.26, dub * 0.65)), 1.0)


def war_drum(seed: int = 0) -> np.ndarray:
    """A big low drum that shakes the floor."""
    return level(mix(thump(82, 44, 0.6, attack=0.004, tau=0.14), noise(0.12, 90, 900, tau=0.045, seed=seed) * 0.5), 1.0)


def taiko(seed: int = 0) -> np.ndarray:
    return level(mix(thump(95, 48, 0.5, attack=0.003, tau=0.12),
                     tone(140, 0.4, attack=0.003, tau=0.06, partials=((1, 0.6), (1.59, 0.35), (2.14, 0.2))) * 0.5,
                     noise(0.08, 150, 1400, tau=0.03, seed=seed) * 0.5), 1.0)


def tom(seed: int = 0, *, pitch: float = 120.0) -> np.ndarray:
    return level(mix(thump(pitch * 1.4, pitch * 0.7, 0.35, tau=0.12), noise(0.02, 300, 2500, tau=0.008, seed=seed) * 0.3), 1.0)


def frame_drum(seed: int = 0) -> np.ndarray:
    return level(mix(thump(160, 85, 0.25, tau=0.08), noise(0.03, 400, 2500, tau=0.01, seed=seed) * 0.4), 1.0)


def rattle(seed: int = 0) -> np.ndarray:
    """Dry bones shaken: a short gritty burst."""
    return noise(0.08, 1800, 6000, attack=0.01, tau=0.025, seed=seed)


def timpani(note: Note, length: float = 1.2, *, seed: int = 0) -> np.ndarray:
    f = _freq(note)
    return level(mix(thump(f * 1.3, f, length, attack=0.003, tau=length * 0.18),
                     tone(f, length, attack=0.003, tau=length * 0.25, partials=((1, 1.0), (1.5, 0.5), (1.98, 0.3), (2.44, 0.15))) * 0.6,
                     noise(0.04, 200, 2000, tau=0.012, seed=seed) * 0.25), 1.0)
