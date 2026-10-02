"""The skill tree: its prerequisites, and that each skill changes the fight the way its words say."""

from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.players.ordinary import tile_scores
from hellward.sim.campaign import g
from hellward.sim.content import SOUL, MONSTERS, Element, Wave
from hellward.sim.model import Monster, Refused, SIM_DT, World
from hellward.sim.skills import COLUMNS, SKILLS, TREE_COST, can_learn, check, perks


def world_of(*groups, learned=(), **kwargs) -> World:
    location = replace(campaign.CATACOMBS, waves=(Wave(tuple(groups), 10),), wave_names=("test",), life=1.0,
                       arsenal=campaign.TEMPLE.arsenal)   # full catalog's rules, not this stage's unlocks
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
    assert can_learn(frozenset({"adept_fire"}), "master_fire", 3)
    assert not can_learn(frozenset({"adept_fire", "master_fire"}), "fire_ball", 5, stage=7)
    assert can_learn(frozenset({"adept_fire", "master_fire"}), "fire_ball", 5, stage=8)
    with pytest.raises(ValueError):
        check(frozenset({"blaze", "adept_fire"}))


def test_the_tree_costs_sixty_three_with_a_small_steel_column():
    assert TREE_COST == 63
    assert COLUMNS["arrow"] == "Steel"
    assert sum(s.cost for s in SKILLS.values() if s.column == "arrow") == 5
    for column in ("fire", "lightning", "cold", "poison", "bone", "nature"):
        assert sum(s.cost for s in SKILLS.values() if s.column == column) == 8
    assert sum(s.cost for s in SKILLS.values() if s.column == "warding") == 4
    assert sum(s.cost for s in SKILLS.values() if s.column == "sorcery") == 6
    assert COLUMNS.keys() >= {"fire", "lightning", "cold", "poison", "bone", "nature", "warding", "sorcery"}


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
    third = world_of(learned=("adept_fire", "master_fire"))
    pyre = third.build("pyre", best(third, 1)[0])
    third.upgrade(pyre.id)
    third.upgrade(pyre.id)
    assert pyre.level == 2
    assert third.rank_needs(pyre) is None
    assert third.upgrade_cost(pyre) is None


def test_fire_ball_cannot_be_learned_without_master_fire():
    assert not can_learn(frozenset({"adept_fire"}), "fire_ball", 10)
    with pytest.raises(ValueError):
        check(frozenset({"adept_fire", "fire_ball"}))
    assert can_learn(frozenset({"adept_fire", "master_fire"}), "fire_ball", 5)


@pytest.mark.parametrize("kind,learned", [("pyre", ("adept_fire", "master_fire", "fire_ball")),
                                          ("storm", ("adept_lightning", "master_lightning", "static_field", "chain_lightning")),
                                          ("frost", ("adept_cold", "glacial_spike")),
                                          ("plague", ("adept_poison", "master_poison", "lower_resist"))])
def test_combat_skills_hurt_a_cluster_more(kind, learned):
    """A tough cluster in reach shows extra damage before kills or leaks hide it."""
    plain = world_of()
    reach = plain.tower_levels[kind][0].range
    tile = next(tile for _, tile in tile_scores(plain, reach) if plain.level.coverage(tile, reach))
    a, b = plain.level.coverage(tile, reach)[0]
    middle = (a + b) / 2

    def remaining_hp(skills):
        world = world_of(learned=skills)
        world.build(kind, tile)
        for offset in (-0.1, 0.0, 0.1):
            monster = Monster(world._id(), MONSTERS["zombie"], 0, 0, 0, MONSTERS["zombie"].hp * 10, 0)
            monster.s = middle + offset
            monster.frozen = 5.0
            world.monsters.append(monster)
        world.monsters.sort(key=lambda monster: monster.s, reverse=True)
        run(world, 2)
        return sum(monster.hp for monster in world.monsters)

    assert remaining_hp(learned) < remaining_hp(())


def test_holy_shield_and_thorns_make_a_gate_hold_more_life_and_hurt_its_batterers():
    def gate(learned):
        """Put the same three zombies beside the gate and compare the next five seconds."""
        world = world_of(g("zombie", 3, 0.3), learned=learned)
        world.build_door(0)
        world.call_wave()
        run(world, 2)
        assert len(world.monsters) == 3
        for monster in world.monsters:
            monster.s = world.doors[0].s - 0.5
        run(world, 5)
        return world.doors[0].hp, sum(m.hp for m in world.monsters)
    plain_gate, plain_life = gate(())
    shield_gate, shield_life = gate(("holy_shield",))
    thorn_gate, thorn_life = gate(("holy_shield", "thorns"))
    assert shield_gate > plain_gate
    assert thorn_gate >= shield_gate
    assert thorn_life < shield_life <= plain_life


def test_static_field_draws_the_lightning_to_a_leader():
    def leader_hp(learned):
        world = world_of(learned=learned)
        tower = world.build("storm", best(world, 1)[0])
        a, b = world.level.coverage(tower.tile, tower.reach)[0]
        s = (a + b) / 2
        skeleton = Monster(world._id(), MONSTERS["skeleton"], 0, 0, 0, 100, 0)
        priest = Monster(world._id(), MONSTERS["priest"], 0, 0, 0, 100, 0)
        skeleton.s, priest.s = s + 0.1, s - 0.1
        skeleton.frozen = priest.frozen = 1.0
        world.monsters = [skeleton, priest]
        world.step()
        return priest.hp
    full = ("adept_lightning", "master_lightning", "static_field")
    partial = ("adept_lightning", "master_lightning")
    assert leader_hp(full) < leader_hp(partial)


def test_shatter_hurts_the_neighbours_of_a_monster_that_dies_chilled():
    def hurt_around(learned):
        world = world_of(learned=learned)
        first = Monster(world._id(), MONSTERS["fallen"], 0, 0, 0, 100, 0)
        second = Monster(world._id(), MONSTERS["fallen"], 0, 0, 0, 100, 0)
        first.s, second.s = 6.0, 6.4
        first.chill_left = 1.0
        world.monsters = [first, second]
        world._hurt(first, 101.0, Element.FIRE)
        return second.hp, sum(1 for e in world.events if e[0] == "shatter")
    chilled = hurt_around(("adept_cold", "glacial_spike", "master_cold", "shatter"))
    plain = hurt_around(("adept_cold", "glacial_spike", "master_cold"))
    assert chilled[0] < plain[0] and chilled[1] == 1 and plain[1] == 0


def test_contagion_carries_venom_to_the_next_monster_and_lower_resist_strips_its_protections():
    learned = ("adept_poison", "master_poison", "lower_resist", "contagion")
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
    assert goatman.taken(m, Element.LIGHTNING) < 1.0   # protected
    m.poison.append([1.0, 5.0])
    assert goatman.taken(m, Element.LIGHTNING) == 1.0
    zombie = world_of(g("zombie", 1), learned=learned)
    zombie.call_wave()
    run(zombie, 1)
    zombie.monsters[0].poison.append([1.0, 5.0])
    assert zombie.taken(zombie.monsters[0], Element.FIRE) > 1.0   # a vulnerability stays


def test_sorcery_fills_the_orb_faster_and_cheapens_the_spells():
    plain, warm = world_of(g("fallen", 1)), world_of(g("fallen", 1), learned=("warmth",))
    for w in (plain, warm):
        w.mana = 0
        run(w, 10)
    assert warm.mana > plain.mana
    mastered = world_of(g("fallen", 1), learned=("warmth", "soul_harvest", "spell_mastery"))
    for spell in ("smite", "hymn", "meteor", "orb"):
        assert mastered.spell_cost(spell) < plain.spell_cost(spell)


def test_soul_harvest_pays_mana_for_a_slain_leader():
    world = world_of(g("shaman", 1), learned=("warmth", "soul_harvest"))
    world.call_wave()
    run(world, 1)
    world.mana = world.spell_cost("smite")
    shaman = world.monsters[0]
    shaman.hp = 1   # wounded: one small Smite finishes it
    world.smite(shaman.id)
    assert world.mana == pytest.approx(SOUL)
