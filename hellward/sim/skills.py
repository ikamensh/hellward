"""The skill tree, read from ``data/skills.toml``: a column per tower kind plus Warding, Sorcery and Battle
Magic, bought with sigils.

A skill needs the one above it in its column. Every tower kind but the Arrow is locked until its `unlock_`
skill is learned; each kind then teaches its own second and third ranks (`adept_*`, `master_*`) and, for the
six elemental kinds, two specials. Battle Magic unlocks the Hymn, the Orb and the Meteor in turn (Smite is
free); Sorcery holds mana and spell mastery; Warding the gate skills. :func:`perks` turns a set of learned
skills into
:class:`Perks`, every number and rule they change, which a :class:`~hellward.sim.model.World` reads
when a defence begins (:func:`tower_levels` bakes the tower modifiers into each kind's ranks once).
The second and third ranks of a tower are learned here: :attr:`Perks.ranks` holds, per tower kind,
the highest rank index that may be bought.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Final

from hellward.sim import tuning
from hellward.sim.content import DOOR, MANA_MAX, MANA_REGEN, SPELLS, TOWERS, TowerLevel
from hellward.sim.items import EMPTY_LOADOUT, Loadout
from hellward.sim.sums import int_sum


@dataclass(frozen=True)
class Skill:
    key: str
    name: str
    column: str
    tier: int            # 1 to 5, top to bottom; the price in sigils is `cost`
    cost: int
    blurb: str
    needs: tuple[str, ...] = ()   # what it works on (a tower kind, "gate" or a spell): it does nothing where none is offered
    first_location: int = 0        # zero-based campaign stage; learned only when this location opens


PHYSICAL: Final = ("arrow", "ballista", "hook", "knife")   # the towers of no element, which armor checks

COLUMNS: Final[dict[str, str]] = dict(tuning.table("skills.columns"))


def _load() -> dict[str, Skill]:
    """Every skill in ``skills.toml``, validated: each names its column, tier, cost and words."""
    found: dict[str, Skill] = {}
    for key, row in tuning.table("skills.skills").items():
        try:
            needs = tuple(row.get("needs", ()))
            found[key] = Skill(key, row["name"], row["column"], int(row["tier"]), int(row["cost"]),
                               row["blurb"], needs, int(row.get("first_location", 0)))
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"skills.toml [{key}]: {e}")
        if found[key].column not in COLUMNS:
            raise ValueError(f"skills.toml [{key}]: unknown column {found[key].column!r}")
    return found


SKILLS: Final[dict[str, Skill]] = _load()

TREE_COST = int_sum(s.cost for s in SKILLS.values())


def _ranks() -> dict[str, tuple[str, str]]:
    """Each tower kind's rank skills: the column's `adept_*` (rank II) and `master_*` (rank III)."""
    found: dict[str, tuple[str, str]] = {}
    for kind in TOWERS:
        adept = [k for k, s in SKILLS.items() if k.startswith("adept_") and kind in s.needs]
        master = [k for k, s in SKILLS.items() if k.startswith("master_") and kind in s.needs]
        assert len(adept) == len(master) == 1, kind
        found[kind] = (adept[0], master[0])
    return found


RANK_SKILL: Final[dict[str, tuple[str, str]]] = _ranks()


def _unlocks() -> dict[str, str | None]:
    """Each tower kind's `unlock_` skill, if it has one: the Arrow is free."""
    found: dict[str, str | None] = {}
    for kind in TOWERS:
        keys = [k for k, s in SKILLS.items() if k.startswith("unlock_") and kind in s.needs]
        assert len(keys) <= 1, kind
        found[kind] = keys[0] if keys else None
    return found


UNLOCK: Final[dict[str, str | None]] = _unlocks()


def unlocked(kind: str, learned: frozenset[str] | set[str]) -> bool:
    """Whether the kind can be raised: free, or its unlock skill learned."""
    key = UNLOCK[kind]
    return key is None or key in learned


def _spell_unlocks() -> dict[str, str]:
    """Each gated spell's `unlock_` skill: Smite and Cleanse are free."""
    found: dict[str, str] = {}
    for spell in SPELLS:
        keys = [k for k, s in SKILLS.items() if k.startswith("unlock_") and spell in s.needs]
        assert len(keys) <= 1, spell
        if keys:
            found[spell] = keys[0]
    return found


SPELL_UNLOCK: Final[dict[str, str]] = _spell_unlocks()


def above(skill: Skill) -> Skill | None:
    """The skill a skill needs: the one above it in its column."""
    for other in SKILLS.values():
        if other.column == skill.column and other.tier == skill.tier - 1:
            return other
    return None


def cost(learned: Iterable[str]) -> int:
    return int_sum(SKILLS[key].cost for key in learned)


def can_learn(learned: frozenset[str], key: str, sigils: int, stage: int | None = None) -> bool:
    skill = SKILLS[key]
    needed = above(skill)
    return (key not in learned and (needed is None or needed.key in learned) and cost(learned) + skill.cost <= sigils
            and (stage is None or stage >= skill.first_location))


def kept(learned: Iterable[str], sigils: int, stage: int | None = None) -> frozenset[str]:
    """The learned skills a save from an older tree keeps: those the tree still has, each with every skill above it
    in its column learned too (a skill the tree lost, or moved above one learned, takes those below it along), top
    tier first while the sigils pay for them (a skill whose price rose is unlearned rather than owed); the unlocks
    of a tier before the rest, so a tight purse never locks a kind to keep a bonus."""
    have = {key for key in learned if key in SKILLS}
    out: frozenset[str] = frozenset()
    for skill in sorted((SKILLS[key] for key in have),
                       key=lambda s: (s.tier, 0 if s.key.startswith("unlock_") else 1, s.key)):
        if can_learn(out, skill.key, sigils, stage):
            out |= {skill.key}
    return out


def check(learned: frozenset[str]) -> None:
    """Raise ValueError unless every learned skill has the one above it."""
    for key in learned:
        needed = above(SKILLS[key])
        if needed is not None and needed.key not in learned:
            raise ValueError(f"{SKILLS[key].name} needs {needed.name}")


def column_of(kind: str) -> str:
    """The tree column of a tower kind: where its ranks are learned."""
    return SKILLS[RANK_SKILL[kind][0]].column


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
    thorns: bool = False
    mana_max: float = MANA_MAX
    mana_regen: float = MANA_REGEN
    soul_harvest: bool = False
    spell_cost: float = 1.0      # every spell's mana
    spell_power: float = 1.0
    locked: frozenset[str] = frozenset()   # tower kinds and spells whose unlock is not learned

    def top(self, kind: str) -> int:
        """The highest rank index of this tower kind that may be bought (0 = only the first rank)."""
        for name, rank in self.ranks:
            if name == kind:
                return rank
        return 0


NO_PERKS: Final = Perks()


def perks(learned: Iterable[str], stage: int | None = None) -> Perks:
    chosen = frozenset(learned)
    check(chosen)
    if stage is not None:
        chosen = kept(chosen, cost(chosen), stage)
    p = NO_PERKS
    shut = frozenset([k for k in TOWERS if not unlocked(k, chosen)]
                     + [s for s, key in SPELL_UNLOCK.items() if key not in chosen])
    if shut:
        p = replace(p, locked=shut)
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
    if "thorns" in chosen:
        p = replace(p, thorns=True)
    if "warmth" in chosen:
        p = replace(p, mana_max=MANA_MAX + 25, mana_regen=MANA_REGEN * 1.4, soul_harvest=True)
    if "spell_mastery" in chosen:
        p = replace(p, spell_cost=0.75, spell_power=1.3)
    return p


_BAKED: Final[dict[tuple[Perks, Loadout], dict[str, tuple[TowerLevel, ...]]]] = {}


def baked(p: Perks, loadout: Loadout = EMPTY_LOADOUT) -> dict[str, tuple[TowerLevel, ...]]:
    """Every tower kind's ranks with the perks in them, worked out once per set of perks: every world begins with
    them, and so does every clone the planner looks ahead in. Nothing changes them."""
    key = (p, loadout)
    found = _BAKED.get(key)
    if found is None:
        found = _BAKED[key] = {kind: tower_levels(kind, p, loadout) for kind in TOWERS}
    return found


def tower_levels(kind: str, p: Perks, loadout: Loadout = EMPTY_LOADOUT) -> tuple[TowerLevel, ...]:
    """A tower kind's ranks with the perks baked in."""
    ranks = TOWERS[kind].levels
    if kind in PHYSICAL:
        trained = tuple(ranks)
    elif kind == "pyre":
        splash = [0.8, ranks[1].splash + 0.3, ranks[2].splash + 0.3] if p.fire_ball else [r.splash for r in ranks]
        trained = tuple(replace(r, splash=splash[i]) for i, r in enumerate(ranks))
    elif kind == "storm":
        trained = tuple(replace(r, chains=r.chains + p.extra_leaps) for r in ranks)
    elif kind == "frost":
        trained = tuple(replace(r, damage=r.damage * p.frost_damage, range=r.range + p.frost_reach,
                                splash=0.9 if p.shatter else 0.0) for r in ranks)
    elif kind in ("plague", "altar", "grove"):
        trained = tuple(ranks)
    else:
        raise KeyError(kind)
    pattern = loadout.for_family(kind)
    if pattern is None:
        return trained
    return tuple(replace(r, damage=r.damage + pattern.damage_delta[i], splash=r.splash + pattern.splash_delta[i],
                         chains=r.chains + pattern.chain_delta[i], rate=r.rate * pattern.rate_factor,
                         leader_bonus=pattern.leader_damage_bonus) for i, r in enumerate(trained))
