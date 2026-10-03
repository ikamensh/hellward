"""M9: a light build falls behind where armor walks (tools/armor.py fights the duels)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import armor  # noqa: E402


def test_the_duels_builds_cost_exactly_equal_gold():
    for location, make, count in armor.DUELS:
        light, heavy = make(location, count)
        assert armor.plan_cost(light.steps) == armor.plan_cost(heavy.steps) > 0
        assert {s[1] for s in light.steps if s[0] == "build"} == {"arrow"}
        assert {s[1] for s in heavy.steps if s[0] == "build"} == {"ballista"}


def test_a_light_build_loses_hells_gate_and_a_heavy_build_of_equal_gold_wins():
    light, heavy, cost = armor.duel("hells_gate", armor.capped, 9, [0, 1, 2, 3, 4, 5])
    assert cost == 108
    assert all(o.startswith("d") for o in light)
    assert all(o.startswith("v") for o in heavy)


def test_a_light_build_loses_the_temple_and_a_heavy_build_of_equal_gold_wins():
    light, heavy, cost = armor.duel("temple", armor.full, 9, [0, 1, 2, 3, 4, 5])
    assert cost == 300
    assert all(o.startswith("d") for o in light)
    assert all(o.startswith("v") for o in heavy)


def test_the_light_build_holds_the_unarmored_caves_at_the_same_budget():
    light, _, cost = armor.duel("caves", armor.capped, 9, [0, 1, 2, 3, 4, 5])
    assert cost == 108
    assert all(o.startswith("v") for o in light)
