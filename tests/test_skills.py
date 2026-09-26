"""The skill tree: its prerequisites, and that each skill changes the fight the way its words say."""

from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.players.ordinary import tile_scores
from hellward.sim.campaign import g
from hellward.sim.content import SOUL, Element, Wave
from hellward.sim.model import Refused, SIM_DT, World
from hellward.sim.skills import COLUMNS, SKILLS, TREE_COST, can_learn, check, perks


def world_of(*groups, learned=(), **kwargs) -> World:
    location = replace(campaign.CATACOMBS, waves=(Wave(tuple(groups), 10),), wave_names=("test",))
    world = World(location, perks=perks(learned), **kwargs)
    world.gold = 5000
    return world


def best(world: World, n: int) -> list[tuple[int, int]]:
    """The n floor tiles that watch the most path: where any player builds first."""
    return [tile for _, tile in tile_scores(world)[:n]]


def run(world: World, seconds: float) -> None:
    end = world.time + seconds
    while world.time < end - 1e-9 and world.outcome is None:
        world.step(SIM_DT)


def test_a_skill_needs_the_one_above_it_and_enough_sigils():
    assert can_learn(frozenset(), "adept_fire", 1)
    assert not can_learn(frozenset(), "fire_ball", 10)
    assert not can_learn(frozenset({"adept_fire"}), "fire_ball", 2)
    assert can_learn(frozenset({"adept_fire"}), "fire_ball", 3)
    with pytest.raises(ValueError):
        check(frozenset({"blaze", "adept_fire"}))
    assert TREE_COST == 44


def test_the_tree_costs_forty_four_and_every_tower_column_costs_eight():
    assert TREE_COST == 44
    for column in ("fire", "lightning", "cold", "poison"):
        assert sum(s.cost for s in SKILLS.values() if s.column == column) == 8
    assert sum(s.cost for s in SKILLS.values() if s.column == "warding") == 6
    assert sum(s.cost for s in SKILLS.values() if s.column == "sorcery") == 6
    assert COLUMNS.keys() >= {"fire", "lightning", "cold", "poison", "warding", "sorcery"}


def test_a_pyre_needs_its_adept_and_master_for_the_second_and_third_ranks():
    world = world_of(learned=())
    pyre = world.build("pyre", best(world, 1)[0])
    assert world.rank_needs(pyre) == "adept_fire"
    with pytest.raises(Refused, match="Learn Adept of Fire in the skill tree"):
        world.upgrade(pyre.id)
    second = world_of(learned=("adept_fire",))
    pyre = second.build("pyre", best(second, 1)[0])
    assert second.rank_needs(pyre) is None
    second.upgrade(pyre.id)
    assert pyre.level == 1
    assert second.rank_needs(pyre) == "master_fire"
    with pytest.raises(Refused, match="Learn Master of Fire in the skill tree"):
        second.upgrade(pyre.id)
    third = world_of(learned=("adept_fire", "fire_ball", "master_fire"))
    pyre = third.build("pyre", best(third, 1)[0])
    third.upgrade(pyre.id)
    third.upgrade(pyre.id)
    assert pyre.level == 2
    assert third.rank_needs(pyre) is None
    assert third.upgrade_cost(pyre) is None


def test_master_fire_cannot_be_learned_without_fire_ball():
    assert not can_learn(frozenset({"adept_fire"}), "master_fire", 10)
    with pytest.raises(ValueError):
        check(frozenset({"adept_fire", "master_fire"}))
    assert can_learn(frozenset({"adept_fire", "fire_ball"}), "master_fire", 5)


@pytest.mark.parametrize("kind,column", [("pyre", ("adept_fire", "fire_ball")),
                                         ("storm", ("adept_lightning", "chain_lightning")),
                                         ("frost", ("adept_cold", "glacial_spike")),
                                         ("plague", ("adept_poison", "contagion", "master_poison",
                                                     "lower_resist"))])
def test_a_towers_skills_make_it_kill_more(kind, column):
    """Property: every tower skill leaves fewer monsters alive, or fewer lives lost, than none."""
    def result(learned):
        world = world_of(g("zombie", 6, 0.6), g("fallen", 8, 0.4, start=2.0), learned=learned)
        for tile in best(world, 2):
            world.build(kind, tile)
        world.call_wave()
        run(world, 40)
        return (world.lives, world.kills, -sum(m.hp for m in world.monsters))
    assert result(column) > result(())


def test_holy_shield_and_thorns_make_a_gate_hold_longer_and_hurt_its_batterers():
    def gate(learned):
        """How long the first gate held against three zombies, and the life they had left when it fell."""
        world = world_of(g("zombie", 3, 0.3), learned=learned)
        world.build_door(0)
        world.call_wave()
        while world.doors[0].built:
            run(world, 0.5)
            assert world.time < 300
        return world.time, sum(m.hp for m in world.monsters)
    plain_held, plain_life = gate(())
    shield_held, _ = gate(("holy_shield",))
    thorn_held, thorn_life = gate(("holy_shield", "salvation", "thorns"))
    assert shield_held > plain_held
    assert thorn_life < plain_life


def test_static_field_draws_the_lightning_to_a_leader():
    def leader_hp(learned):
        world = world_of(g("skeleton", 6, 0.3), g("priest", 1, start=1.0), learned=learned)
        world.build("storm", best(world, 1)[0])
        world.call_wave()
        run(world, 9)
        priest = next((m for m in world.monsters if m.kind.key == "priest"), None)
        return priest.hp / priest.max_hp if priest is not None else 0.0
    full = ("adept_lightning", "chain_lightning", "master_lightning", "static_field")
    partial = ("adept_lightning", "chain_lightning", "master_lightning")
    assert leader_hp(full) < leader_hp(partial)


def test_shatter_hurts_the_neighbours_of_a_monster_that_dies_chilled():
    def hurt_around(learned):
        world = world_of(g("fallen", 6, 0.2), learned=learned)
        frost, pyre = best(world, 2)
        world.build("frost", frost)
        world.build("pyre", pyre)   # kills them while the frost holds them
        world.call_wave()
        run(world, 12)
        return sum(1 for e in world.events if e[0] == "shatter")
    assert hurt_around(("adept_cold", "glacial_spike", "master_cold", "shatter")) > 0
    assert hurt_around(("adept_cold", "glacial_spike", "master_cold")) == 0


def test_contagion_carries_venom_to_the_next_monster_and_lower_resist_opens_it_up():
    learned = ("adept_poison", "contagion", "master_poison", "lower_resist")
    world = world_of(g("fallen", 6, 0.2), learned=learned)
    plague, pyre = best(world, 2)
    world.build("plague", plague)
    world.build("pyre", pyre)   # kills them while the venom is in them
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
    shaman = world.monsters[0]
    shaman.hp = shaman.max_hp * 0.5   # wounded: one smite finishes it
    world.smite(shaman.id)
    assert world.mana == pytest.approx(SOUL)
