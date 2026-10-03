"""The Bone Altar's amplification, Druid Grove's aura and their skills."""

from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.campaign import g
from hellward.sim.content import TOWERS, Curse, Element, Group, Wave, felt_hit
from hellward.sim.level import Level
from hellward.sim.model import SIM_DT, World
from hellward.sim.skills import perks


def act2_world(*groups: Group, learned=("unlock_pyre", "unlock_grove", "unlock_altar"), seed=0) -> World:
    """A short open field with buildable tiles next to the route; the arena's kinds come unlocked."""
    arsenal = replace(campaign.CATHEDRAL.arsenal,
                      towers=campaign.CATHEDRAL.arsenal.towers + ("altar", "grove"))
    level = Level("Act II tower field", 12, 9, ((0, 4), (11, 4)), ())
    location = replace(campaign.CATHEDRAL, level=level, arsenal=arsenal,
                       waves=(Wave(tuple(groups), 10),), wave_names=("test",))
    world = World(location, perks=perks(learned), seed=seed)
    world.gold = 5000
    return world


def run(world: World, seconds: float) -> None:
    end = world.time + seconds
    while world.time < end - 1e-9 and world.outcome is None:
        world.step(SIM_DT)


def spawned(world: World, count: int) -> None:
    world.call_wave()
    while len(world.monsters) < count:
        world.step()
        assert world.time < 60


def first_bolt(world: World):
    """The first bolt a tower fires, stepping until it does."""
    world.call_wave()
    while True:
        world.step()
        for e in world.events:
            if e[0] == "bolt":
                return e[1]
        world.events.clear()
        assert world.time < 120


def test_an_altar_amplifies_the_thickest_knot_and_everything_hurts_it_more():
    world = act2_world(g("fallen", 3, 0.5))
    altar = world.build("altar", (4, 3))
    world.call_wave()
    while not any(e[0] == "amplify" for e in world.events):
        world.step()
        assert world.time < 60
    event = next(e for e in world.events if e[0] == "amplify")
    _, tower_id, _, struck = event
    assert tower_id == altar.id and struck
    for m in world.monsters:
        if m.id in struck:
            assert m.amplified > 0 and m.amplify == pytest.approx(altar.stats.damage)


def test_amplification_multiplies_a_pyres_damage_but_not_after_it_lapses():
    world = act2_world(g("fallen", 1), seed=0)
    spawned(world, 1)
    m = world.monsters[0]
    m.hp = m.max_hp = 200.0   # it lives through both blows
    m.amplified, m.amplify = 5.0, 0.3
    hp = m.hp
    world._strike(m, 4.0, Element.FIRE)
    assert hp - m.hp == felt_hit(4.0, Element.FIRE, m.kind, 1.3) == 6   # 5.2, rounded up
    m.amplified = 0.0
    hp = m.hp
    world._strike(m, 4.0, Element.FIRE)
    assert hp - m.hp == 4


def test_amplification_does_not_stack():
    world = act2_world(g("fallen", 2, 0.1))
    altar = world.build("altar", (4, 3))
    spawned(world, 2)
    a, b = world.monsters
    a.s = b.s = 4.0
    a.amplified, a.amplify = 5.0, 0.6   # already stronger than the altar's pulse
    altar.cooldown = 0.0
    world.events.clear()
    world.step(SIM_DT)
    assert any(e[0] == "amplify" for e in world.events)
    assert a.amplify == pytest.approx(0.6)   # the greater holds, not the sum and not the lesser
    assert a.amplified == pytest.approx(5.0 - SIM_DT)
    assert b.amplify == pytest.approx(altar.stats.damage)
    assert b.amplified == pytest.approx(altar.stats.lasting - SIM_DT)


def test_a_grove_next_to_a_pyre_makes_its_bolt_hit_harder():
    world = act2_world(g("fallen", 1))
    pyre = world.build("pyre", (4, 3))
    grove = world.build("grove", (5, 3))
    bolt = first_bolt(world)
    assert bolt.damage == pyre.stats.damage and bolt.factor == pytest.approx(1 + grove.stats.damage)


def test_a_grove_three_tiles_away_lends_nothing():
    world = act2_world(g("fallen", 1))
    world.build("pyre", (4, 3))
    world.build("grove", (7, 3))
    assert first_bolt(world).factor == 1.0


def test_two_groves_do_not_stack():
    world = act2_world(g("fallen", 1))
    pyre = world.build("pyre", (4, 3))
    grove = world.build("grove", (5, 3))
    world.build("grove", (3, 3))
    assert first_bolt(world).factor == pytest.approx(1 + grove.stats.damage)


def test_a_weakened_grove_lends_a_third_and_a_caged_one_nothing():
    world = act2_world(g("fallen", 1))
    pyre = world.build("pyre", (4, 3))
    grove = world.build("grove", (5, 3))
    grove.curses[Curse.WEAKEN] = 5.0
    assert first_bolt(world).factor == pytest.approx(1 + grove.stats.damage * grove.damage_mult())

    world = act2_world(g("fallen", 1))
    pyre = world.build("pyre", (4, 3))
    grove = world.build("grove", (5, 3))
    grove.curses[Curse.BONE_PRISON] = 5.0   # caged: the aura is switched off
    assert first_bolt(world).factor == 1.0


def test_dim_vision_does_nothing_to_an_aura():
    world = act2_world(g("fallen", 1))
    pyre = world.build("pyre", (4, 3))
    grove = world.build("grove", (5, 3))
    grove.curses[Curse.DIM_VISION] = 5.0
    assert first_bolt(world).factor == pytest.approx(1 + grove.stats.damage)


def test_a_grove_drinks_a_charge_and_lends_double_for_a_while():
    world = act2_world(g("fallen", 1))
    spawned(world, 1)   # towers idle with no monsters; this one waits out of reach, frozen
    world.monsters[0].frozen = 1e9
    pyre = world.build("pyre", (4, 3))
    grove = world.build("grove", (5, 3))
    world.attune(pyre.id)
    before = pyre.charges
    world.step()   # the grove drinks at once: a charge spent, the verb counted, the event out
    assert pyre.charges == pytest.approx(before - 1.0, abs=0.01)
    assert world.verb_count.get("charge", 0) == 1
    drink = [e for e in world.events if e[0] == "drink"]
    assert len(drink) == 1 and drink[0][1] == grove.id and drink[0][2] == pyre.id
    assert drink[0][3] == 6.0   # the empowerment's seconds, for the client to show
    assert world.aura_mult(pyre) == pytest.approx(1 + grove.stats.damage * 2)
    run(world, 7)   # the empowerment lapses; the next drink waits for its twenty seconds
    assert world.aura_mult(pyre) == pytest.approx(1 + grove.stats.damage)
    assert world.verb_count.get("charge", 0) == 1
    run(world, 14)   # past twenty seconds the grove drinks again; the idle pyre's charges refilled
    assert world.verb_count.get("charge", 0) == 2


def test_a_grove_with_no_charged_neighbour_drinks_nothing():
    world = act2_world(g("fallen", 1))
    spawned(world, 1)
    world.monsters[0].frozen = 1e9
    pyre = world.build("pyre", (4, 3))
    grove = world.build("grove", (5, 3))
    run(world, 25)
    assert world.verb_count.get("charge", 0) == 0
    assert world.aura_mult(pyre) == pytest.approx(1 + grove.stats.damage)


def test_a_grove_drinks_from_the_attuned_neighbour_holding_the_most():
    world = act2_world(g("fallen", 1))
    spawned(world, 1)
    world.monsters[0].frozen = 1e9
    full = world.build("pyre", (4, 3))
    world.attune(full.id)
    low = world.build("pyre", (6, 3))
    world.attune(low.id)
    low.charges = 1.0
    world.build("grove", (5, 3))
    before = full.charges
    world.step()
    drink = [e for e in world.events if e[0] == "drink"]
    assert len(drink) == 1 and drink[0][2] == full.id
    assert full.charges == pytest.approx(before - 1.0, abs=0.01)
    assert low.charges == pytest.approx(1.0, abs=0.01)


def test_corpse_explosion_bursts_once_and_does_not_chain():
    world = act2_world(g("fallen", 3, 0.1),
                       learned=("unlock_altar", "adept_bone", "master_bone", "life_tap", "corpse_explosion"))
    spawned(world, 3)
    a, b, c = world.monsters
    a.s = b.s = c.s = 4.0
    a.amplified, a.amplify = 5.0, 0.3
    b.amplified, b.amplify, b.hp = 5.0, 0.3, a.max_hp * 0.1   # the burst kills it, amplified or not
    full = c.hp
    world.events.clear()
    world._hurt(a, 10000.0, None)
    bursts = [e for e in world.events if e[0] == "corpse_explosion"]
    assert len(bursts) == 1   # b's death sets off no burst of its own
    assert b.hp <= 0
    assert full - c.hp == pytest.approx(a.max_hp * 0.15)


def test_life_tap_pays_a_fifth_of_the_bounty_in_mana():
    world = act2_world(g("fallen", 1),
                       learned=("unlock_altar", "adept_bone", "corpse_explosion", "master_bone", "life_tap"))
    spawned(world, 1)
    m = world.monsters[0]
    m.amplified, m.amplify = 5.0, 0.3
    world.mana = 10.0
    world._hurt(m, 10000.0, None)
    assert world.mana == pytest.approx(10.0 + m.bounty / 5)


def test_hurricane_slows_a_walker_near_a_grove():
    plain = act2_world(g("zombie", 1))
    spawned(plain, 1)
    plain.monsters[0].s = 4.0
    run(plain, 2.0)
    far = plain.monsters[0].s - 4.0

    windy = act2_world(g("zombie", 1),
                       learned=("unlock_grove", "adept_nature", "master_nature", "hurricane"))
    windy.build("grove", (4, 3))
    spawned(windy, 1)
    windy.monsters[0].s = 4.0
    run(windy, 2.0)
    near = windy.monsters[0].s - 4.0
    assert near == pytest.approx(far * 0.8, rel=0.05)


def test_twister_roots_the_front_walker_but_not_an_overlord_or_a_gargoyle():
    learned = ("unlock_grove", "adept_nature", "hurricane", "master_nature", "twister")
    world = act2_world(g("zombie", 1), g("gargoyle", 1), g("overlord", 1), learned=learned)
    grove = world.build("grove", (4, 3))
    spawned(world, 3)
    by_kind = {m.kind.key: m for m in world.monsters}
    by_kind["zombie"].s = 4.2
    by_kind["gargoyle"].s = 4.1
    by_kind["overlord"].s = 4.0
    grove.timer = 3.9
    world.events.clear()
    world.step(0.2)
    assert ("twister", grove.id, by_kind["zombie"].id) in world.events
    assert by_kind["zombie"].frozen == pytest.approx(1.5)
    assert by_kind["gargoyle"].frozen == 0
    assert by_kind["overlord"].frozen == 0
    run(world, 4.0)
    assert len([e for e in world.events if e[0] == "twister"]) >= 2


def test_the_new_towers_fit_the_price_scale_and_keep_rank_skills():
    assert TOWERS["altar"].name == "Bone Altar" and TOWERS["altar"].element is Element.BONE
    assert TOWERS["altar"].attack == "amplify"
    assert TOWERS["grove"].name == "Druid Grove" and TOWERS["grove"].element is Element.NATURE
    assert TOWERS["grove"].attack == "aura"
    for key in ("altar", "grove"):
        levels = TOWERS[key].levels
        assert len(levels) == len(TOWERS["arrow"].levels)
        assert all(level.cost > TOWERS["arrow"].levels[rank].cost for rank, level in enumerate(levels))
        assert 0 < levels[0].damage < levels[1].damage < levels[2].damage < 1
    world = act2_world(g("fallen", 1), learned=("unlock_altar", "adept_bone", "unlock_grove", "adept_nature"))
    assert world.rank_needs(world.build("altar", (4, 3))) is None
    assert world.rank_needs(world.build("grove", (5, 3))) is None
    bare = act2_world(g("fallen", 1), learned=("unlock_altar", "unlock_grove"))
    assert bare.rank_needs(bare.build("altar", (4, 3))) == "adept_bone"
    assert bare.rank_needs(bare.build("grove", (5, 3))) == "adept_nature"
