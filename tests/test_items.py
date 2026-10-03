"""Tower patterns: authored recipes and the immutable loadout chosen before a defence."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pickle import dumps, loads

import pytest

from hellward.sim.items import Loadout, PATTERNS
from hellward.sim.campaign import DOCKS, GRAVEYARD, HELLS_GATE, TRAVINCAL, TRISTRAM
from hellward.sim.content import MONSTERS
from hellward.sim.model import Monster, World


def test_a_loadout_resolves_one_pattern_for_each_equipped_tower_family() -> None:
    """The run can read one fixed modifier for a tower family without knowing the inventory UI."""
    loadout = Loadout(("honed_string", "blast_chamber"))

    assert loadout.for_family("arrow") == PATTERNS["honed_string"]
    assert loadout.for_family("pyre") == PATTERNS["blast_chamber"]
    assert loadout.for_family("storm") is None


@pytest.mark.parametrize("keys", [
    ("unknown_pattern",),
    ("honed_string", "honed_string"),
    ("honed_string", "laminated_limbs"),
    ("laminated_limbs", "execution_bow"),
])
def test_a_loadout_rejects_unknown_or_conflicting_patterns(keys: tuple[str, ...]) -> None:
    """Saved or supplied equipment cannot quietly stack effects on one family."""
    with pytest.raises(ValueError):
        Loadout(keys)


def test_loadout_and_catalog_are_immutable_and_order_independent() -> None:
    """Equivalent equipment is one cache key, and neither the catalog nor a run can mutate it."""
    first = Loadout(("honed_string", "blast_chamber"))
    reversed_order = Loadout(("blast_chamber", "honed_string"))
    assert first == reversed_order
    assert hash(first) == hash(reversed_order)
    assert loads(dumps(first)) == first
    with pytest.raises(FrozenInstanceError):
        first.equipped = ()
    with pytest.raises(FrozenInstanceError):
        PATTERNS["honed_string"].name = "changed"
    with pytest.raises(TypeError):
        PATTERNS["honed_string"] = PATTERNS["blast_chamber"]


def test_recipes_preserve_the_flat_now_vs_scaling_later_choice() -> None:
    """The cheap opening pattern helps at rank I; area and boss power arrive later."""
    assert set(PATTERNS) == {"honed_string", "laminated_limbs", "blast_chamber", "forked_coil", "execution_bow"}
    assert all(20 <= len(pattern.blurb) <= 110 for pattern in PATTERNS.values())
    honed, laminated = PATTERNS["honed_string"], PATTERNS["laminated_limbs"]
    assert honed.salvage_cost == 3 and honed.damage_delta == (1, 1, 1)
    assert laminated.salvage_cost == 6 and laminated.damage_delta == (0, 1, 2)
    assert honed.damage_delta[0] > laminated.damage_delta[0]
    assert laminated.damage_delta[2] > honed.damage_delta[2]

    blast, fork = PATTERNS["blast_chamber"], PATTERNS["forked_coil"]
    assert blast.salvage_cost == 8 and blast.trophy_cost == 3
    assert fork.salvage_cost == 9 and fork.trophy_cost == 2
    assert blast.splash_delta[:2] == (0, 0) and blast.splash_delta[2] > 0
    assert fork.chain_delta[:2] == (0, 0) and fork.chain_delta[2] == 1
    assert blast.first_location == 7 and fork.first_location == 10

    execution = PATTERNS["execution_bow"]
    assert execution.salvage_cost == 10 and execution.trophy_cost == 2
    assert execution.first_location == 11
    assert execution.leader_damage_bonus > 0 and 0 < execution.rate_factor < 1


def test_patterns_bake_into_a_run_only_when_that_location_can_use_them() -> None:
    honed = Loadout(("honed_string",))
    laminated = Loadout(("laminated_limbs",))
    assert World(TRISTRAM, loadout=honed).tower_levels["arrow"][0].damage == 2
    assert World(GRAVEYARD, loadout=honed).tower_levels["arrow"][0].damage == 3
    assert World(GRAVEYARD, loadout=laminated).tower_levels["arrow"][0].damage == 2
    assert World(GRAVEYARD, loadout=laminated).tower_levels["arrow"][2].damage == 6
    blast = Loadout(("blast_chamber",))
    assert World(HELLS_GATE, loadout=blast).tower_levels["pyre"][2].splash == 0
    docks = World(DOCKS, loadout=blast)
    assert docks.tower_levels["pyre"][2].splash == 0.8
    assert docks.clone().tower_levels == docks.tower_levels


def test_execution_bow_pays_for_slow_fire_with_a_large_leader_hit() -> None:
    """The impact snapshots its pattern even while the arrow is in flight."""
    from dataclasses import replace

    def first_hit(loadout: Loadout) -> float:
        location = replace(TRAVINCAL, level=TRISTRAM.level, start_gold=100)
        world = World(location, loadout=loadout)
        world.build("arrow", (9, 12))
        leader = Monster(1001, MONSTERS["shaman"], 0, 0.0, 0.0, 100.0, 0.0)
        leader.s, leader.frozen = 10.0, 10.0
        world.monsters.append(leader)
        for _ in range(30):
            world.step()
            if leader.hp < 100:
                return 100 - leader.hp
        raise AssertionError("Arrow never reached its target")

    plain = first_hit(Loadout())
    execution = first_hit(Loadout(("execution_bow",)))
    assert execution == pytest.approx(plain * 2.5)
