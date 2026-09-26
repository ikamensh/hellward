"""The skill tree: tower columns of four skills and two columns of three, bought with sigils.

A skill needs the one above it in its column; the tower columns cost 1, 2, 2 and 3 sigils top to
bottom, Warding and Sorcery 1, 2 and 3. :func:`perks` turns a set of learned skills into
:class:`Perks`, every number and rule they change, which a :class:`~hellward.sim.model.World` reads
when a defence begins (:func:`tower_levels` bakes the tower modifiers into each kind's ranks once).
The second and third ranks of a tower are learned here: :attr:`Perks.ranks` holds, per tower kind,
the highest rank index that may be bought.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Final

from hellward.sim.content import DOOR, MANA_MAX, MANA_REGEN, SPELLS, TOWERS, TowerLevel
from hellward.sim.sums import int_sum


@dataclass(frozen=True)
class Skill:
    key: str
    name: str
    column: str
    tier: int            # 1 to 4, top to bottom; the price in sigils is `cost`
    cost: int
    blurb: str
    needs: tuple[str, ...] = ()   # what it works on (a tower kind, "gate" or a spell): it does nothing where none is offered


COLUMNS: dict[str, str] = {"fire": "Fire", "lightning": "Lightning", "cold": "Cold", "poison": "Poison",
                           "bone": "Bone", "nature": "Nature", "warding": "Warding", "sorcery": "Sorcery"}

SKILLS: dict[str, Skill] = {s.key: s for s in (
    Skill("adept_fire", "Adept of Fire", "fire", 1, 1, "Pyres can be raised to the second rank.", ("pyre",)),
    Skill("fire_ball", "Fire Ball", "fire", 2, 2, "A Pyre's first rank bursts into fireballs too, and every blast is 0.3 wider.", ("pyre",)),
    Skill("master_fire", "Master of Fire", "fire", 3, 2, "Pyres can be raised to the third rank.", ("pyre",)),
    Skill("blaze", "Blaze", "fire", 4, 3, "Fireballs leave the floor burning for 2 seconds.", ("pyre",)),
    Skill("adept_lightning", "Adept of Lightning", "lightning", 1, 1, "Storm Obelisks can be raised to the second rank.", ("storm",)),
    Skill("chain_lightning", "Chain Lightning", "lightning", 2, 2, "One more leap at every rank, and a leap keeps 95% of its strength.", ("storm",)),
    Skill("master_lightning", "Master of Lightning", "lightning", 3, 2, "Storm Obelisks can be raised to the third rank.", ("storm",)),
    Skill("static_field", "Static Field", "lightning", 4, 3, "Lightning strikes a leader in reach first, and leaps to leaders first.", ("storm",)),
    Skill("adept_cold", "Adept of Cold", "cold", 1, 1, "Frost Shrines can be raised to the second rank.", ("frost",)),
    Skill("glacial_spike", "Glacial Spike", "cold", 2, 2, "Frost novas reach 0.4 further and hit 50% harder.", ("frost",)),
    Skill("master_cold", "Master of Cold", "cold", 3, 2, "Frost Shrines can be raised to the third rank.", ("frost",)),
    Skill("shatter", "Shatter", "cold", 4, 3, "A monster that dies chilled bursts: a tenth of its life as cold to those around it.", ("frost",)),
    Skill("adept_poison", "Adept of Poison", "poison", 1, 1, "Plague Totems can be raised to the second rank.", ("plague",)),
    Skill("contagion", "Contagion", "poison", 2, 2, "When a poisoned monster dies, its venom leaps to the nearest monster.", ("plague",)),
    Skill("master_poison", "Master of Poison", "poison", 3, 2, "Plague Totems can be raised to the third rank.", ("plague",)),
    Skill("lower_resist", "Lower Resist", "poison", 4, 3, "A poisoned monster resists everything 25 points less. Immunities hold.", ("plague",)),
    Skill("adept_bone", "Adept of Bone", "bone", 1, 1, "Bone Altars can be raised to the second rank.", ("altar",)),
    Skill("corpse_explosion", "Corpse Explosion", "bone", 2, 2, "A monster that dies amplified bursts for 15% of its life, unresisted, within 1.2.", ("altar",)),
    Skill("master_bone", "Master of Bone", "bone", 3, 2, "Bone Altars can be raised to the third rank.", ("altar",)),
    Skill("life_tap", "Life Tap", "bone", 4, 3, "A monster that dies amplified gives a fifth of its bounty in mana.", ("altar",)),
    Skill("adept_nature", "Adept of Nature", "nature", 1, 1, "Druid Groves can be raised to the second rank.", ("grove",)),
    Skill("hurricane", "Hurricane", "nature", 2, 2, "Walkers within 2.5 tiles of a grove move 20% slower.", ("grove",)),
    Skill("master_nature", "Master of Nature", "nature", 3, 2, "Druid Groves can be raised to the third rank.", ("grove",)),
    Skill("twister", "Twister", "nature", 4, 3, "Every 4 s the grove roots the walker nearest the sanctuary within 2.5 tiles for 1.5 s.", ("grove",)),
    Skill("holy_shield", "Holy Shield", "warding", 1, 1, "Warded gates have 50% more life and mend fully between waves.", ("gate",)),
    Skill("salvation", "Salvation", "warding", 2, 2, "Cleanse costs 25 mana and wards the tower against curses for 8 seconds.", ("cleanse",)),
    Skill("thorns", "Thorns", "warding", 3, 3, "A gate returns half of each blow to the monster that strikes it, frost or no frost.", ("gate",)),
    Skill("warmth", "Warmth", "sorcery", 1, 1, "Mana flows 40% faster, and the orb holds 25 more."),
    Skill("soul_harvest", "Soul Harvest", "sorcery", 2, 2, "Every slain leader gives 10 mana."),
    Skill("spell_mastery", "Spell Mastery", "sorcery", 3, 3, "Smite, Meteor and Frozen Orb cost 25% less and strike 30% harder.", ("smite", "meteor", "orb")),
)}

TREE_COST = int_sum(s.cost for s in SKILLS.values())


def above(skill: Skill) -> Skill | None:
    """The skill a skill needs: the one above it in its column."""
    for other in SKILLS.values():
        if other.column == skill.column and other.tier == skill.tier - 1:
            return other
    return None


def cost(learned: Iterable[str]) -> int:
    return int_sum(SKILLS[key].cost for key in learned)


def can_learn(learned: frozenset[str], key: str, sigils: int) -> bool:
    skill = SKILLS[key]
    needed = above(skill)
    return key not in learned and (needed is None or needed.key in learned) and cost(learned) + skill.cost <= sigils


def check(learned: frozenset[str]) -> None:
    """Raise ValueError unless every learned skill has the one above it."""
    for key in learned:
        needed = above(SKILLS[key])
        if needed is not None and needed.key not in learned:
            raise ValueError(f"{SKILLS[key].name} needs {needed.name}")


RANK_SKILL: Final[dict[str, tuple[str, str]]] = {
    "pyre": ("adept_fire", "master_fire"),
    "storm": ("adept_lightning", "master_lightning"),
    "frost": ("adept_cold", "master_cold"),
    "plague": ("adept_poison", "master_poison"),
    "altar": ("adept_bone", "master_bone"),
    "grove": ("adept_nature", "master_nature"),
}


@dataclass(frozen=True)
class Perks:
    """Every number and rule the learned skills change; the defaults are the untrained game."""

    ranks: tuple[tuple[str, int], ...] = ()
    fire_ball: bool = False
    blaze: bool = False
    extra_leaps: int = 0
    leap_keeps: float = 0.85
    static_field: bool = False
    frost_reach: float = 0.0
    frost_damage: float = 1.0
    shatter: bool = False
    contagion: bool = False
    lower_resist: bool = False
    corpse_explosion: bool = False
    life_tap: bool = False
    hurricane: bool = False
    twister: bool = False
    gate_life: float = DOOR.hp
    gate_mend: float = DOOR.repair
    cleanse_cost: float = SPELLS["cleanse"].mana
    salvation: bool = False
    thorns: bool = False
    mana_max: float = MANA_MAX
    mana_regen: float = MANA_REGEN
    soul_harvest: bool = False
    spell_cost: float = 1.0      # Smite, Meteor and Frozen Orb
    spell_power: float = 1.0

    def top(self, kind: str) -> int:
        """The highest rank index of this tower kind that may be bought (0 = only the first rank)."""
        for name, rank in self.ranks:
            if name == kind:
                return rank
        return 0


NO_PERKS: Final = Perks()


def perks(learned: Iterable[str]) -> Perks:
    chosen = frozenset(learned)
    check(chosen)
    p = NO_PERKS
    tops: dict[str, int] = {}
    for kind, (adept, master) in RANK_SKILL.items():
        if adept in chosen:
            tops[kind] = 1
        if master in chosen:
            tops[kind] = 2
    if tops:
        p = replace(p, ranks=tuple(sorted(tops.items())))
    if "fire_ball" in chosen:
        p = replace(p, fire_ball=True)
    if "blaze" in chosen:
        p = replace(p, blaze=True)
    if "chain_lightning" in chosen:
        p = replace(p, extra_leaps=1, leap_keeps=0.95)
    if "static_field" in chosen:
        p = replace(p, static_field=True)
    if "glacial_spike" in chosen:
        p = replace(p, frost_reach=0.4, frost_damage=1.5)
    if "shatter" in chosen:
        p = replace(p, shatter=True)
    if "contagion" in chosen:
        p = replace(p, contagion=True)
    if "lower_resist" in chosen:
        p = replace(p, lower_resist=True)
    if "corpse_explosion" in chosen:
        p = replace(p, corpse_explosion=True)
    if "life_tap" in chosen:
        p = replace(p, life_tap=True)
    if "hurricane" in chosen:
        p = replace(p, hurricane=True)
    if "twister" in chosen:
        p = replace(p, twister=True)
    if "holy_shield" in chosen:
        p = replace(p, gate_life=DOOR.hp * 1.5, gate_mend=1.0)
    if "salvation" in chosen:
        p = replace(p, cleanse_cost=25.0, salvation=True)
    if "thorns" in chosen:
        p = replace(p, thorns=True)
    if "warmth" in chosen:
        p = replace(p, mana_max=MANA_MAX + 25, mana_regen=MANA_REGEN * 1.4)
    if "soul_harvest" in chosen:
        p = replace(p, soul_harvest=True)
    if "spell_mastery" in chosen:
        p = replace(p, spell_cost=0.75, spell_power=1.3)
    return p


_BAKED: Final[dict[Perks, dict[str, tuple[TowerLevel, ...]]]] = {}


def baked(p: Perks) -> dict[str, tuple[TowerLevel, ...]]:
    """Every tower kind's ranks with the perks in them, worked out once per set of perks: every world begins with
    them, and so does every clone the planner looks ahead in. Nothing changes them."""
    found = _BAKED.get(p)
    if found is None:
        found = _BAKED[p] = {kind: tower_levels(kind, p) for kind in TOWERS}
    return found


def tower_levels(kind: str, p: Perks) -> tuple[TowerLevel, ...]:
    """A tower kind's ranks with the perks baked in."""
    ranks = TOWERS[kind].levels
    if kind == "pyre":
        splash = [0.8, ranks[1].splash + 0.3, ranks[2].splash + 0.3] if p.fire_ball else [r.splash for r in ranks]
        return tuple(replace(r, splash=splash[i]) for i, r in enumerate(ranks))
    if kind == "storm":
        return tuple(replace(r, chains=r.chains + p.extra_leaps) for r in ranks)
    if kind == "frost":
        return tuple(replace(r, damage=r.damage * p.frost_damage, range=r.range + p.frost_reach) for r in ranks)
    if kind in ("plague", "altar", "grove"):
        return tuple(ranks)
    raise KeyError(kind)
