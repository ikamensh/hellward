"""The first defence teaches single-target damage at a human-readable scale."""

from dataclasses import replace

from hellward.sim.balance import BALANCE
from hellward.sim.campaign import GRAVEYARD, LOCATIONS, ORDER, TEMPLE, TRISTRAM
from hellward.sim.content import Group, SPELLS, TOWERS, Wave
from hellward.sim.model import World
from hellward.sim.skills import SKILLS, perks, tower_levels


def test_a_new_defence_starts_with_a_plain_arrow_tower():
    """The opening build choice really runs through World.build, at 1–20 hit and HP numbers."""
    world = World(TRISTRAM, seed=0)
    assert TRISTRAM.arsenal.towers == ("arrow",)
    arrow = TOWERS["arrow"]
    assert arrow.levels[0].splash == 0 and arrow.levels[0].chains == 0
    assert 1 <= arrow.levels[0].damage <= 20
    tower = world.build("arrow", (1, 4))
    assert tower.kind is arrow
    world.call_wave()
    while not world.monsters:
        world.step()
    assert 1 <= world.monsters[0].max_hp <= 20


def test_an_arrow_hits_only_one_enemy_in_a_pack():
    """Two enemies together must still need two separate arrows."""
    place = replace(TRISTRAM, waves=(Wave((Group("fallen", 2, 0.0),), 0),), wave_names=("pair",))
    world = World(place, seed=2)
    world.build("arrow", (10, 6))
    world.call_wave()
    world.step()
    assert len(world.monsters) == 2
    # Fallen choose routes independently; keep this pair together to test one arrow's impact.
    for monster in world.monsters:
        monster.route = "main"
        monster.s = 10.0
        monster.frozen = 10.0
    for _ in range(100):
        world.step()
        if any(event[0] == "hit" for event in world.events):
            break
    else:
        raise AssertionError("Arrow never hit the pack")
    full = world.monsters[0].max_hp
    assert sorted(monster.hp for monster in world.monsters) == [full - TOWERS["arrow"].levels[0].damage, full]


def test_first_six_locations_cannot_buy_a_damaging_area_attack():
    """Even a replay with every skill learned gets only single-target damage here."""
    for stage, key in enumerate(ORDER[:6]):
        location = LOCATIONS[key]
        trained = perks(SKILLS, stage)
        for kind in location.arsenal.towers:
            tower = TOWERS[kind]
            if kind in {"altar", "grove"}:
                continue  # support reaches an area but deals no direct damage
            assert tower.attack not in {"nova"}
            for rank in tower_levels(kind, trained):
                assert rank.splash == 0 and rank.chains == 0
        assert not trained.shatter and not trained.contagion and not trained.corpse_explosion
        assert all(SPELLS[spell].radius == 0 for spell in location.arsenal.spells)


def test_smite_has_a_small_single_target_hit_when_first_offered():
    assert 1 <= SPELLS["smite"].damage <= 20
    assert SPELLS["smite"].radius == 0


def test_tristram_wanderers_use_multiple_seeded_trails():
    def routes() -> tuple[str, ...]:
        world = World(TRISTRAM, seed=11)
        world.call_wave()
        while world.schedule:
            world.step()
        return tuple(monster.route for monster in world.monsters)

    first = routes()
    assert first == routes()
    assert len(set(first)) >= 2
    assert set(first) <= {route.key for route in TRISTRAM.level.routes}


def test_frost_burst_is_a_reliable_late_aoe_without_trophies():
    learned = {"adept_cold", "glacial_spike", "master_cold", "shatter"}
    assert tower_levels("frost", perks(learned, stage=7))[0].splash == 0
    assert tower_levels("frost", perks(learned, stage=8))[0].splash > 0


def test_battle_prices_and_wave_drops_follow_the_local_gold_unit():
    for stage, location in ((0, TRISTRAM), (1, GRAVEYARD), (11, TEMPLE)):
        world = World(location, seed=3)
        assert world.cost("arrow") == BALANCE.gold_unit(stage)
        world.call_wave()
        assert sum(world.gold_schedule) + location.waves[0].bonus == BALANCE.wave_income(stage, 0)
        assert world.clone().gold_schedule == world.gold_schedule
