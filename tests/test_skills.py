"""The skill tree: its prerequisites, and that each skill changes the fight the way its words say."""

from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.campaign import g
from hellward.sim.content import Element, Wave
from hellward.sim.model import SIM_DT, World
from hellward.sim.skills import SKILLS, TREE_COST, can_learn, check, perks


def world_of(*groups, learned=(), **kwargs) -> World:
    location = replace(campaign.CATACOMBS, waves=(Wave(tuple(groups), 10),), wave_names=("test",))
    world = World(location, perks=perks(learned), **kwargs)
    world.gold = 5000
    return world


def run(world: World, seconds: float) -> None:
    end = world.time + seconds
    while world.time < end - 1e-9 and world.outcome is None:
        world.step(SIM_DT)


def test_a_skill_needs_the_one_above_it_and_enough_sigils():
    assert can_learn(frozenset(), "fire_mastery", 1)
    assert not can_learn(frozenset(), "fire_ball", 10)
    assert not can_learn(frozenset({"fire_mastery"}), "fire_ball", 2)
    assert can_learn(frozenset({"fire_mastery"}), "fire_ball", 3)
    with pytest.raises(ValueError):
        check(frozenset({"blaze", "fire_mastery"}))
    assert TREE_COST == 36


@pytest.mark.parametrize("kind,column", [("pyre", ("fire_mastery", "fire_ball")),
                                         ("storm", ("lightning_mastery", "chain_lightning")),
                                         ("frost", ("cold_mastery", "glacial_spike")),
                                         ("plague", ("poison_mastery",))])
def test_a_towers_skills_make_it_kill_more(kind, column):
    """Property: every tower skill leaves fewer monsters alive, or fewer lives lost, than none."""
    def result(learned):
        world = world_of(g("zombie", 6, 0.6), g("fallen", 8, 0.4, start=2.0), learned=learned)
        world.build(kind, (5, 5))
        world.build(kind, (11, 6))
        world.call_wave()
        run(world, 40)
        return (world.lives, world.kills, -sum(m.hp for m in world.monsters))
    assert result(column) > result(())


def test_holy_shield_and_thorns_make_a_gate_hold_longer_and_hurt_its_batterers():
    def gate(learned):
        world = world_of(g("zombie", 3, 0.3), learned=learned)
        world.build_door(0)
        world.call_wave()
        run(world, 30)
        return world.doors[0].hp, sum(m.hp for m in world.monsters)
    plain_gate, plain_life = gate(())
    shield_gate, _ = gate(("holy_shield",))
    thorn_gate, thorn_life = gate(("holy_shield", "salvation", "thorns"))
    assert shield_gate > plain_gate
    assert thorn_life < plain_life


def test_static_field_draws_the_lightning_to_a_leader():
    def leader_hp(learned):
        world = world_of(g("skeleton", 6, 0.3), g("priest", 1, start=1.0), learned=learned)
        world.build("storm", (4, 5))
        world.call_wave()
        run(world, 9)
        priest = next((m for m in world.monsters if m.kind.key == "priest"), None)
        return priest.hp / priest.max_hp if priest is not None else 0.0
    assert leader_hp(("lightning_mastery", "chain_lightning", "static_field")) < leader_hp(("lightning_mastery", "chain_lightning"))


def test_shatter_hurts_the_neighbours_of_a_monster_that_dies_chilled():
    def hurt_around(learned):
        world = world_of(g("fallen", 6, 0.2), learned=learned)
        world.build("frost", (5, 5))
        world.build("pyre", (4, 5))   # kills them while the frost holds them
        world.call_wave()
        run(world, 12)
        return sum(1 for e in world.events if e[0] == "shatter")
    assert hurt_around(("cold_mastery", "glacial_spike", "shatter")) > 0
    assert hurt_around(("cold_mastery", "glacial_spike")) == 0


def test_contagion_carries_venom_to_the_next_monster_and_lower_resist_opens_it_up():
    learned = ("poison_mastery", "contagion", "lower_resist")
    world = world_of(g("goatman", 4, 0.3), learned=learned)
    world.build("plague", (5, 5))
    world.build("pyre", (4, 5))   # kills them while the venom is in them
    world.call_wave()
    run(world, 25)
    assert any(e[0] == "contagion" for e in world.events)
    goatman = world_of(g("goatman", 1), learned=learned)
    goatman.call_wave()
    run(goatman, 1)
    m = goatman.monsters[0]
    before = goatman.taken(m, Element.LIGHTNING)
    m.poison.append([1.0, 5.0])
    assert goatman.taken(m, Element.LIGHTNING) == pytest.approx(before + 0.25)
    skeleton = world_of(g("skeleton", 1), learned=learned)
    skeleton.call_wave()
    run(skeleton, 1)
    skeleton.monsters[0].poison.append([1.0, 5.0])
    assert skeleton.taken(skeleton.monsters[0], Element.POISON) == 0   # immunities hold


def test_sorcery_fills_the_orb_faster_and_cheapens_the_spells():
    plain, warm = world_of(g("fallen", 1)), world_of(g("fallen", 1), learned=("warmth",))
    for w in (plain, warm):
        w.mana = 0
        run(w, 10)
    assert warm.mana > plain.mana
    mastered = world_of(g("fallen", 1), learned=("warmth", "soul_harvest", "spell_mastery"))
    assert mastered.spell_cost("meteor") < plain.spell_cost("meteor")
    assert mastered.spell_cost("cleanse") == plain.spell_cost("cleanse")


def test_soul_harvest_pays_mana_for_a_slain_leader():
    world = world_of(g("shaman", 1), learned=("warmth", "soul_harvest"))
    world.call_wave()
    run(world, 1)
    world.mana = world.spell_cost("smite")
    world.smite(world.monsters[0].id)   # a shaman's life is less than one smite
    assert world.mana == pytest.approx(20)
