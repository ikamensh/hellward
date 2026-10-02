"""The physical family of stage 1: the Ballista's heavy bolt, the Hook Tower's pull and the Knife Post's knives at a
gate, through the World's step."""

from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.content import MONSTERS, TOWERS, Curse, Element, Group, Wave, felt_hit
from hellward.sim.level import Level
from hellward.sim.model import DOOR_STOP, HOOK, HOOK_PULL, SIM_DT, Monster, World

# A hall west to east, then south through an arch (s = 11) and east to the sanctuary.
FIELD = Level("Steel field", 16, 12, ((0, 2), (7, 2), (7, 10), (15, 10)), ((7, 6),))
CROSSING = FIELD.door_s[0]
BESIDE_ARCH = (9, 6)   # two tiles east of the arch: its spot on the route is the crossing
BESIDE_HALL = (8, 4)   # a tile east of the southward hall: its spot is s = 9
SPOT = 9.0


def field() -> World:
    location = replace(campaign.DOCKS, level=FIELD, waves=(Wave((Group("fallen", 1, 1.0),), 10),),
                       wave_names=("test",), life=1.0)
    world = World(location)
    world.gold = 10_000
    world.wave = 0
    world.wave_alive[0] = 0
    return world


def put(world: World, kind: str, s: float, hp: float = 1000.0) -> Monster:
    """A monster of this kind standing at ``s``, with life enough to live through the test."""
    m = Monster(world._id(), MONSTERS[kind], 0, 0.0, 0.0, hp, 99.0)
    m.s = s
    world.monsters.append(m)
    world.monsters.sort(key=lambda o: o.s, reverse=True)   # nearest the sanctuary first, as the world keeps them
    world.wave_alive[0] += 1
    return m


def hooks(world: World) -> list[tuple]:
    return [e for e in world.events if e[0] == "hook"]


def test_the_ballista_looses_a_heavy_bolt_at_the_foremost_that_armor_barely_dents():
    world = field()
    ballista = world.build("ballista", BESIDE_ARCH)
    behind, front = put(world, "overlord", CROSSING - 1.0), put(world, "overlord", CROSSING + 1.0)
    front.frozen = behind.frozen = 10.0
    world.step(SIM_DT)
    bolt = next(e[1] for e in world.events if e[0] == "bolt")
    assert bolt.kind == "ballista" and bolt.target == front.id
    origin, at = bolt.origin, bolt.last
    assert bolt.left == pytest.approx(((at[0] - origin[0]) ** 2 + (at[1] - origin[1]) ** 2) ** 0.5 / 14.0)
    hp = front.hp
    while world.bolts:
        world.step(SIM_DT)
    assert hp - front.hp == 7 - MONSTERS["overlord"].armor
    assert ballista.stats.damage == 7 and "armor" in TOWERS["ballista"].blurb


def test_a_hook_drags_the_foremost_small_monster_back_toward_its_spot_and_hits_it():
    """Small means one life, no boss, no leader: the overlord ahead and the shaman behind are left alone."""
    world = field()
    hook = world.build("hook", BESIDE_HALL)
    overlord = put(world, "overlord", SPOT + 2.5)
    fallen = put(world, "fallen", SPOT + 2.3)
    shaman = put(world, "shaman", SPOT + 1.5)
    for m in world.monsters:
        m.frozen = 10.0
    world.step(SIM_DT)
    assert hooks(world) == [("hook", hook.id, fallen.id, SPOT + 2.3, pytest.approx(SPOT + 2.3 - HOOK_PULL))]
    assert fallen.moved & HOOK
    assert fallen.max_hp - fallen.hp == felt_hit(hook.stats.damage, Element.PHYSICAL, fallen.kind)
    assert (overlord.s, shaman.s) == (SPOT + 2.5, SPOT + 1.5) and not overlord.moved | shaman.moved
    assert [m.s for m in world.monsters] == sorted((m.s for m in world.monsters), reverse=True)


def test_a_hook_takes_a_monster_once_and_waits_while_it_has_nothing_to_take():
    world = field()
    hook = world.build("hook", BESIDE_HALL)
    fallen = put(world, "fallen", SPOT + 2.5)
    fallen.frozen = 30.0
    world.step(SIM_DT)
    assert len(hooks(world)) == 1
    for _ in range(int(2 / hook.stats.rate / SIM_DT)):   # two of its periods: it would have hooked twice more
        world.step(SIM_DT)
    assert len(hooks(world)) == 1
    assert hook.cooldown == 0.0   # its timer waits for a monster to hook


def test_a_hook_takes_only_a_monster_a_tile_past_its_spot_and_never_pulls_it_past():
    world = field()
    hook = world.build("hook", BESIDE_ARCH)
    near = put(world, "gargoyle", CROSSING + 0.9)   # within a tile of the spot: left alone
    near.frozen = 10.0
    world.step(SIM_DT)
    assert not hooks(world)
    world = field()
    hook = world.build("hook", BESIDE_ARCH)
    close = put(world, "gargoyle", CROSSING + 1.2)
    close.frozen = 10.0
    world.step(SIM_DT)
    assert hooks(world) == [("hook", hook.id, close.id, CROSSING + 1.2, CROSSING)]   # a flyer too, to the spot


def test_a_walker_hooked_into_a_standing_gates_arch_stops_at_its_queue():
    world = field()
    world.build_door(0)
    hook = world.build("hook", BESIDE_ARCH)
    fallen = put(world, "fallen", CROSSING + 1.5)   # it slipped through before the gate stood
    fallen.jostle = 0.3
    fallen.frozen = 10.0
    world.step(SIM_DT)
    stop = CROSSING - DOOR_STOP - fallen.jostle
    assert hooks(world) == [("hook", hook.id, fallen.id, CROSSING + 1.5, pytest.approx(stop))]


def test_a_hook_leaves_a_monster_at_a_gate_alone():
    world = field()
    world.build_door(0)
    world.build("hook", (9, 4))   # its spot is two tiles before the arch
    fallen = put(world, "fallen", CROSSING - DOOR_STOP)
    fallen.door = 0
    world.step(SIM_DT)
    assert not hooks(world) and not fallen.moved


def test_a_weakened_hook_pulls_a_weakened_share():
    world = field()
    hook = world.build("hook", BESIDE_HALL)
    hook.curses[Curse.WEAKEN] = 5.0
    fallen = put(world, "fallen", SPOT + 2.5)
    fallen.frozen = 10.0
    world.step(SIM_DT)
    (_, _, _, before, after), = hooks(world)
    assert before - after == pytest.approx(HOOK_PULL * hook.damage_mult())


def test_a_knife_post_throws_at_a_monster_standing_at_a_gate_and_hits_it_twice_as_hard():
    world = field()
    world.build_door(0)
    knife = world.build("knife", BESIDE_ARCH)
    zombie = put(world, "zombie", CROSSING - DOOR_STOP)   # battering the gate
    zombie.door = 0
    bat = put(world, "bat", CROSSING + 1.0)   # the foremost, flying over the gate
    bat.frozen = 0.0
    zombie.frozen = 0.0
    world.step(SIM_DT)
    bolt = next(e[1] for e in world.events if e[0] == "bolt")
    assert bolt.kind == "knife" and bolt.target == zombie.id
    while world.bolts:
        world.step(SIM_DT)
    assert zombie.max_hp - zombie.hp == felt_hit(knife.stats.damage, Element.PHYSICAL, zombie.kind, 2.0) == 4
    assert bat.hp == bat.max_hp


def test_a_knife_post_throws_at_the_foremost_when_nothing_stands():
    world = field()
    knife = world.build("knife", BESIDE_ARCH)
    behind, front = put(world, "zombie", CROSSING - 1.0), put(world, "zombie", CROSSING + 1.0)
    world.step(SIM_DT)
    bolt = next(e[1] for e in world.events if e[0] == "bolt")
    assert bolt.target == front.id
    while world.bolts:
        world.step(SIM_DT)
    assert front.max_hp - front.hp == knife.stats.damage == 2


def test_a_knife_post_takes_a_held_monster_for_a_standing_one():
    """Frozen (an orb, a grove's root) stands as still as battering a gate."""
    world = field()
    knife = world.build("knife", BESIDE_ARCH)
    behind, front = put(world, "zombie", CROSSING - 1.0), put(world, "zombie", CROSSING + 1.0)
    behind.frozen = 5.0
    world.step(SIM_DT)
    assert next(e[1] for e in world.events if e[0] == "bolt").target == behind.id
    while world.bolts:
        world.step(SIM_DT)
    assert behind.max_hp - behind.hp == 2 * knife.stats.damage and front.hp == front.max_hp
