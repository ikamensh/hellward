"""A defence follows each monster's committed route."""

from dataclasses import replace

import pytest

from hellward.sim.campaign import CATHEDRAL
from hellward.sim import planner
from hellward.sim.content import Group, MONSTERS, Wave
from hellward.sim.level import Level, Route
from hellward.sim.model import DOOR_STOP, Monster, Refused, World


def _yard() -> Level:
    return Level("yard", 9, 9, ((0, 7), (8, 7)), (),
                 extra_routes=(Route("north", ((0, 1), (6, 1), (6, 7), (8, 7))),
                               Route("north_detour", ((0, 1), (2, 1), (2, 4), (5, 4), (5, 7), (8, 7)))))


def test_a_monster_keeps_its_route_and_position_in_a_planners_clone():
    """A curse rollout sees the same off-main position as the live defence."""
    world = World(replace(CATHEDRAL, level=_yard(), start_gold=100))
    kind = MONSTERS["fallen"]
    monster = Monster(123, kind, 0, 0.0, 0.0, kind.hp, 0.0, route="north")
    monster.s = 3.0
    world.monsters.append(monster)

    assert world.position(monster) == (3.5, 1.5)
    twin = world.clone()
    assert twin.monsters[0].route == "north"
    assert twin.position(twin.monsters[0]) == (3.5, 1.5)


def test_a_tower_targets_the_nearby_route_not_the_same_distance_on_a_far_route():
    """Reach is geometric even when two monsters have the same route-local distance."""
    world = World(replace(CATHEDRAL, level=_yard(), start_gold=100))
    tower = world.build("pyre", (4, 2))
    kind = MONSTERS["fallen"]
    main = Monster(201, kind, 0, 0.0, 0.0, kind.hp, 0.0)
    side = Monster(202, kind, 0, 0.0, 0.0, kind.hp, 0.0, route="north")
    main.s = side.s = 4.0
    main.frozen = side.frozen = 1.0
    world.monsters.extend((main, side))

    world.step()

    assert world.bolts and world.bolts[0].tower == tower.id
    assert world.bolts[0].target == side.id


def test_wanderers_choose_seeded_routes_from_their_entrance_while_runners_go_direct():
    """An optional entrance never admits an unrelated spawn, and a runner keeps its authored route."""
    waves = (Wave((Group("fallen", 16, 0.05, route="north"), Group("bat", 1, 1.0, route="north")), 0),)
    location = replace(CATHEDRAL, level=_yard(), waves=waves, wave_names=("The yard",))

    def spawned(seed: int) -> list[tuple[str, str]]:
        world = World(location, seed=seed)
        world.call_wave()
        while world.schedule:
            world.step()
        return [(monster.kind.key, monster.route) for monster in world.monsters]

    routes = spawned(5)
    assert routes == spawned(5)
    assert {route for kind, route in routes if kind == "fallen"} == {"north", "north_detour"}
    assert [(kind, route) for kind, route in routes if kind == "bat"] == [("bat", "north")]


def test_wander_routes_do_not_change_when_combat_uses_other_random_draws():
    """The spawn's route is a map choice, independent of later combat randomness."""
    waves = (Wave((Group("fallen", 16, 0.05, route="north"),), 0),)
    location = replace(CATHEDRAL, level=_yard(), waves=waves, wave_names=("The yard",))
    first, second = World(location, seed=17), World(location, seed=17)
    for _ in range(40):
        second.rng.random()
    for world in (first, second):
        world.call_wave()
        while world.schedule:
            world.step()
    assert [m.route for m in first.monsters] == [m.route for m in second.monsters]


def test_a_detouring_monster_leaks_only_at_the_end_of_its_own_route():
    """Passing the main route's distance does not mean the monster reached the sanctuary."""
    waves = (Wave((Group("fallen", 1, 1.0, route="north"),), 0),)
    location = replace(CATHEDRAL, level=_yard(), waves=waves, wave_names=("The yard",))
    world = World(location, seed=1)
    world.call_wave()
    for _ in range(140):
        world.step()
    assert len(world.monsters) == 1
    assert world.monsters[0].s > world.level.length
    assert world.lives > 0

    for _ in range(120):
        world.step()
    assert world.monsters == []
    assert world.outcome == "victory"


def test_a_gate_cannot_be_built_around_a_monster_on_another_route():
    """A shared arch has a different distance from each entrance."""
    level = Level("yard", 9, 9, ((0, 4), (4, 4), (4, 7), (8, 7)), ((4, 5),),
                  extra_routes=(Route("north", ((0, 1), (1, 1), (4, 2), (4, 7), (8, 7))),))
    world = World(replace(CATHEDRAL, level=level, start_gold=100))
    kind = MONSTERS["fallen"]
    monster = Monster(500, kind, 0, 0.0, 0.0, kind.hp, 0.0, route="north")
    monster.s = level.crossings("north")[0][1]
    world.monsters.append(monster)

    with pytest.raises(Refused, match="arch"):
        world.build_door(0)


def test_a_leader_plans_against_towers_near_its_committed_route():
    """The curse shortlist uses the leader's side-route position after its chant."""
    world = World(replace(CATHEDRAL, level=_yard(), start_gold=100))
    tower = world.build("pyre", (4, 2))
    kind = MONSTERS["shaman"]
    leader = Monster(600, kind, 0, 0.0, 0.0, kind.hp, 0.0, route="north")
    leader.s = 4.0
    world.monsters.append(leader)
    world.wave_alive[0] = 1

    assert planner.reachable(world, leader) == [tower]
    assert any(option.estimate > 0 for option in planner.candidates(world, leader))
    decision = planner.decide(world, leader.id, shortlist=1, timing=False)
    assert decision.leader == leader.id and decision.considered > 0


def test_a_gate_breaks_under_a_side_route_monster_without_stalling_the_world():
    """The next step may continue after a route-specific gate crossing breaks its gate."""
    level = Level("yard", 9, 9, ((0, 4), (4, 4), (4, 7), (8, 7)), ((4, 5),),
                  extra_routes=(Route("north", ((0, 1), (1, 1), (4, 2), (4, 7), (8, 7))),))
    world = World(replace(CATHEDRAL, level=level, start_gold=100))
    door = world.doors[0]
    door.built, door.hp = True, 0.01
    kind = MONSTERS["fallen"]
    monster = Monster(700, kind, 0, 0.0, 0.0, kind.hp, 0.0, route="north")
    monster.s = level.crossings("north")[0][1] - DOOR_STOP
    world.monsters.append(monster)

    world.step()

    assert door.rubble and not door.built
    assert any(event[0] == "door_broken" for event in world.events)


def test_a_frost_bolt_chills_its_side_route_target_on_impact():
    """Single-target frost keeps its slow after the old nova attack is removed."""
    location = replace(CATHEDRAL, level=_yard(), start_gold=100,
                       arsenal=replace(CATHEDRAL.arsenal, towers=("frost",)))
    world = World(location)
    tower = world.build("frost", (4, 2))
    kind = replace(MONSTERS["skeleton"], hp=1000)
    monster = Monster(800, kind, 0, 0.0, 0.0, kind.hp, 0.0, route="north")
    monster.s = 4.0
    world.monsters.append(monster)

    for _ in range(20):
        world.step()
        if monster.chill_left > 0:
            break

    assert monster.chill == pytest.approx(tower.stats.chill * kind.taken(tower.kind.element))
    assert monster.chill_left > 0
