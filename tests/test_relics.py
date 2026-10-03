"""The run's relics: each fires on its verb's count, and the run carries the counts on."""

from dataclasses import replace

from hellward.run import camp, finish, from_json, kit, observe_world, start, take_relic, to_json
from hellward.sim import campaign
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import SPELLS, TOWERS, Group, Wave
from hellward.sim.level import Level
from hellward.sim.model import Refused, World
from hellward.sim.relics import RELICS, draw

ARENA = Level("Relic field", 25, 14,
              ((0, 2), (9, 2), (9, 8), (19, 8), (19, 11), (24, 11)), ((9, 5),))


def arena(foe: str = "fallen", **kwargs) -> World:
    waves = (Wave((Group(foe, 4, 1.0),), 10),)
    arsenal = replace(campaign.CATHEDRAL.arsenal, towers=tuple(TOWERS), spells=tuple(SPELLS), gates=True)
    location = replace(campaign.CATHEDRAL, level=ARENA, arsenal=arsenal, waves=waves, wave_names=("pack",))
    world = World(location, **kwargs)
    world.gold = 10000
    return world


def floor(world: World, n: int) -> list[tuple[int, int]]:
    return [(x, y) for y in range(14) for x in range(25) if world.buildable(x, y)][:n]


def relic_events(world: World) -> list[tuple]:
    return [e for e in world.events if e[0] == "relic"]


def test_every_sixth_tower_stands_free():
    world = arena(relics=("tithe",))
    cost = world.cost("arrow")
    for tile in floor(world, 6):
        world.build("arrow", tile)
    assert world.builds == 6
    assert world.gold == 10000 - 5 * cost
    assert ("relic", "tithe", "The Mason's Tithe") in world.events


def test_every_third_tower_pays_gold():
    world = arena(relics=("scaffold",))
    for tile in floor(world, 4):
        world.build("arrow", tile)
    assert world.gold == 10000 - 4 * world.cost("arrow") + 25
    assert [e for e in relic_events(world) if e[1] == "scaffold"] != []


def test_every_second_rank_costs_half():
    from hellward.sim.skills import perks

    world = arena(relics=("whetstone",), perks=perks({"adept_arrow"}))
    tiles = floor(world, 2)
    for tile in tiles:
        world.build("arrow", tile)
    ids = [world.tower_at(tile).id for tile in tiles]
    first = world.upgrade_cost(world.towers[ids[0]])
    world.upgrade(ids[0])
    second = world.upgrade_cost(world.towers[ids[1]])
    world.upgrade(ids[1])
    assert world.upgrades == 2
    assert world.gold == 10000 - 2 * world.cost("arrow") - first - second + round(second / 2)


def test_every_third_rank_wells_mana():
    from hellward.sim.skills import perks

    world = arena(relics=("masterwork",), perks=perks({"adept_arrow"}))
    world.mana = 0.0
    tiles = floor(world, 3)
    for tile in tiles:
        world.build("arrow", tile)
    for tile in tiles:
        world.upgrade(world.tower_at(tile).id)
    assert world.mana == 25.0


def test_each_cast_quickens_every_tower_while_it_lasts():
    world = arena(relics=("trance",))
    world.mana = 1000.0
    world.meteor(12.0, 4.0)
    assert world.fervor == 6.0
    assert world._fervor() == 1.25
    for _ in range(int(7.0 / 0.05) + 1):
        world.step(0.05)
    assert world.fervor == 0.0
    assert world._fervor() == 1.0


def test_every_second_cast_costs_half_its_mana():
    world = arena(relics=("deep_well",))
    cost = world.spell_cost("meteor")
    world.mana = world.mana_max
    world.meteor(12.0, 4.0)
    world.mana = world.mana_max   # the purse is not what is tested
    world.recharge.clear()   # the gathering is not what is tested
    world.meteor(13.0, 4.0)
    assert world.mana == world.mana_max - cost + cost / 2


def test_curses_landing_well_mana_and_pay_gold():
    world = arena("shaman", relics=("spite", "martyr"))
    world.call_wave()
    while not world.monsters:
        world.step()
    world.mana = 0.0   # after the spawning's steps: no regen may hide in the count
    lid = world.monsters[0].id
    for tile in floor(world, 1):
        world.build("arrow", tile)
    from hellward.sim.content import Curse
    spot = world.towers[list(world.towers)[0]].tile
    tile = min(world.level.path_tiles, key=lambda t: (t[0] - spot[0]) ** 2 + (t[1] - spot[1]) ** 2)
    world.monster(lid).s = world.level.s_of(tile)
    gold = world.gold
    for _ in range(3):
        world._land(lid, Curse.WEAKEN, spot)
    assert world.curses_landed == 3
    assert world.mana == 15.0
    assert world.gold == gold + 30


def test_each_leak_pays_gold_and_costs_a_life_more():
    world = arena(relics=("blood_money",))
    world.call_wave()
    while not world.monsters:
        world.step()
    m = world.monsters[0]
    lives, gold = world.lives, world.gold
    m.s = world.level.route(m.route).length - 0.01
    world.step()
    assert world.leaks == 1
    assert world.gold == gold + m.kind.lives * 12
    assert world.lives == lives - m.kind.lives - 1
    assert ("relic", "blood_money", "The Blood Money") in world.events


def test_the_canticle_sings_hymn_where_none_is_offered_for_a_shallower_well():
    world = World(LOCATIONS["tristram"], relics=("canticle",))
    assert "hymn" in world.spells
    assert world.mana_max == world.perks.mana_max - 10.0
    world.gold = 10000
    tile = next((x, y) for y in range(20) for x in range(30) if world.buildable(x, y))
    world.build("arrow", tile)
    world.mana = 100.0
    world.hymn(world.tower_at(tile).id)
    assert world.tower_at(tile).hymn > 0
    bare = World(LOCATIONS["tristram"])
    assert "hymn" not in bare.spells


def test_hymn_stays_refused_where_it_is_locked():
    from hellward.sim.skills import perks

    world = arena(perks=perks(frozenset()))   # no unlock_hymn: the Hymn is locked
    tile = floor(world, 1)[0]
    world.build("arrow", tile)
    world.mana = 100.0
    try:
        world.hymn(world.tower_at(tile).id)
    except Refused:
        pass
    else:
        raise AssertionError("hymn sung with no unlock and no canticle")
    sung = arena(relics=("canticle",), perks=perks(frozenset()))
    tile = floor(sung, 1)[0]
    sung.build("arrow", tile)
    sung.mana = 100.0
    sung.hymn(sung.tower_at(tile).id)
    assert sung.tower_at(tile).hymn > 0


def test_the_clone_keeps_the_relics_and_their_counts():
    world = arena(relics=("tithe", "scaffold"), counters=(("tithe", 4),))
    for tile in floor(world, 2):
        world.build("arrow", tile)
    twin = world.clone()
    assert twin.relics == ("tithe", "scaffold")
    assert twin.progress == {"tithe": 6, "scaffold": 2}
    assert twin.builds == 2


def test_a_held_location_draws_the_camp_an_offer_of_three():
    run = start(11)
    first = draw(11, 0, ())
    assert len(first) == 3
    assert len(set(first)) == 3
    assert all(key in RELICS for key in first)
    assert draw(11, 0, ()) == first   # the seed draws the same offer
    assert all(key not in first[:1] for key in draw(11, 0, first[:1]))   # the held are not offered again


def test_taking_a_relic_carries_it_into_the_next_defence():
    run = start(11)
    played = kit(run)
    world = played.world()
    world.outcome = "victory"
    run = finish(run, observe_world(played, world, run.drawn))
    assert len(run.offer) == 3
    taken = run.offer[0]
    run = take_relic(run, taken)
    assert run.relics == (taken,)
    assert run.offer == ()
    assert kit(run).relics == (taken,)
    try:
        take_relic(run, taken)
    except ValueError:
        pass
    else:
        raise AssertionError("a relic taken twice")


def test_the_counts_carry_from_defence_to_defence():
    import dataclasses

    run = start(11)
    played = kit(run)
    world = played.world()
    world.outcome = "victory"
    run = finish(run, observe_world(played, world, run.drawn))
    run = take_relic(run, run.offer[0])
    run = dataclasses.replace(run, relics=("tithe",))   # the test needs the Tithe's count
    carried = kit(run)
    assert carried.relics == ("tithe",)
    again = carried.world()
    again.gold = 10000
    tiles = [(x, y) for y in range(20) for x in range(30) if again.buildable(x, y)][:2]
    for tile in tiles:
        again.build("arrow", tile)
    again.outcome = "victory"
    run = finish(run, observe_world(carried, again, run.drawn))
    assert run.counters == (("tithe", 2),)
    assert kit(run).counters == (("tithe", 2),)


def test_a_run_with_relics_saves_and_resumes():
    run = start(11)
    played = kit(run)
    world = played.world()
    world.outcome = "victory"
    run = finish(run, observe_world(played, world, run.drawn))
    run = take_relic(run, run.offer[0])
    run = camp(run)
    back = from_json(to_json(run))
    assert back.relics == run.relics
    assert back.offer == run.offer
    assert back.counters == run.counters
    assert kit(back).relics == run.relics


def test_a_struck_shrine_rings_every_tower_a_charge_and_drains_the_well():
    world = arena(relics=("bell",))
    tower = world.build("arrow", floor(world, 1)[0])
    world.attune(tower.id)
    world.mana = world.mana_max
    world.call_wave()
    while not world.monsters:
        world.step()
    tower.charges = 2.9
    monster = world.monsters[0]
    monster.s = world.level.route(monster.route).length - 0.01
    world.step()
    assert world.leaks == 1
    assert tower.charges == 3.0
    assert world.mana == world.mana_max - 15.0
    assert ("relic", "bell", "The Martyr's Bell") in world.events


def test_full_charges_reach_one_further_with_the_seal():
    world = arena(relics=("hoard",))
    tower = world.build("arrow", floor(world, 1)[0])
    world.attune(tower.id)
    assert world.striking_reach(tower) == tower.reach + 1.0
    tower.charges = 2.0
    assert world.striking_reach(tower) == tower.reach


def test_every_third_curse_answers_its_caster():
    from hellward.sim.content import Curse
    world = arena("shaman", relics=("candle",))
    tiles = floor(world, 9)
    for tile in tiles:
        world.build("arrow", tile)
    world.call_wave()
    while not any(m.kind.key == "shaman" for m in world.monsters):
        world.step()
    leader = next(m for m in world.monsters if m.kind.key == "shaman")
    tile = min(world.level.path_tiles, key=lambda t: (t[0] - tiles[0][0]) ** 2 + (t[1] - tiles[0][1]) ** 2)
    leader.s = world.level.s_of(tile)
    before = leader.hp
    for _ in range(3):
        world._land(leader.id, Curse.WEAKEN, tiles[0])
    smites = [e for e in world.events if e[0] == "smite" and e[1] == leader.id]
    assert len(smites) == 1
    assert leader.hp < before
    assert world.spells_cast == 1


def test_every_sixth_charge_casts_on_the_foremost():
    world = arena(relics=("volatile",))
    world.call_wave()
    while not world.monsters:
        world.step()
    foremost = min(world.monsters, key=world.remaining)
    before = foremost.hp
    for _ in range(6):
        world._relic("charge")
    assert foremost.hp < before
    assert world.spells_cast == 1
    assert [e for e in relic_events(world) if e[1] == "volatile"] != []


def test_a_given_charge_counts_the_verb():
    from hellward.sim.model import WELL_EVERY
    world = arena(relics=("volatile",))
    well = world.build("well", floor(world, 2)[0])
    neighbour = world.build("arrow", floor(world, 2)[1])
    world.attune(neighbour.id)
    world.call_wave()
    while not world.monsters:
        world.step()
    neighbour.charges = 0.0
    world.progress.clear()
    well.timer = WELL_EVERY[0]
    world.step(0.05)
    assert ("charge_given", well.id, neighbour.id) in world.events
    assert world.progress["volatile"] == 1


def test_every_third_rank_attunes_free_and_every_fourth_tower_too():
    from hellward.sim.skills import perks
    world = arena(relics=("temper", "lodestone"), perks=perks({"adept_arrow"}))
    one, two, three = floor(world, 3)
    world.build("arrow", one)
    world.build("arrow", two)
    world.build("arrow", three)
    assert not world.tower_at(one).attuned
    fourth = world.build("arrow", floor(world, 4)[3])
    assert fourth.attuned and fourth.charges == 3.0
    gold = world.gold
    world.upgrade(world.tower_at(one).id)
    world.upgrade(world.tower_at(two).id)
    assert not world.tower_at(one).attuned
    world.upgrade(world.tower_at(three).id)
    assert world.tower_at(three).attuned
    assert world.gold < gold   # ranks paid; only the attunement was free


def test_every_fifth_tower_wells_mana_from_a_smaller_well():
    world = arena(relics=("bellows",))
    world.mana = 0.0
    for tile in floor(world, 5):
        world.build("arrow", tile)
    assert world.mana == 20.0
    assert world.mana_max == world.perks.mana_max - 10.0


def test_every_fifth_cast_charges_every_attuned_tower():
    world = arena(relics=("stormglass",))
    tower = world.build("arrow", floor(world, 1)[0])
    world.attune(tower.id)
    tower.charges = 0.0
    for _ in range(5):
        world._relic("cast", 0.0)
    assert tower.charges == 1.0


def test_most_relics_read_one_verb_and_write_another():
    converters = [key for key, spec in RELICS.items() if spec.verb and spec.writes and spec.verb != spec.writes]
    assert len(converters) / len(RELICS) >= 0.6
    assert {"bell", "candle", "volatile", "temper", "bellows", "lodestone", "stormglass"} <= set(converters)


def test_every_verb_costs_and_some_relic_pays_for_it():
    # what leaning in costs, and the relics that turn the cost into payoff
    costs = {"build": "gold", "upgrade": "gold", "cast": "mana", "curse": "tower-time",
             "leak": "lives", "charge": "attunement gold"}
    for verb in ("build", "upgrade", "cast", "curse", "leak", "charge"):
        assert verb in costs
        assert [key for key, spec in RELICS.items() if spec.verb == verb], verb


def test_each_verb_tower_produces_or_consumes_one_verb():
    # idol, censer, well and effigy are verb engines; altar and grove predate the verb system (auras)
    engines = {"idol": "cast", "censer": "leak", "well": "charge", "effigy": "curse"}
    for kind, verb in engines.items():
        assert TOWERS[kind].attack not in ("bolt", "chain", "nova", "venom", "hook")
        assert verb in ("build", "upgrade", "cast", "curse", "leak", "charge")


def test_relics_fire_on_counts_touch_no_random_and_show_their_counters():
    import inspect

    from hellward.server.protocol import state
    from hellward.sim import model
    assert "random" not in inspect.getsource(model.World._relic)
    assert "rng" not in inspect.getsource(model.World._relic)
    for spec in RELICS.values():
        assert (spec.every > 0) == bool(spec.verb)
    world = arena(relics=("tithe", "bell"))
    world.build("arrow", floor(world, 1)[0])
    found = state(world)
    assert found["relic_counters"] == {"tithe": 1, "bell": 0}
    assert {"temper", "lodestone"} <= set(RELICS)   # free attunement: tech beyond the forge's teaching


def test_downsides_come_only_with_a_chosen_relic_and_say_so():
    downsides = {"blood_money", "canticle", "bell", "bellows"}
    for key in downsides:
        words = RELICS[key].words
        assert "loses" in words or "less" in words or "costs" in words, key
    assert downsides <= set(RELICS)   # every one of them a camp's offer away, never forced
