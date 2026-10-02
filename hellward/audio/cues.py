"""Every cue the game plays, by name: physical sounds composed from the generated pieces, tonal and
magical ones synthesised.

A :class:`Cue` has one or more takes; ``CUES[name].render(take)`` returns a finished clip (44.1 kHz,
mono or stereo) levelled to the cue's loudness, faded in and out so it cannot click.  A cue with
one take is written as ``<name>.wav``, one with several as ``<name>_<take>.wav``; the bank picks
the take.  Physical events with stages follow Warband's deaths: the cry, then the body landing a
fixed gap later, the takes rotated against each other so no two cues share a whole fall.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from hellward.audio import instruments as inst
from hellward.audio import pieces
from sagaforge.synth import AH, DARK, OH, OO, SAMPLE_RATE, formant, level, lowpass, mix, noise, reverb, seconds, thump, tone

#: Loudness targets: the loudest 50 ms of a cue has this RMS (see :func:`loudness`).  Four battle
#: cues landing together stay under full scale; interface cues sit well under the fight.
UI, ACTION, BATTLE, ALERT = 0.06, 0.1, 0.11, 0.16
#: Budget classes and their highest peak: ``battle`` cues share the bank's voice budget, so up to four
#: land together and each keeps its peak low; the rest always play, one or two at a time.
PEAKS = {"ui": 0.5, "action": 0.8, "battle": 0.55, "alert": 0.9}


@dataclass(frozen=True)
class Cue:
    make: Callable[[int], np.ndarray]
    takes: int
    kind: str
    loud: float
    pitch: float = 0.0   # ± share of random pitch variation per play
    yields: int = 0      # voices of the battle budget this cue leaves free for more telling ones (a death over a cast)

    def __post_init__(self) -> None:
        if self.kind not in PEAKS:
            raise ValueError(f"kind must be one of {tuple(PEAKS)}, not {self.kind!r}")

    def render(self, take: int) -> np.ndarray:
        if not 0 <= take < self.takes:
            raise ValueError(f"take {take} out of range 0..{self.takes - 1}")
        return finish(self.make(take), self.loud, PEAKS[self.kind])

    def files(self, name: str) -> list[str]:
        """The file stems this cue is written as."""
        return [name] if self.takes == 1 else [f"{name}_{take}" for take in range(self.takes)]


# -- Levels and edges ----------------------------------------------------------------


def loudness(clip: np.ndarray) -> float:
    """The RMS of the loudest 50 ms: how loud a cue sounds at its peak moment."""
    x = clip.mean(axis=1) if clip.ndim == 2 else clip
    window = int(0.05 * SAMPLE_RATE)
    if len(x) <= window:
        return float(np.sqrt(np.mean(x ** 2)))
    power = np.convolve(x ** 2, np.ones(window) / window, mode="valid")
    return float(np.sqrt(power.max()))


def finish(clip: np.ndarray, loud: float, cap: float) -> np.ndarray:
    """Level to *loud* with the peak held under *cap*, with a 3 ms fade in and 30 ms fade out."""
    out = clip * (loud / loudness(clip))
    peak = float(np.abs(out).max())
    if peak > cap:
        out *= cap / peak
    head = int(0.003 * SAMPLE_RATE)
    ramp = np.linspace(0, 1, head)
    out[:head] *= ramp[:, None] if out.ndim == 2 else ramp
    return fade(out, 0.03)


def fade(clip: np.ndarray, length: float) -> np.ndarray:
    """A cosine fade over the last *length* seconds."""
    n = min(len(clip), int(length * SAMPLE_RATE))
    ramp = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, n))
    out = clip.copy()
    out[-n:] *= ramp[:, None] if out.ndim == 2 else ramp
    return out


def cut(clip: np.ndarray, length: float, tail: float = 0.06) -> np.ndarray:
    """The first *length* seconds, fading over the last *tail*: the first blow of a piece that has two."""
    return fade(clip[:int(length * SAMPLE_RATE)], tail)


def room(clip: np.ndarray, decay: float, wet: float, *, seed: int = 0) -> np.ndarray:
    """A stone room around a one-shot; the tail is kept and faded."""
    return fade(reverb(clip, decay=decay, mix=wet, damping=4500, seed=seed), 0.4)


def glide(f0: float, f1: float, length: float, *, partials=((1, 1.0),), vibrato: tuple[float, float] = (5.0, 0.0), seed: int = 0) -> np.ndarray:
    """A tone sliding exponentially from *f0* to *f1* Hz, with vibrato; no envelope."""
    t = seconds(length)
    rng = np.random.default_rng(seed)
    rate, depth = vibrato
    freq = f0 * (f1 / f0) ** (t / length) * (1 + depth * np.sin(2 * np.pi * rate * t + rng.uniform(0, 6.3)))
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    out = sum(amp * np.sin(k * phase + rng.uniform(0, 6.3)) for k, amp in partials if f0 * k < 18000 and f1 * k < 18000)
    return out / sum(amp for _, amp in partials)


def shape(length: float, attack: float, release: float) -> np.ndarray:
    """A raised-cosine swell in and out over a held middle."""
    t = seconds(length)
    env = np.ones_like(t)
    env *= np.where(t < attack, 0.5 - 0.5 * np.cos(np.pi * t / max(attack, 1e-6)), 1.0)
    start = length - release
    env *= np.where(t > start, 0.5 + 0.5 * np.cos(np.pi * np.minimum(t - start, release) / max(release, 1e-6)), 1.0)
    return env


def sputter(length: float, low: float, high: float, *, rate: float, seed: int) -> np.ndarray:
    """Band noise chopped into random bursts: crackle, sparks, a sputtering flame."""
    rng = np.random.default_rng(seed)
    n = int(length * SAMPLE_RATE)
    gate = np.zeros(n)
    at = 0
    while at < n:
        on = int(rng.uniform(0.002, 0.012) * SAMPLE_RATE)
        gate[at:at + on] = rng.uniform(0.3, 1.0)
        at += on + int(rng.exponential(1 / rate) * SAMPLE_RATE)
    return noise(length, low, high, attack=0.001, tau=length, seed=seed) * lowpass(gate, 400)


# -- Interface -----------------------------------------------------------------------


def click(_: int) -> np.ndarray:
    """A dry wooden tick with a dull glint."""
    return mix(thump(1400, 700, 0.03, attack=0.0005, tau=0.008), noise(0.03, 2000, 7000, attack=0.0005, tau=0.005, seed=1) * 0.5,
               tone(1318.5, 0.06, attack=0.001, tau=0.015, partials=DARK) * 0.3)


def refuse(_: int) -> np.ndarray:
    """A muted low thunk, twice, the second a tone lower: not here, not now."""
    def thunk(f: float, seed: int) -> np.ndarray:
        return mix(thump(f * 1.6, f, 0.16, attack=0.002, tau=0.04), tone(f, 0.16, attack=0.002, tau=0.05, partials=DARK) * 0.5,
                   noise(0.04, 150, 900, tau=0.012, seed=seed) * 0.3)
    return lowpass(mix(thunk(130, 1), (0.1, thunk(110, 2) * 0.7)), 1800)


def upgrade(_: int) -> np.ndarray:
    """A rising chime in D major, a little sparkle over it, in a small stone room."""
    notes = [(i * 0.075, inst.chime(n, 0.9) * g) for i, (n, g) in enumerate((("D5", 0.7), ("F#5", 0.75), ("A5", 0.85), ("D6", 1.0)))]
    return room(mix(*notes, (0.22, noise(0.5, 5000, 11000, attack=0.05, tau=0.15, seed=3) * 0.08)), 1.4, 0.3, seed=1)


def holy(_: int) -> np.ndarray:
    """Holy light: a bright glass cluster over a soft sung ``ah`` in A major, shimmering up."""
    bells = [(i * 0.04, inst.chime(f, 1.2) * 0.5) for i, f in enumerate(("A5", "C#6", "E6", "A6", "C#7"))]
    voices = mix(*(inst.choir(f, 1.1, attack=0.08, seed=i) * 0.35 for i, f in enumerate(("A4", "E5", "C#5"))))
    sparkle = sputter(1.0, 6000, 12000, rate=60, seed=4) * shape(1.0, 0.2, 0.6) * 0.25
    return room(mix(voices, *bells, sparkle), 1.8, 0.35, seed=2)


# -- Building ----------------------------------------------------------------------------


def build(take: int) -> np.ndarray:
    """A stone block ground into place, then set down."""
    grind = cut(pieces.take("stone_grind", take, 0.7), 0.75, 0.25)
    return mix(grind, (0.6, pieces.take("stone_thud", take, 0.9)))


def sell(take: int) -> np.ndarray:
    """The tower unseated, a short grind, and the refund chinking into the purse."""
    return mix(pieces.take("stone_thud", take + 1, 0.5), cut(pieces.take("stone_grind", take, 0.5), 0.35, 0.15),
               (0.22, pieces.take("coins", take, 0.8)))


def door_build(take: int) -> np.ndarray:
    """Three knocks of a mallet: the door hung and wedged."""
    return mix(*((i * 0.24, pieces.take("door_hammer", take + i, gain)) for i, gain in enumerate((0.7, 0.8, 1.0))))


def gold(take: int) -> np.ndarray:
    return pieces.take("coins", take)


# -- Doors ---------------------------------------------------------------------------------------


def door_hit(take: int) -> np.ndarray:
    """One blow on an iron-banded door; pieces that ring on with a second blow are cut to the first."""
    return cut(pieces.take("door_hit", take), 0.45)


def door_break(take: int) -> np.ndarray:
    """The last blow, the door bursting, the wreck clattering down and a thump under it all."""
    return mix(cut(pieces.take("door_hit", take + 2, 0.8), 0.3),
               (0.06, pieces.take("door_splinter", take, 0.95)),
               (0.06, thump(90, 38, 0.5, attack=0.002, tau=0.12) * 0.5),
               (0.4, pieces.take("door_debris", take + 1, 0.6)))


# -- Towers ----------------------------------------------------------------------------------------


def arrow_cast(take: int) -> np.ndarray:
    """A taut string snaps free with a little wood and feather, without a magical tail."""
    length = 0.15
    string = glide(690 + 45 * take, 240 + 20 * take, length,
                   partials=((1, 1.0), (2, 0.35), (3, 0.15)), seed=700 + take)
    string *= np.exp(-seconds(length) / 0.025)
    wood = thump(520, 170, 0.12, attack=0.0005, tau=0.022)
    feather = noise(0.11, 1300, 5200, attack=0.001, tau=0.022, seed=710 + take)
    return mix(string * 0.45, wood * 0.5, feather * 0.17)


def arrow_hit(take: int) -> np.ndarray:
    """A small dry shaft impact and a muted point strike."""
    point = thump(660 + 40 * take, 220, 0.13, attack=0.0005, tau=0.025)
    shaft = noise(0.11, 500, 3300, attack=0.0008, tau=0.018, seed=720 + take)
    body = thump(210, 95, 0.12, attack=0.001, tau=0.03)
    return mix(point * 0.55, shaft * 0.25, body * 0.25)


def fire_cast(take: int) -> np.ndarray:
    return pieces.take("fire_whoosh", take)


def fire_hit(take: int) -> np.ndarray:
    return pieces.take("fire_hit", take)


def fireball(take: int) -> np.ndarray:
    """A bolt landing and bursting: the hit, the blast on its heels and a low boom."""
    return mix(pieces.take("fire_hit", take, 0.6), (0.03, pieces.take("fire_blast", take, 0.9)),
               (0.03, thump(95, 36, 0.5, attack=0.003, tau=0.12) * 0.45))


def lightning(take: int) -> np.ndarray:
    """A crack of static, a buzzing zap falling in pitch, crackle trailing off, a dull thump under it."""
    rng = np.random.default_rng(300 + take)
    start = (1100, 850, 1400)[take]
    zap = glide(start, start * 0.22, 0.32, partials=tuple((k, 1 / k) for k in range(1, 9)), vibrato=(70, 0.05), seed=take)
    zap = zap * np.exp(-seconds(0.32) / 0.09)
    crack = noise(0.05, 2500, 12000, attack=0.0005, tau=0.01, seed=310 + take)
    crackle = sputter(0.45, 2000, 10000, rate=90, seed=320 + take) * np.exp(-seconds(0.45) / 0.15)
    return mix(crack * 0.8, zap * 0.5, (0.01, crackle * 0.7), thump(160, 50, 0.25, attack=0.001, tau=0.06) * 0.45,
               (rng.uniform(0.08, 0.14), crack * 0.35))


def frost(take: int) -> np.ndarray:
    """A frost nova: a burst of cold air, a glassy shimmer spilling outwards, ice cracking in it."""
    rng = np.random.default_rng(400 + take)
    scale = (1760.0, 1975.5, 2349.3, 2637.0, 2960.0, 3520.0, 3951.1, 4698.6)
    shimmer = mix(*((rng.uniform(0, 0.35), inst.chime(scale[rng.integers(len(scale))], rng.uniform(0.25, 0.5)) * rng.uniform(0.3, 0.7))
                    for _ in range(14)))
    air = noise(0.7, 2500, 10000, attack=0.04, tau=0.2, seed=410 + take)
    burst = thump(220, 90, 0.2, attack=0.002, tau=0.05)
    return mix(burst * 0.45, air * 0.35, (0.01, shimmer * 0.5), (0.02, pieces.take("ice_shatter", take, 0.55)))


def ballista_cast(take: int) -> np.ndarray:
    """The heavy arms thrown forward: a deep string slapping free, the frame knocking against its stops."""
    length = 0.3
    string = glide(260 + 18 * take, 85, length, partials=((1, 1.0), (2, 0.45), (3, 0.25), (4, 0.1)), seed=740 + take)
    string *= np.exp(-seconds(length) / 0.06)
    frame = mix(thump(240, 80, 0.25, attack=0.001, tau=0.05), (0.04, thump(180, 70, 0.2, attack=0.001, tau=0.04) * 0.6))
    rush = noise(0.22, 300, 2500, attack=0.01, tau=0.06, seed=750 + take)
    return mix(string * 0.5, frame * 0.6, rush * 0.2)


def ballista_hit(take: int) -> np.ndarray:
    """An iron-headed bolt driven home: a heavy blunt strike and the shaft shuddering."""
    blow = thump(380 + 30 * take, 95, 0.25, attack=0.0005, tau=0.05)
    shudder = glide(170, 120, 0.2, partials=((1, 1.0), (2, 0.3)), vibrato=(38, 0.06), seed=760 + take)
    shudder *= np.exp(-seconds(0.2) / 0.06)
    crack = noise(0.12, 600, 4500, attack=0.0005, tau=0.02, seed=770 + take)
    return mix(blow * 0.7, crack * 0.35, (0.01, shudder * 0.3))


def knife_cast(take: int) -> np.ndarray:
    """A knife leaving the hand, whirring end over end as it goes."""
    length = 0.24
    t = seconds(length)
    whirr = noise(length, 1400, 7000, attack=0.01, tau=length, seed=780 + take) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * (26 + 3 * take) * t)))
    return mix(whirr * shape(length, 0.04, 0.12), thump(900, 500, 0.05, attack=0.0005, tau=0.01) * 0.25)


def knife_hit(take: int) -> np.ndarray:
    """A blade biting home: a short bright tick of steel and a dull thud."""
    steel = tone(2400 + 200 * take, 0.12, attack=0.0005, tau=0.025, partials=((1, 1.0), (2.76, 0.4), (5.4, 0.2)))
    return mix(steel * 0.4, thump(420, 160, 0.1, attack=0.0005, tau=0.02) * 0.6,
               noise(0.06, 2000, 9000, attack=0.0005, tau=0.01, seed=790 + take) * 0.3)


def hook(take: int) -> np.ndarray:
    """A hook thrown on its chain: the links rattling out, the bite, and the haul scraping back."""
    rattle = sputter(0.3, 2200, 8000, rate=110, seed=800 + take) * shape(0.3, 0.02, 0.1)
    bite = mix(tone(1150 + 80 * take, 0.25, attack=0.0005, tau=0.05, partials=((1, 1.0), (2.4, 0.5), (4.1, 0.25))),
               thump(300, 110, 0.15, attack=0.0005, tau=0.03))
    haul = mix(noise(0.4, 180, 1400, attack=0.04, tau=0.2, seed=810 + take) * 0.6,
               sputter(0.4, 1500, 6000, rate=60, seed=820 + take) * shape(0.4, 0.05, 0.2) * 0.5)
    return mix(rattle * 0.6, (0.13, bite * 0.6), (0.18, haul))


def venom_cast(take: int) -> np.ndarray:
    """A wet spit and bubbles rising off it."""
    rng = np.random.default_rng(500 + take)
    bubbles = [(rng.uniform(0.02, 0.24), glide(f, f * 2.4, 0.045) * np.exp(-seconds(0.045) / 0.018))
               for f in rng.uniform(260, 620, 8)]
    spit = noise(0.14, 300, 3000, attack=0.003, tau=0.03, seed=510 + take)
    return mix(spit * 0.7, thump(140, 260, 0.08, attack=0.002, tau=0.03) * 0.4, *((at, b * 0.5) for at, b in bubbles))


def venom_hit(take: int) -> np.ndarray:
    """The splat, and the flesh hissing where it landed."""
    return mix(pieces.take("poison_splat", take, 0.85), (0.05, noise(0.45, 3000, 9000, attack=0.03, tau=0.14, seed=520 + take) * 0.2))


# -- Leaders ----------------------------------------------------------------------------------------


def ponder(_: int) -> np.ndarray:
    """A soft low breath through the teeth, and a murmur under it: a leader weighing its curse."""
    length = 0.9
    breath = lowpass(formant(noise(length, 200, 2500, attack=0.001, tau=length, seed=600), OO), 1400) * shape(length, 0.3, 0.45)
    murmur = glide(98, 92, length, partials=((1, 1.0), (2, 0.4), (3, 0.2)), vibrato=(5.0, 0.01)) * shape(length, 0.25, 0.4)
    return mix(level(breath, 1.0), lowpass(murmur, 900) * 0.4)


def chant(_: int) -> np.ndarray:
    """The curse being spoken: a low dissonant drone rising a third, and whispering over it."""
    length = 1.15
    env = shape(length, 0.25, 0.12)
    voices = [glide(f, f * 2 ** (4 / 12), length, partials=tuple((k, 1 / k) for k in range(1, 11)), vibrato=(4.5, 0.008), seed=i)
              for i, f in enumerate((73.4, 77.8, 103.8))]  # D, E flat, and the tritone over D
    drone = lowpass(formant(mix(*voices), OH), 2500) * env
    t = seconds(length)
    syllables = np.clip(np.sin(2 * np.pi * 5.5 * t + 1.3 * np.sin(2 * np.pi * 1.7 * t)), 0, 1) ** 2
    whisper = formant(noise(length, 900, 7000, attack=0.001, tau=length, seed=610), AH) * syllables * env
    return mix(level(drone, 1.0), level(whisper, 0.4))


def curse(_: int) -> np.ndarray:
    """The curse landing: a reversed swell sucks in to a dark impact that rings a low dissonance."""
    swell = (noise(0.22, 200, 5000, attack=0.001, tau=0.08, seed=620) * 0.5 + tone(146.8, 0.22, attack=0.001, tau=0.1, partials=DARK) * 0.3)[::-1]
    hit = mix(thump(120, 34, 0.7, attack=0.001, tau=0.14), noise(0.25, 60, 1500, attack=0.001, tau=0.05, seed=621) * 0.5)
    ring = mix(tone(73.4, 1.2, attack=0.004, tau=0.45, partials=((1, 1.0), (2, 0.5), (3, 0.3))),
               tone(77.8, 1.2, attack=0.004, tau=0.4, partials=((1, 0.8), (2, 0.4))) * 0.8)
    return room(mix(swell, (0.2, hit), (0.2, ring * 0.45)), 1.6, 0.35, seed=3)


def fizzle(_: int) -> np.ndarray:
    """A curse failing: the drone sags and gutters out in sparks."""
    length = 0.6
    sag = glide(420, 95, length, partials=((1, 1.0), (2, 0.5), (3, 0.3)), vibrato=(17, 0.04)) * np.exp(-seconds(length) / 0.2)
    sparks = sputter(length, 2000, 7000, rate=40, seed=630) * np.exp(-seconds(length) / 0.18)
    return mix(lowpass(sag, 2500) * 0.6, sparks * 0.5, noise(0.3, 400, 2000, attack=0.01, tau=0.1, seed=631) * 0.25)


# -- The player's spells -------------------------------------------------------------------------------


def smite(take: int) -> np.ndarray:
    """Holy lightning from the vault: the thunder crack, a deep blow under it, a bright sung chord blooming over it."""
    return mix(lightning(take) * 0.9, (0.01, thump(110, 38, 0.7, attack=0.001, tau=0.16) * 0.6), (0.05, holy(0) * 0.55))


def meteor_fall(_: int) -> np.ndarray:
    """A meteor coming down: a roar that swells and drops in pitch for the second before it lands."""
    length = 1.2
    roar = noise(length, 120, 2200, attack=length * 0.85, tau=0.08, seed=700)
    howl = glide(520, 140, length, partials=((1, 1.0), (2, 0.4), (3, 0.2)), vibrato=(9, 0.03), seed=701) * shape(length, 0.9, 0.08)
    return mix(roar * 0.7, lowpass(howl, 1800) * 0.25, sputter(length, 1500, 6000, rate=35, seed=702) * shape(length, 0.8, 0.1) * 0.3)


def meteor(take: int) -> np.ndarray:
    """The meteor landing: the blast, a ground-shaking boom, rubble falling after."""
    boom = mix(thump(70, 24, 1.3, attack=0.002, tau=0.35), noise(0.6, 40, 900, attack=0.001, tau=0.18, seed=710 + take) * 0.6)
    return room(mix(fireball(take), (0.01, boom * 0.9), (0.25, pieces.take("stone_crumble", take % 2, 0.5))), 1.4, 0.25, seed=take)


def orb(take: int) -> np.ndarray:
    """A frozen orb bursting: ice exploding outwards, the air freezing with a glassy ring."""
    ring = mix(*(inst.chime(f, 1.4) * 0.35 for f in (2349.3, 2793.8, 3520.0)))
    return mix(frost(take), (0.03, pieces.take("ice_shatter", (take + 1) % 3, 0.9)), thump(320, 110, 0.35, attack=0.001, tau=0.08) * 0.5,
               (0.08, ring))


def hymn(_: int) -> np.ndarray:
    """Battle Hymn over a tower: voices holding a bright E major chord, bells climbing it, a drumbeat under them."""
    bells = [(i * 0.05, inst.chime(f, 1.3) * 0.45) for i, f in enumerate(("E5", "G#5", "B5", "E6"))]
    hum = mix(*(inst.choir(f, 1.2, attack=0.15, seed=10 + i) * 0.3 for i, f in enumerate(("E4", "B4", "G#4"))))
    drum = mix(*((at, inst.timpani("E2", 0.5, seed=i) * 0.35) for i, at in enumerate((0.0, 0.32))))
    return room(mix(hum, *bells, drum), 1.6, 0.3, seed=5)


def returned(_: int) -> np.ndarray:
    """A boss struck back from the shrine: a holy blow, the thunder rolling away, the light ringing after it."""
    blow = mix(thump(120, 30, 1.0, attack=0.001, tau=0.25), noise(0.3, 60, 1200, attack=0.001, tau=0.08, seed=730) * 0.5)
    return room(mix(blow, (0.02, lightning(1) * 0.6), (0.08, holy(0) * 0.7)), 2.2, 0.4, seed=10)


# -- Waves and outcome ----------------------------------------------------------------------------------


def wave(take: int) -> np.ndarray:
    """The cathedral bell tolling a wave in, the stone ringing on after it."""
    return room(fade(pieces.take("bell", take), 0.5), 4.0, 0.55, seed=4 + take)


def cleared(_: int) -> np.ndarray:
    """A short chord of organ and voices that lands on the major: a breath between waves."""
    chord = ("D3", "F#3", "A3", "D4")
    organ = mix(*(inst.organ(n, 1.7, attack=0.08, seed=i) for i, n in enumerate(chord)))
    voices = mix(*(inst.choir(n, 1.7, attack=0.25, seed=i) for i, n in enumerate(("A3", "D4", "F#4"))))
    return room(mix(level(organ, 0.6), level(voices, 0.5)), 2.8, 0.45, seed=5)


def leak(_: int) -> np.ndarray:
    """Something got through: an ominous low gong blooming, and a far-off wail falling under it."""
    length = 3.2
    t = seconds(length)
    rng = np.random.default_rng(700)
    gong = np.zeros_like(t)
    for ratio, amp, bloom, decay in ((1.0, 1.0, 0.01, 1.6), (1.47, 0.6, 0.15, 1.2), (2.09, 0.5, 0.3, 1.0), (2.56, 0.4, 0.45, 0.9),
                                     (3.14, 0.3, 0.6, 0.8), (3.9, 0.2, 0.7, 0.6)):
        rise = 1 - np.exp(-t / bloom)
        gong += amp * rise * np.exp(-t / decay) * np.sin(2 * np.pi * 55.0 * ratio * t + rng.uniform(0, 6.3))
    strike = noise(0.08, 60, 800, attack=0.002, tau=0.03, seed=701)
    wail = formant(glide(587.3, 293.7, 1.8, partials=tuple((k, 1 / k ** 1.5) for k in range(1, 8)), vibrato=(5.5, 0.012), seed=2), OO)
    wail = wail * shape(1.8, 0.45, 0.8)
    return room(mix(level(gong, 1.0), strike * 0.4, (0.35, level(wail, 0.3))), 3.0, 0.45, seed=6)


def victory(_: int) -> np.ndarray:
    """Minor to major: organ and voices climb through B flat and C to a D major chord, and the bells ring."""
    changes = ((0.0, 1.1, ("D3", "F3", "A3", "D4")), (1.1, 1.0, ("D3", "F3", "A#3", "D4")), (2.1, 0.9, ("E3", "G3", "C4", "E4")),
               (3.0, 2.3, ("D3", "F#3", "A3", "D4", "F#4")))
    layers = []
    for at, length, chord in changes:
        layers.append((at, mix(*(inst.organ(n, length + 0.25, attack=0.1, seed=i) for i, n in enumerate(chord))) * 0.28))
        layers.append((at, mix(*(inst.choir(n, length + 0.3, attack=0.2, seed=i) for i, n in enumerate(chord[1:]))) * 0.3))
    layers += [(3.0, inst.church_bell("D4", 2.6, seed=1) * 0.35), (3.35, inst.church_bell("A4", 2.2, seed=2) * 0.25),
               (3.0, inst.timpani("D2", 1.4) * 0.5), (2.7, inst.timpani("A1", 0.6, seed=1) * 0.3)]
    return room(mix(*layers), 2.6, 0.4, seed=7)[:int(6.0 * SAMPLE_RATE)]


def defeat(_: int) -> np.ndarray:
    """The heart slows and stops under a falling bow and low voices; one toll at the end."""
    layers = [(i * 1.0, inst.cello(n, 1.3, attack=0.15, seed=i) * 0.35) for i, n in enumerate(("D3", "C3", "A#2", "A2"))]
    layers.append((0.0, mix(*(inst.hollow_choir(n, 4.2, seed=i) for i, n in enumerate(("D3", "F3", "A3")))) * 0.25))
    layers += [(at, inst.heartbeat(i) * g) for i, (at, g) in enumerate(((0.0, 0.8), (1.2, 0.6), (2.6, 0.4)))]
    layers += [(3.8, inst.church_bell("D3", 2.0, seed=3) * 0.45), (3.8, inst.cello("D2", 1.8, attack=0.1, seed=9) * 0.3)]
    return room(mix(*layers), 3.0, 0.45, seed=8)[:int(6.0 * SAMPLE_RATE)]


# -- Deaths --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Fall:
    """How a monster dies: its cry, then what lands, at *gap* seconds from the end of the cry (negative:
    under its last moment).  *cry* ``None`` is a death without a voice (bones collapsing)."""

    cry: str | None
    body: str
    gap: float = -0.12
    body_gain: float = 0.85
    boom: float = 0.0   # a synthesised sub-thump under the body, for the big ones
    longest: float = 0.0  # cut a long rumble (bones, rubble) to this many seconds; 0 keeps it whole
    takes: int = 3


FALLS: dict[str, Fall] = {
    # The painted deaths land well before these long cries end.  Let the body
    # sound meet the fallen sprite, with the last of the voice over its heap.
    "fallen": Fall("fallen_cry", "body_light", gap=-1.0),
    "skeleton": Fall(None, "bones", longest=1.8),
    "zombie": Fall("zombie_cry", "body_wet", gap=-1.0),
    "goatman": Fall("goatman_cry", "body_medium"),
    "gargoyle": Fall("gargoyle_cry", "stone_crumble", gap=-0.15, body_gain=0.8, longest=1.6),
    "overlord": Fall("overlord_cry", "body_heavy", gap=-0.2, body_gain=0.9, boom=0.35),
    "azazel": Fall("azazel_cry", "body_colossal", gap=-0.3, body_gain=0.95, boom=0.5, takes=2),
    "shaman": Fall("shaman_cry", "body_light", takes=2),
    "priest": Fall("priest_cry", "bones", gap=-0.15, body_gain=0.6, longest=1.4, takes=2),
    "witch": Fall("witch_cry", "body_medium", takes=2),
    # Act II borrows Act I's pieces, the nearest in body and voice, until its own foley is generated
    "flayer": Fall("fallen_cry", "body_light"),
    "zealot": Fall("priest_cry", "body_medium"),
    "spider": Fall("gargoyle_cry", "body_light", body_gain=0.7),
    "bat": Fall("gargoyle_cry", "body_light", body_gain=0.6),
    "hulk": Fall("overlord_cry", "body_heavy", gap=-0.2, body_gain=0.9, boom=0.35),
    "drowned": Fall("zombie_cry", "body_wet", gap=-0.2),
    "fetish": Fall("shaman_cry", "body_light", takes=2),
    "inquisitor": Fall("priest_cry", "body_medium", takes=2),
    "bone_priest": Fall("priest_cry", "bones", gap=-0.3, body_gain=0.95, boom=0.5, takes=2),
}
BOSSES = ("azazel", "bone_priest")   # their deaths are alerts, whole and unpitched, in a room


def death(kind: str, take: int) -> np.ndarray:
    """Cry *take*, faded as the fall lands, then the body (rotated one take against the cry)."""
    fall = FALLS[kind]
    body = pieces.take(fall.body, take if fall.cry is None else take + 1, fall.body_gain)
    if fall.longest and len(body) > fall.longest * SAMPLE_RATE:
        body = cut(body, fall.longest, 0.4)
    if fall.cry is None:
        return body
    cry = fade(pieces.take(fall.cry, take, 0.72), 0.15)
    at = max(0.0, len(cry) / SAMPLE_RATE + fall.gap)
    layers = [cry, (at, body)]
    if fall.boom:
        layers.append((at, thump(70, 28, 0.8, attack=0.004, tau=0.2) * fall.boom))
    out = mix(*layers)
    return room(out, 2.5, 0.3, seed=9) if kind in BOSSES else out


def _death(kind: str) -> Callable[[int], np.ndarray]:
    return lambda take: death(kind, take)


CUES: dict[str, Cue] = {
    "click": Cue(click, 1, "ui", UI),
    "refuse": Cue(refuse, 1, "ui", UI),
    "build": Cue(build, 2, "action", ACTION),
    "upgrade": Cue(upgrade, 1, "action", ACTION),
    "sell": Cue(sell, 2, "action", ACTION),
    "door_build": Cue(door_build, 2, "action", ACTION),
    "door_hit": Cue(door_hit, 4, "battle", BATTLE, pitch=0.04, yields=1),
    "door_break": Cue(door_break, 2, "alert", ALERT, pitch=0.03),
    "wave": Cue(wave, 2, "alert", ALERT),
    "cleared": Cue(cleared, 1, "alert", ALERT * 0.8),
    "leak": Cue(leak, 1, "alert", ALERT),
    "gold": Cue(gold, 3, "battle", ACTION * 0.8, pitch=0.04, yields=1),
    "ponder": Cue(ponder, 1, "alert", ACTION * 0.6),
    "chant": Cue(chant, 1, "alert", ACTION),
    "curse": Cue(curse, 1, "alert", ALERT),
    "fizzle": Cue(fizzle, 1, "alert", ACTION * 0.8),
    "arrow_cast": Cue(arrow_cast, 3, "battle", BATTLE * 0.58, pitch=0.04, yields=1),
    "arrow_hit": Cue(arrow_hit, 3, "battle", BATTLE * 0.7, pitch=0.04, yields=1),
    "fire_cast": Cue(fire_cast, 3, "battle", BATTLE * 0.8, pitch=0.04, yields=1),
    "fire_hit": Cue(fire_hit, 3, "battle", BATTLE, pitch=0.04, yields=1),
    "fireball": Cue(fireball, 3, "battle", BATTLE * 1.1, pitch=0.04, yields=1),
    "lightning": Cue(lightning, 3, "battle", BATTLE, pitch=0.04, yields=1),
    "frost": Cue(frost, 3, "battle", BATTLE, pitch=0.04, yields=1),
    "ballista_cast": Cue(ballista_cast, 3, "battle", BATTLE * 0.75, pitch=0.04, yields=1),
    "ballista_hit": Cue(ballista_hit, 3, "battle", BATTLE * 0.85, pitch=0.04, yields=1),
    "knife_cast": Cue(knife_cast, 3, "battle", BATTLE * 0.5, pitch=0.05, yields=1),
    "knife_hit": Cue(knife_hit, 3, "battle", BATTLE * 0.6, pitch=0.05, yields=1),
    "hook": Cue(hook, 2, "battle", BATTLE * 0.9, pitch=0.04),
    "venom_cast": Cue(venom_cast, 3, "battle", BATTLE * 0.8, pitch=0.04, yields=1),
    "venom_hit": Cue(venom_hit, 3, "battle", BATTLE, pitch=0.04, yields=1),
    "smite": Cue(smite, 3, "alert", ALERT * 0.9),
    "meteor_fall": Cue(meteor_fall, 1, "action", ACTION),
    "meteor": Cue(meteor, 2, "alert", ALERT),
    "orb": Cue(orb, 3, "alert", ALERT * 0.9),
    "hymn": Cue(hymn, 1, "action", ACTION),
    "returned": Cue(returned, 1, "alert", ALERT),
    "victory": Cue(victory, 1, "alert", ALERT),
    "defeat": Cue(defeat, 1, "alert", ALERT),
    **{f"death_{kind}": Cue(_death(kind), fall.takes, "alert" if kind in BOSSES else "battle",
                            ALERT if kind in BOSSES else BATTLE, pitch=0.0 if kind in BOSSES else 0.03)
       for kind, fall in FALLS.items()},
}


def files() -> dict[str, Callable[[], np.ndarray]]:
    """Every WAV the bank writes: file stem → its renderer."""
    return {stem: (lambda cue=cue, take=take: cue.render(take))
            for name, cue in CUES.items() for take, stem in enumerate(cue.files(name))}
