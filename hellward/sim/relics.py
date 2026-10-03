"""The run's relics, won a location at a time, and the verbs they read.

A verb is an event in the player's own engine — a tower raised, a rank bought, a spell cast, a curse
landing, a monster reaching the shrine. Each happens a handful to a few dozen times a wave, every
occurrence visible on the field, and the player sets how often through the build and where towers stand.
Most relics read one verb and write another: a count fires them (no chance), and leaning into the verb
costs something the relic turns into the payoff.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Final

VERBS: Final = ("build", "upgrade", "cast", "curse", "leak", "charge")


@dataclass(frozen=True)
class Relic:
    key: str
    name: str
    words: str        # the camp's offer and the held relic's line, written out
    verb: str         # the verb read, or "" for the still ones (Canticle, Hoarder's Seal)
    every: int        # the count that fires it
    writes: str       # the verb the firing feeds, through gold, mana or directly; "" for none


RELICS: Final[dict[str, Relic]] = {
    key: Relic(key, *row) for key, row in {
        "tithe": ("The Mason's Tithe", "Every 6th tower stands free.", "build", 6, "build"),
        "scaffold": ("The Scaffold", "Every 3rd tower raised pays 25 gold.", "build", 3, "build"),
        "whetstone": ("The Whetstone", "Every 2nd rank costs half.", "upgrade", 2, "upgrade"),
        "masterwork": ("The Masterwork", "Every 3rd rank wells 25 mana.", "upgrade", 3, "cast"),
        "trance": ("The Battle Trance", "Each cast quickens every tower for 6 s.", "cast", 1, ""),
        "deep_well": ("The Deep Well", "Every 2nd cast costs half its mana.", "cast", 2, "cast"),
        "spite": ("The Spite", "Every 2nd curse landing wells 15 mana.", "curse", 2, "cast"),
        "martyr": ("The Martyr", "Every 3rd curse landing pays 30 gold.", "curse", 3, "build"),
        "blood_money": ("The Blood Money", "Each leak pays 12 gold a life — and costs 1 life more.",
                        "leak", 1, "build"),
        "canticle": ("The Canticle", "Battle Hymn may be sung every defence; the well holds 10 less.",
                     "", 0, "cast"),
        "bell": ("The Martyr's Bell", "When the shrine is struck, every tower gains a charge; the well"
                 " loses 15 mana.", "leak", 1, "charge"),
        "hoard": ("The Hoarder's Seal", "An attuned tower with full charges reaches 1 further.",
                  "", 0, ""),
        "candle": ("The Martyr's Candle", "Every 3rd curse landing answers its caster with a smite.",
                   "curse", 3, "cast"),
        "volatile": ("The Volatile", "Every 6th charge spent or given casts a smite on the foremost.",
                     "charge", 6, "cast"),
        "temper": ("The Tempering", "Every 3rd rank bought attunes its tower free.", "upgrade", 3,
                   "charge"),
        "bellows": ("The Bellows", "Every 5th tower raised wells 20 mana; the well holds 10 less.",
                    "build", 5, "cast"),
        "lodestone": ("The Lodestone", "Every 4th tower raised attunes it free.", "build", 4,
                      "charge"),
        "stormglass": ("The Stormglass", "Every 5th cast gives every attuned tower a charge.",
                       "cast", 5, "charge"),
    }.items()
}

TITHE_EVERY: Final = 6
SCAFFOLD_EVERY: Final = 3
SCAFFOLD_GOLD: Final = 25
WHETSTONE_EVERY: Final = 2
MASTERWORK_EVERY: Final = 3
MASTERWORK_MANA: Final = 25.0
TRANCE_RATE: Final = 1.25
TRANCE_TIME: Final = 6.0
DEEP_WELL_EVERY: Final = 2
SPITE_EVERY: Final = 2
SPITE_MANA: Final = 15.0
MARTYR_EVERY: Final = 3
MARTYR_GOLD: Final = 30
BLOOD_GOLD: Final = 12
BLOOD_LIVES: Final = 1
CANTICLE_WELL: Final = 10.0
BELL_MANA: Final = 15.0
HOARD_REACH: Final = 1.0
CANDLE_EVERY: Final = 3
VOLATILE_EVERY: Final = 6
TEMPER_EVERY: Final = 3
BELLOWS_EVERY: Final = 5
BELLOWS_MANA: Final = 20.0
BELLOWS_WELL: Final = 10.0
LODESTONE_EVERY: Final = 4
STORMGLASS_EVERY: Final = 5
OFFER_N: Final = 3   # the camp's choice after a held location


def draw(seed: int, index: int, held: tuple[str, ...]) -> tuple[str, ...]:
    """The camp's offer after the run's `index`-th location: up to three relics not already held,
    drawn by the run's seed, in the table's order."""
    rng = random.Random(f"relics:{seed}:{index}")
    pool = [key for key in RELICS if key not in held]
    return tuple(sorted(rng.sample(pool, min(OFFER_N, len(pool))), key=pool.index))
