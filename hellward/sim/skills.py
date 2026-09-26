"""The skill tree: six columns of three skills, bought with sigils, and what the learned ones change.

A skill needs the one above it in its column; the tiers cost 1, 2 and 3 sigils. :func:`perks` turns a set of
learned skills into :class:`Perks`, every number and rule they change, which a :class:`~hellward.sim.model.World`
reads when a defence begins (:func:`tower_levels` bakes the tower modifiers into each kind's ranks once).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from hellward.sim.content import DOOR, MANA_MAX, MANA_REGEN, SPELLS, TOWERS, TowerLevel


@dataclass(frozen=True)
class Skill:
    key: str
    name: str
    column: str
    tier: int            # 1 to 3, top to bottom; a skill costs its tier in sigils
    blurb: str
    needs: tuple[str, ...] = ()   # what it works on (a tower kind, "gate" or a spell): it does nothing where none is offered

    @property
    def cost(self) -> int:
        return self.tier


COLUMNS: dict[str, str] = {"fire": "Fire", "lightning": "Lightning", "cold": "Cold", "poison": "Poison",
                           "warding": "Warding", "sorcery": "Sorcery"}

SKILLS: dict[str, Skill] = {s.key: s for s in (
    Skill("fire_mastery", "Fire Mastery", "fire", 1, "Pyres deal 25% more damage.", ("pyre",)),
    Skill("fire_ball", "Fire Ball", "fire", 2, "A Pyre's first rank bursts into fireballs too, and every blast is 0.3 wider.", ("pyre",)),
    Skill("blaze", "Blaze", "fire", 3, "Fireballs leave the floor burning for 2 seconds.", ("pyre",)),
    Skill("lightning_mastery", "Lightning Mastery", "lightning", 1, "Storm Obelisks deal 25% more damage.", ("storm",)),
    Skill("chain_lightning", "Chain Lightning", "lightning", 2, "One more leap at every rank, and a leap keeps 95% of its strength.", ("storm",)),
    Skill("static_field", "Static Field", "lightning", 3, "Lightning strikes a leader in reach first, and leaps to leaders first.", ("storm",)),
    Skill("cold_mastery", "Cold Mastery", "cold", 1, "Frost chills 10 points deeper and 30% longer.", ("frost",)),
    Skill("glacial_spike", "Glacial Spike", "cold", 2, "Frost novas reach 0.4 further and hit 50% harder.", ("frost",)),
    Skill("shatter", "Shatter", "cold", 3, "A monster that dies chilled bursts: a tenth of its life as cold to those around it.", ("frost",)),
    Skill("poison_mastery", "Poison Mastery", "poison", 1, "Venom is 30% stronger.", ("plague",)),
    Skill("contagion", "Contagion", "poison", 2, "When a poisoned monster dies, its venom leaps to the nearest monster.", ("plague",)),
    Skill("lower_resist", "Lower Resist", "poison", 3, "A poisoned monster resists everything 25 points less. Immunities hold.", ("plague",)),
    Skill("holy_shield", "Holy Shield", "warding", 1, "Warded gates have 50% more life and mend fully between waves.", ("gate",)),
    Skill("salvation", "Salvation", "warding", 2, "Cleanse costs 25 mana and wards the tower against curses for 8 seconds.", ("cleanse",)),
    Skill("thorns", "Thorns", "warding", 3, "A gate returns half of each blow to the monster that strikes it, frost or no frost.", ("gate",)),
    Skill("warmth", "Warmth", "sorcery", 1, "Mana flows 40% faster, and the orb holds 25 more."),
    Skill("soul_harvest", "Soul Harvest", "sorcery", 2, "Every slain leader gives 10 mana."),
    Skill("spell_mastery", "Spell Mastery", "sorcery", 3, "Smite, Meteor and Frozen Orb cost 25% less and strike 30% harder.", ("smite", "meteor", "orb")),
)}

TREE_COST = sum(s.cost for s in SKILLS.values())


def above(skill: Skill) -> Skill | None:
    """The skill a skill needs: the one above it in its column."""
    for other in SKILLS.values():
        if other.column == skill.column and other.tier == skill.tier - 1:
            return other
    return None


def cost(learned: Iterable[str]) -> int:
    return sum(SKILLS[key].cost for key in learned)


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


@dataclass(frozen=True)
class Perks:
    """Every number and rule the learned skills change; the defaults are the untrained game."""

    fire_damage: float = 1.0
    fire_ball: bool = False
    blaze: bool = False
    storm_damage: float = 1.0
    extra_leaps: int = 0
    leap_keeps: float = 0.85
    static_field: bool = False
    chill_deeper: float = 0.0
    chill_longer: float = 1.0
    frost_reach: float = 0.0
    frost_damage: float = 1.0
    shatter: bool = False
    venom: float = 1.0
    contagion: bool = False
    lower_resist: bool = False
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


NO_PERKS = Perks()


def perks(learned: Iterable[str]) -> Perks:
    chosen = frozenset(learned)
    check(chosen)
    p = NO_PERKS
    if "fire_mastery" in chosen:
        p = replace(p, fire_damage=1.25)
    if "fire_ball" in chosen:
        p = replace(p, fire_ball=True)
    if "blaze" in chosen:
        p = replace(p, blaze=True)
    if "lightning_mastery" in chosen:
        p = replace(p, storm_damage=1.25)
    if "chain_lightning" in chosen:
        p = replace(p, extra_leaps=1, leap_keeps=0.95)
    if "static_field" in chosen:
        p = replace(p, static_field=True)
    if "cold_mastery" in chosen:
        p = replace(p, chill_deeper=0.1, chill_longer=1.3)
    if "glacial_spike" in chosen:
        p = replace(p, frost_reach=0.4, frost_damage=1.5)
    if "shatter" in chosen:
        p = replace(p, shatter=True)
    if "poison_mastery" in chosen:
        p = replace(p, venom=1.3)
    if "contagion" in chosen:
        p = replace(p, contagion=True)
    if "lower_resist" in chosen:
        p = replace(p, lower_resist=True)
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


def tower_levels(kind: str, p: Perks) -> tuple[TowerLevel, ...]:
    """A tower kind's ranks with the perks baked in."""
    ranks = TOWERS[kind].levels
    if kind == "pyre":
        splash = [0.8, ranks[1].splash + 0.3, ranks[2].splash + 0.3] if p.fire_ball else [r.splash for r in ranks]
        return tuple(replace(r, damage=r.damage * p.fire_damage, splash=splash[i]) for i, r in enumerate(ranks))
    if kind == "storm":
        return tuple(replace(r, damage=r.damage * p.storm_damage, chains=r.chains + p.extra_leaps) for r in ranks)
    if kind == "frost":
        return tuple(replace(r, damage=r.damage * p.frost_damage, range=r.range + p.frost_reach, chill=r.chill + p.chill_deeper,
                             chill_time=r.chill_time * p.chill_longer) for r in ranks)
    if kind == "plague":
        return tuple(replace(r, poison=r.poison * p.venom) for r in ranks)
    raise KeyError(kind)
