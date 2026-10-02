"""Whole defences, played by the scripted players through a person's hands."""

import math
import random
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from hellward.sim import planner
from hellward.sim.breaches import BREACHES
from hellward.sim.campaign import LOCATIONS, ORDER, g
from hellward.sim.content import SPELLS, Wave
from hellward.sim.level import Level, Route
from hellward.sim.model import SIM_DT, World
from hellward.sim.players import PLAYERS
from hellward.sim.players.adaptive import ORDERS, Adaptive
from hellward.sim.players.hands import Hands, defend
from hellward.sim.players.planned import PLANS, THINK, Plan as PlannedPlan, Planned, load
from hellward.sim.players.warden import fingerprint, load_plans
from hellward.sim.skills import SKILLS, can_learn, check, cost

GRAVEYARD_SIGNS = Level("Sign timing", 25, 14, ((0, 10), (10, 10), (10, 3), (24, 3)), ((10, 7),))

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import plan_player  # noqa: E402
import warden_plans  # noqa: E402


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_the_ordinary_player_defends_every_location_to_its_end_against_smart_leaders(key):
    location = LOCATIONS[key]
    world, record = defend(location, PLAYERS["ordinary"](1), seed=1, sigils=0, planner=planner.smart)
    assert world.outcome in ("victory", "defeat")
    assert world.outcome == "defeat" or world.wave == len(location.waves) - 1
    assert record.chants >= record.landed   # it may fall before a leader comes, or before its towers kill anything


def test_the_warden_holds_tristram():
    world, record = defend(LOCATIONS["tristram"], PLAYERS["warden"](1), seed=1, sigils=0, planner=planner.smart)
    assert world.outcome == "victory"
    assert record.landed > 0


def test_warden_search_starts_at_real_difficulty_when_the_draft_loses():
    assert warden_plans.starting_life(None, [0.0, 0.0, 0.0, 0.0]) == 1.0
    with pytest.raises(ValueError, match="positive"):
        warden_plans.starting_life(0.0, [0.0])


def test_every_stored_warden_plan_is_for_todays_map_and_its_sigils():
    """A plan searched on a map that has changed since is not played: search it again (tools/warden_plans.py)."""
    for key, plan in load_plans().items():
        name, sigils = key.split("/")
        location = LOCATIONS[name]
        assert plan.map == fingerprint(location), key
        assert cost(plan.skills) <= int(sigils), key
        assert all(s.kind in location.arsenal.towers for s in plan.steps if s.what == "build"), key


def test_warden_plan_is_invalidated_when_the_walkable_hall_changes():
    """A build searched for one corridor layout must not be reused on another."""
    location = LOCATIONS["tristram"]
    level = location.level
    extra = next((x, y) for y in range(1, level.height - 1) for x in range(1, level.width - 1)
                 if level.buildable(x, y))
    revised = replace(level, halls=level.walkable_tiles | {extra})
    assert fingerprint(replace(location, level=revised)) != fingerprint(location)


def test_a_leaders_sign_reaches_a_player_only_a_persons_reaction_later():
    pack = Wave((g("skeleton", 4), g("priest", 2, 4.0, start=1.0)), 10)
    world = World(replace(LOCATIONS["graveyard"], level=GRAVEYARD_SIGNS,
                          waves=(pack,), wave_names=("pack",)), seed=3, planner=planner.smart)
    hands = Hands(world, react=0.6)
    world.gold = 1000
    world.build("arrow", (9, 9))
    world.call_wave()
    seen_at = {}
    signed_at = {}
    stood = {}
    while world.outcome is None and world.time < 60 and len(seen_at) < 3:
        world.step(SIM_DT)
        for e in world.events:
            if e[0] in ("ponder", "chant"):
                signed_at.setdefault((e[1], e[0]), world.time)
                stood[(e[1], e[0])] = world.position(world.monster(e[1]))
        hands.observe(world.events)
        world.events.clear()
        for sign in hands.threats():
            seen_at.setdefault((sign.leader, sign.kind), world.time)
            assert sign.at == stood[(sign.leader, sign.kind)]   # aimed where it stood, not where it walks now
    assert seen_at
    for key, seen in seen_at.items():
        assert seen >= signed_at[key] + 0.6 - 1e-6


def test_a_defence_still_undecided_at_the_limit_is_an_error():
    with pytest.raises(RuntimeError, match="undecided"):
        defend(LOCATIONS["tristram"], PLAYERS["ordinary"](1), seed=1, sigils=0, planner=None, limit=5.0)


FORBIDDEN = (".asking", ".ask_left", ".chant_", ".cooldown", "planner", ".clone(", ".forced", ".rng", "decide(", "rollout(")


@pytest.mark.parametrize("path", sorted((Path(__file__).parent.parent / "hellward/sim/players").glob("*.py")),
                         ids=lambda p: p.name)
def test_a_player_reads_no_leaders_mind_and_no_future(path):
    """A person sees the dots and the beam, not a leader's planner, cooldown or chant clock, and cannot copy the world."""
    if path.name == "hands.py":
        return   # the harness itself reads the events a person would see
    source = path.read_text()
    assert not [word for word in FORBIDDEN if word in source]


def test_the_planned_player_holds_tristram_with_its_searched_build():
    """The stored build wins on evaluation seeds it did not see during its search."""
    for seed in range(1000, 1008):
        world, _ = defend(LOCATIONS["tristram"], PLAYERS["planned"](seed), seed=seed, sigils=0,
                          planner=planner.smart)
        assert world.outcome == "victory", seed


def test_the_planned_player_holds_temple_with_its_searched_build():
    """The finale's stored build wins most unseen smart-leader defences at the game's real HP."""
    victories = 0
    failed = []
    for seed in range(1000, 1008):
        world, _ = defend(LOCATIONS["temple"], PLAYERS["planned"](seed), seed=seed, sigils=33,
                          planner=planner.smart)
        victories += world.outcome == "victory"
        if world.outcome != "victory":
            failed.append(seed)
    assert victories >= 6, failed


def test_planned_player_spends_smite_on_a_high_stakes_boss_before_it_nears_the_exit():
    """A boss that costs the sanctuary twenty lives deserves damage before a last-second rescue is possible."""
    location = replace(LOCATIONS["temple"], waves=(Wave((g("bone_priest", 1),), 10),), wave_names=("Boss",))
    world = World(location, planner=None)
    hands = Hands(world, react=0.0)
    player = Planned(plan=PlannedPlan([], [], [100.0]))
    world.call_wave()
    world.step(SIM_DT)
    hands.observe(world.events)
    world.events.clear()
    boss = world.monsters[0]
    assert world.remaining(boss) > world.level.route(boss.route).length / 2
    world.mana = SPELLS["smite"].mana + 1

    player.act(hands)

    assert hands.record.spells["smite"] == 1


def test_planned_player_rebuilds_past_a_boss_in_the_final_stretch():
    """A committed build can sell spent positions and keep firing along a boss's remaining route."""
    location = replace(LOCATIONS["temple"], waves=(Wave((g("bone_priest", 1),), 10),), wave_names=("Boss",))
    world = World(location, planner=None)
    route = world.level.route("main")
    halfway = route.length / 2
    behind = next((x, y) for y in range(world.level.height) for x in range(world.level.width)
                  if world.level.buildable(x, y) and route.coverage((x, y), 3.0)
                  and all(end < halfway for _, end in route.coverage((x, y), 3.0)))
    world.gold = 1000
    old = world.build("arrow", behind)
    world.gold = world.cost("arrow") - 1
    world.mana = 0
    world.call_wave()
    world.step(SIM_DT)
    boss = world.monsters[0]
    boss.s = halfway
    hands = Hands(world, react=0.0)

    player = Planned(plan=PlannedPlan([], [], [100.0]))
    player.act(hands)

    assert old.id not in world.towers
    assert not world.towers   # one sale per decision; the next look buys the replacement
    for _ in range(5):
        world.step(SIM_DT)
        hands.observe(world.events)
        world.events.clear()
    player.act(hands)
    assert any(any(end > boss.s for _, end in route.coverage(t.tile, t.stats.range))
               for t in world.towers.values())


def test_planned_player_skips_the_rank_of_a_tower_sold_during_the_final_stretch():
    """A planned rank no longer applies after that tower has funded an endgame replacement."""
    location = replace(LOCATIONS["temple"], waves=(Wave((g("bone_priest", 1),), 10),), wave_names=("Boss",))
    world = World(location, planner=None)
    route = world.level.route("main")
    halfway = route.length / 2
    tile = next((x, y) for y in range(world.level.height) for x in range(world.level.width)
                if world.level.buildable(x, y) and route.coverage((x, y), 3.0)
                and all(end < halfway for _, end in route.coverage((x, y), 3.0)))
    world.gold = 1000
    tower = world.build("arrow", tile)
    world.gold = world.cost("arrow") - 1
    world.mana = 0
    world.call_wave()
    world.step(SIM_DT)
    world.monsters[0].s = halfway
    player = Planned(plan=PlannedPlan([], [("build", "arrow", tile), ("rank", tile)], [100.0]))
    player.next = 1
    hands = Hands(world, react=0.0)

    player.act(hands)
    assert tower.id not in world.towers
    world.monsters.clear()
    world.time += THINK
    player.act(hands)

    assert player.next == 2


def test_the_adaptive_player_holds_tristram():
    world, record = defend(LOCATIONS["tristram"], PLAYERS["adaptive"](1), seed=1, sigils=0, planner=planner.smart)
    assert world.outcome == "victory"
    assert world.lives >= 10   # the open-field opening still earns at least two sigils


def test_the_apprentice_holds_tristram():
    world, _ = defend(LOCATIONS["tristram"], PLAYERS["apprentice"](1), seed=1, sigils=0, planner=planner.smart)
    assert world.outcome == "victory"


def assert_fits(plan, location):
    assert set(plan.skills) <= set(SKILLS)
    assert len(plan.calls) == len(location.waves)
    built = set()
    ranks = {}
    for step in plan.steps:
        if step[0] == "build":
            assert step[1] in location.arsenal.towers
            assert location.level.buildable(*step[2]) and step[2] not in built
            built.add(step[2])
        elif step[0] == "rank":
            assert step[1] in built
            ranks[step[1]] = ranks.get(step[1], 0) + 1
            assert ranks[step[1]] <= 2
        else:
            assert location.arsenal.gates and 0 <= step[1] < len(location.level.doors)


@pytest.mark.parametrize("path", sorted(PLANS.glob("*.json")), ids=lambda p: p.stem)
def test_every_stored_plan_fits_its_location(path):
    """A plan found for an older map or arsenal would build nowhere; the player would stand idle."""
    if path.name in ("warden.json", "adaptive.json"):
        return
    assert_fits(load(path.stem), LOCATIONS[path.stem])


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_the_plan_search_only_ever_makes_plans_that_fit(key):
    location = LOCATIONS[key]
    rng = random.Random(key)
    tiles = plan_player.ranked_tiles(location, 3.0, 3.0)[:plan_player.TOP_TILES]
    for plan in plan_player.first_plans(location):
        for _ in range(60):
            plan = plan_player.mutate(plan, location, rng, tiles)
            assert_fits(plan, location)


def test_plan_search_scores_build_tiles_beside_a_second_entrance():
    level = Level("Two approaches", 9, 9, ((0, 4), (8, 4)), (),
                  extra_routes=(Route("side", ((0, 6), (4, 6), (8, 4))),
                                Route("breach", ((4, 0), (4, 2), (8, 4)))))
    location = replace(LOCATIONS["tristram"], level=level)
    assert level.buildable(2, 7) and level.buildable(3, 1)
    assert not level.route("main").coverage((2, 7), 1.1)
    assert level.route("side").coverage((2, 7), 1.1)
    assert level.route("breach").coverage((3, 1), 1.1)
    ranked = plan_player.ranked_tiles(location, 1.1, 0.0)
    assert (2, 7) in ranked
    assert (3, 1) not in ranked   # the optional entrance is sealed in an ordinary search defence


def test_planned_player_spends_sigils_only_on_skills_open_at_the_location():
    from hellward.sim.players.planned import Plan, Planned

    plan = Plan(["adept_fire", "master_fire", "fire_ball", "warmth", "soul_harvest"], [], [])
    early = Planned(plan=plan).skills(LOCATIONS["cathedral"], 6)
    assert early == frozenset({"adept_fire", "master_fire", "warmth", "soul_harvest"})
    late = Planned(plan=plan).skills(LOCATIONS["jungle"], 6)
    assert late == frozenset({"adept_fire", "master_fire", "fire_ball", "warmth"})


def test_warden_draft_and_search_mutations_cannot_buy_future_skills():
    from hellward.sim.players.warden import Plan, Warden, draft_skills

    location = LOCATIONS["cathedral"]
    assert all(SKILLS[key].first_location <= 2 for key in draft_skills(location, 6))
    chosen = Warden(plan=Plan(frozenset({"adept_fire", "master_fire", "fire_ball"}), ())).skills(location, 6)
    assert chosen == frozenset({"adept_fire", "master_fire"})
    mutated = warden_plans.reskill(frozenset({"adept_fire", "master_fire", "fire_ball"}), 6,
                                   random.Random(1), stage=2)
    assert all(SKILLS[key].first_location <= 2 for key in mutated)
    stale = Plan(frozenset({"adept_fire", "master_fire", "fire_ball"}), ())
    assert all(SKILLS[key].first_location <= 2
               for key in warden_plans.mutate(stale, location, 6, random.Random(2)).skills)


def test_scripted_players_wait_for_the_local_gate_price(monkeypatch):
    from hellward.sim.content import DOOR
    from hellward.sim.players.planned import Plan as PlannedPlan, Planned
    from hellward.sim.players.warden import Plan as WardenPlan, Step, Warden

    location = LOCATIONS["catacombs"]
    world = World(location)
    world.gold = DOOR.cost
    assert world.gold < world.door_cost

    planned = Planned(plan=PlannedPlan([], [("gate", 0)], [100.0] * len(location.waves)))
    planned._build(world)
    warden = Warden(plan=WardenPlan(frozenset(), (Step("gate", door=0),)))
    warden.skills(location, 0)
    warden._spend(world)

    adaptive = Adaptive("mixed")
    monkeypatch.setattr(adaptive, "_guarded", lambda index: True)
    assert adaptive._keep(world) == world.door_cost
    monkeypatch.setattr(world, "build_door", lambda index: pytest.fail("gate attempted before its local price"))
    adaptive._gates(world)
    assert not world.doors[0].built


@pytest.mark.parametrize("site", ("graveyard", "catacombs"))
def test_adaptive_forecasts_announced_breach_foes_and_prices_their_route(site):
    spec = BREACHES[site]
    wave = Wave((g("skeleton", 1),), 0)
    location = replace(LOCATIONS[site], waves=(wave,) * (spec.after_wave + 3),
                       wave_names=tuple(f"wave {i}" for i in range(spec.after_wave + 3)))
    world = World(location, seed=4)
    bot = Adaptive("mixed")
    bot.think_at = float("inf")   # drive the short fixture's waves ourselves
    hands = Hands(world, react=0.6)
    bot.act(hands)
    assert bot.study is not None and spec.elite.kind not in bot.study.roster

    for _ in range(spec.after_wave + 1):
        world.call_wave()
        while world.schedule:
            world.step()
        for monster in list(world.monsters):
            world._hurt(monster, monster.hp, None)
        world.step()
        bot.act(hands)
    assert world.breach_offered
    world.choose_breach("trophy")
    bot.act(hands)
    assert bot.study is not None and spec.elite.kind in bot.study.roster
    assert bot.study.route_share[spec.elite.kind]["breach"] > 0
    for group in spec.pack:
        assert bot.study.route_share[group.kind]["breach"] > 0

    world.call_wave()
    bot.act(hands)
    announced = bot._to_come(world)
    assert len(announced) == len(world.schedule)
    assert (spec.elite.kind, "breach") in announced
    while not any(monster.route == "breach" for monster in world.monsters):
        world.step()
        assert world.wave_time < 6
    side = next(monster for monster in world.monsters if monster.route == "breach")
    assert side.kind.key in bot.ahead
    assert bot.threat(side) > 0
    bot.act(hands)

    while world.schedule:
        world.step()
    for monster in list(world.monsters):
        world._hurt(monster, monster.hp, None)
    world.step()
    world.call_wave()
    bot.act(hands)
    assert bot.study is not None and spec.elite.kind not in bot.study.roster
    assert all(route != "breach" for _, route in bot._to_come(world))


@pytest.mark.parametrize("order", ["", *ORDERS])
def test_the_adaptive_player_learns_within_its_sigils_and_the_tree(order):
    """Every themed order, and the planned one (empty), buys a set the tree allows, and leaves no sigil it could
    still spend, at every budget and place."""
    for stage, location_key in enumerate(ORDER):
        location = LOCATIONS[location_key]
        for sigils in range(0, 37):
            learned = Adaptive(order).skills(location, sigils)
            check(learned)
            assert cost(learned) <= sigils
            assert all(SKILLS[key].first_location <= stage for key in learned)
            assert not [key for key in SKILLS if can_learn(learned, key, sigils, stage)]


@pytest.mark.parametrize("name", sorted(PLAYERS))
def test_every_player_plays_an_act_two_location_with_its_towers_to_an_outcome(name):
    """Kurast Docks offers the Bone Altar; every player defends its first two waves through the hands, whatever it
    makes of the altar (a whole Act II defence per player, uncompiled, is the balance tools' work)."""
    docks = LOCATIONS["docks"]
    short = replace(docks, waves=docks.waves[:2], wave_names=docks.wave_names[:2])
    player = PLAYERS[name](1)
    if name == "planned":
        player.plan = load("docks")   # the short waves are not what the stored plan was searched on
    world, _ = defend(short, player, seed=1, sigils=18, planner=planner.smart)
    assert world.outcome in ("victory", "defeat")


def test_the_veteran_holds_tristram_and_sees_a_sign_no_sooner_than_a_person_slower_than_the_strong_ones():
    from hellward.sim.players.hands import react_for
    veteran = PLAYERS["veteran"](1)
    assert all(0.8 <= react_for(seed, veteran.reaction) <= 1.2 for seed in range(50))
    world, _ = defend(LOCATIONS["tristram"], veteran, seed=1, sigils=0, planner=planner.smart)
    assert world.outcome == "victory"


def test_the_veteran_drafts_its_build_and_never_reads_the_wardens_stored_plans():
    from hellward.sim.players.warden import draft_skills
    veteran = PLAYERS["veteran"](1)
    assert veteran.plans == {}
    assert veteran.skills(LOCATIONS["cathedral"], 6) == draft_skills(LOCATIONS["cathedral"], 6)


def test_the_corner_player_builds_arrows_that_cover_tristrams_bends():
    """The wide monster halls leave plots beside bends for the corner player's opening."""
    corner = PLAYERS["corner"](1)
    location = LOCATIONS["tristram"]
    world, _ = defend(location, corner, seed=1, sigils=0, planner=planner.smart)
    arrows = [t for t in world.towers.values() if t.kind.key == "arrow"]
    bends = [tile for route in location.level.routes for tile in route.waypoints[1:-1]]
    assert arrows
    assert all(any(route.coverage(tower.tile, tower.reach) for route in location.level.routes)
               for tower in arrows)
    assert any(math.dist(tower.tile, bend) <= tower.reach for tower in arrows for bend in bends)


def test_spacing_marks_down_a_tile_beside_a_tower_where_a_curse_would_catch_both():
    from hellward.sim.players.spacing import max_curse_radius, score_with_spacing
    cathedral = LOCATIONS["cathedral"]   # its leaders curse with Weaken and Decrepify, radius 1.5
    assert max_curse_radius(cathedral) == 1.5
    beside = score_with_spacing(10.0, [(5, 5)], (6, 6), cathedral)
    apart = score_with_spacing(10.0, [(5, 5)], (7, 5), cathedral)
    assert beside < apart == 10.0


def test_a_curse_scale_of_zero_curses_only_the_marked_tile():
    world = World(LOCATIONS["tristram"], seed=1, curse_scale=0.0)
    world.gold = 1000
    level = world.level
    marked = next((x, y) for y in range(level.height) for x in range(level.width)
                  if all(level.buildable(*tile) for tile in ((x, y), (x + 1, y), (x, y + 1))))
    for tile in (marked, (marked[0] + 1, marked[1]), (marked[0], marked[1] + 1)):
        world.build("arrow", tile)
    from hellward.sim.model import curse_radius
    from hellward.sim.content import Curse, MONSTERS
    assert len(world.caught(marked, curse_radius(Curse.WEAKEN, MONSTERS["shaman"], 1.0))) == 3
    assert [t.tile for t in world.caught(marked, curse_radius(Curse.WEAKEN, MONSTERS["shaman"], world.curse_scale))] == [marked]


def test_the_margin_tool_scales_the_locations_own_life_factor(monkeypatch):
    import margin
    seen = []
    monkeypatch.setattr(margin, "defend", lambda location, player, **kw: (seen.append(location.life), (type("W", (), {"outcome": "victory"})(), None))[1])
    assert margin.wins("apprentice", "graveyard", 1000, 3, "smart", 1.5)
    assert seen == [LOCATIONS["graveyard"].life * 1.5]
