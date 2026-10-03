"""The verbs' engine: every happening counts; venom past its maximum bursts, a shatter spends chill."""

from dataclasses import replace

from hellward.sim import campaign
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import MAX_POISON_STACKS, SPELLS, TOWERS, Element, Group, Wave
from hellward.sim.level import Level
from hellward.sim.model import IDOL_EVERY, OVERLOAD, World
from hellward.sim.skills import perks


def arena(kind: str = "skeleton", count: int = 3, relics: tuple[str, ...] = ()) -> World:
    level = Level("Verb field", 25, 14,
                  ((0, 2), (9, 2), (9, 8), (19, 8), (19, 11), (24, 11)), ((9, 5),))
    waves = (Wave((Group(kind, count, 0.5),), 10),)
    arsenal = replace(campaign.CATHEDRAL.arsenal, towers=tuple(TOWERS), spells=tuple(SPELLS), gates=True)
    location = replace(campaign.CATHEDRAL, level=level, arsenal=arsenal, waves=waves, wave_names=("pack",))
    world = World(location, seed=7, relics=relics)
    world.gold = 10000
    return world


def floor(world: World) -> tuple[int, int]:
    return next((x, y) for y in range(14) for x in range(25) if world.buildable(x, y))


def pack(world: World, count: int = 3) -> None:
    world.call_wave()
    while len(world.monsters) < count:
        world.step()


def test_a_shatter_consumes_the_corpse_and_its_chill():
    world = arena()
    world.perks = perks({"unlock_frost", "adept_cold", "master_cold", "glacial_spike", "shatter"})
    pack(world)
    dying = next(m for m in world.monsters if m.hp > 0)
    dying.chill_left = 5.0
    world._hurt(dying, 10000, Element.PHYSICAL)
    assert ("shatter", dying.id, world.position(dying)) in world.events
    assert world.verb_count["corpse"] == 1
    assert world.verb_count["debuff"] == 1


def test_a_kill_alone_counts_no_corpse_but_an_explosion_counts_one():
    world = arena()
    pack(world)
    world._hurt(world.monsters[0], 10000, Element.PHYSICAL)
    assert world.verb_count.get("corpse", 0) == 0
    assert world.kills == 1
    world.perks = perks({"unlock_altar", "adept_bone", "master_bone", "life_tap", "corpse_explosion"})
    dying = next(m for m in world.monsters if m.hp > 0)
    dying.amplified = 5.0
    world._hurt(dying, 10000, Element.PHYSICAL)
    assert world.verb_count["corpse"] == 1


def test_venom_past_its_maximum_bursts_and_counts_debuff():
    world = arena()
    pack(world)
    host, witness = world.monsters[0], world.monsters[1]
    for m in world.monsters:
        m.s = 1.0
    for _ in range(MAX_POISON_STACKS):
        world._poison(host, 1.0, 5.0)
    assert len(host.poison) == MAX_POISON_STACKS
    hurt = witness.hp
    world._poison(host, 1.0, 5.0)   # one past the maximum bursts them all
    assert ("overload", host.id, MAX_POISON_STACKS + 1) in world.events
    assert world.verb_count["debuff"] == 1
    assert host.poison == []
    assert witness.hp == hurt - (MAX_POISON_STACKS + 1) * OVERLOAD


def test_an_overload_kill_bursts_no_further():
    world = arena()
    pack(world)
    host, witness = world.monsters[0], world.monsters[1]
    for m in world.monsters:
        m.s = 1.0
    for _ in range(MAX_POISON_STACKS):
        world._poison(host, 1.0, 5.0)
        world._poison(witness, 1.0, 5.0)
    witness.hp = 1.0
    world._poison(host, 1.0, 5.0)   # the burst kills the witness, stacks and all
    assert witness.hp <= 0
    assert world.verb_count["debuff"] == 1   # the witness's death bursts nothing in turn


def test_casts_and_leaks_count_as_verbs():
    world = arena()
    idol = world.build("idol", floor(world))
    pack(world)
    idol.timer = IDOL_EVERY[0] - 0.01
    world.step(0.05)
    assert world.verb_count["cast"] == 1
    stray = world.monsters[0]
    stray.s = world.level.route(stray.route).length + 1.0
    lives = world.lives
    world.step()
    assert world.lives < lives   # it leaked
    assert world.verb_count["leak"] == 1


def test_a_clone_carries_the_verbs_count():
    world = arena()
    pack(world)
    stray = world.monsters[0]
    stray.s = world.level.route(stray.route).length + 1.0
    world.step()
    assert world.clone().verb_count == {"leak": 1}


def test_the_charnel_pyre_bursts_chilled_deaths_with_no_skill_and_pays_every_tenth():
    world = arena(count=11, relics=("charnel",))
    pack(world, 11)
    gold = world.gold
    for m in list(world.monsters):
        m.chill_left = 5.0   # full life: the 6% bursts spare the neighbours, who count in turn
        world._hurt(m, 10000, Element.PHYSICAL)
    assert world.verb_count["corpse"] == 11
    assert world.verb_count["debuff"] == 11
    assert world.gold == gold + 11 * m.kind.bounty + 12   # bounties, and the tenth corpse pays once
    assert ("relic", "charnel", "The Charnel Pyre") in world.events


def test_the_charnel_pyre_counts_once_beside_the_shatter_skill():
    world = arena(relics=("charnel",))
    world.perks = perks({"unlock_frost", "adept_cold", "master_cold", "glacial_spike", "shatter"})
    pack(world)
    dying = next(m for m in world.monsters if m.hp > 0)
    dying.chill_left = 5.0
    world._hurt(dying, 10000, Element.PHYSICAL)
    assert world.verb_count["corpse"] == 1   # the skill's burst, not two
    assert world.verb_count["debuff"] == 1


def test_the_hoarfrost_wells_mana_every_tenth_debuff():
    world = arena(relics=("hoarfrost",))
    world.mana = 0.0
    for _ in range(9):
        world._relic("debuff")
    assert world.mana == 0.0
    world._relic("debuff")
    assert world.mana == 10.0
    assert ("relic", "hoarfrost", "The Hoarfrost") in world.events


def test_one_landing_counts_each_tower_it_takes():
    from hellward.sim.content import Curse
    world = arena("shaman", relics=("spite",))
    tiles = [(x, y) for y in range(14) for x in range(25) if world.buildable(x, y)][:2]
    for tile in tiles:
        world.build("arrow", tile)
    pack(world, 1)
    lid = world.monsters[0].id
    spot = tiles[0]
    tile = min(world.level.path_tiles, key=lambda t: (t[0] - spot[0]) ** 2 + (t[1] - spot[1]) ** 2)
    world.monster(lid).s = world.level.s_of(tile)
    world.mana = 0.0
    world._land(lid, Curse.WEAKEN, spot)
    assert world.curses_landed == 1
    assert world.verb_count["curse"] == 2   # both neighbours taken
    assert world.mana == 40.0   # the second tower cursed fires the Spite at once
