"""Attunement: towers hold charges for empowered shots, spent where they kill."""

from dataclasses import replace

import pytest

from hellward.server.battle import Battle
from hellward.server.campaign import Campaign, Refusal
from hellward.sim import campaign, planner
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import SPELLS, TOWERS, Group, Wave
from hellward.sim.level import Level
from hellward.sim.model import ATTUNE_GOLD, CHARGES_MAX, CHARGE_EVERY, EMPOWER, Refused, World
from hellward.sim.modes import ATTUNE
from hellward.sim.players.adaptive import Adaptive
from hellward.sim.players.ghost import issue
from hellward.sim.players.hands import Hands, attune_spare
from hellward.sim.players.ordinary import Ordinary

ARENA = Level("Charge field", 25, 14,
              ((0, 2), (9, 2), (9, 8), (19, 8), (19, 11), (24, 11)), ((9, 5),))


def arena() -> World:
    waves = (Wave((Group("skeleton", 1, 0.1),), 10),)
    arsenal = replace(campaign.CATHEDRAL.arsenal, towers=tuple(TOWERS), spells=tuple(SPELLS), gates=True)
    location = replace(campaign.CATHEDRAL, level=ARENA, arsenal=arsenal, waves=waves, wave_names=("pack",))
    world = World(location, seed=7)
    world.gold = 10000
    return world


def floor(world: World) -> tuple[int, int]:
    return next((x, y) for y in range(14) for x in range(25) if world.buildable(x, y))


def tiles(world: World):
    """Fresh buildable tiles, one after another, never a taken one."""
    used = {t.tile for t in world.towers.values()}
    for y in range(14):
        for x in range(25):
            if (x, y) not in used and world.buildable(x, y):
                used.add((x, y))
                yield (x, y)


def test_attuning_costs_gold_starts_full_and_refuses_twice():
    world = arena()
    tower = world.build("arrow", floor(world))
    assert not tower.attuned
    world.gold = ATTUNE_GOLD
    world.attune(tower.id)
    assert (tower.attuned, tower.charges, world.gold) == (True, CHARGES_MAX, 0)
    assert ("attuned", tower.id) in world.events
    assert world.clone().towers[tower.id].attuned
    with pytest.raises(Refused, match="already attuned"):
        world.attune(tower.id)
    world.gold = 10000
    second = world.build("arrow", next(t for t in [(x, y) for y in range(14) for x in range(25)]
                                       if world.buildable(*t) and t != tower.tile))
    world.gold = 0
    with pytest.raises(Refused, match="costs"):
        world.attune(second.id)


def test_charges_regrow_one_per_fifteen_seconds():
    world = arena()
    tower = world.build("arrow", floor(world))
    world.attune(tower.id)
    tower.charges = 0.0
    for _ in range(int(CHARGE_EVERY / 0.05)):
        world.step(0.05)
    assert tower.charges == pytest.approx(1.0)
    for _ in range(int(10 * CHARGE_EVERY / 0.05)):
        world.step(0.05)
    assert tower.charges == CHARGES_MAX   # never past full


def aimed(world: World, tower_id: int, hp: float) -> tuple[float, list]:
    """One attuned arrow's shot at a lone skeleton walking its full reach: the bolt's damage and events."""
    tower = world.towers[tower_id]
    spans = world.level.coverage(tower.tile, tower.stats.range)
    lo, hi = max(spans, key=lambda span: span[1] - span[0])
    monster = world.monsters[0]
    monster.s = lo
    monster.hp = hp
    tower.cooldown = 0.0
    tower.charges = CHARGES_MAX   # whatever the spawning's shots spent, the test starts full
    world.events.clear()
    world.step()
    bolts = [e for e in world.events if e[0] == "bolt"]
    assert len(bolts) == 1
    return bolts[0][1].damage, list(world.events)


def test_the_charge_goes_where_it_kills_and_nowhere_else():
    world = arena()
    tower = world.build("arrow", floor(world))
    world.attune(tower.id)
    world.call_wave()
    while not world.monsters:
        world.step()
    spans = world.level.coverage(tower.tile, tower.stats.range)
    lo, hi = max(spans, key=lambda span: span[1] - span[0])
    m = world.monsters[0]
    shots = (hi - lo) / m.speed * tower.stats.rate + 1.0
    dmg = tower.stats.damage
    assert dmg * shots > dmg   # the field gives the volley room to matter

    twin = world.clone()
    twin.record = True
    damage, events = aimed(twin, tower.id, dmg * shots + 1.0)
    assert damage == dmg * EMPOWER   # escapes normal fire, dies empowered: spent
    assert twin.towers[tower.id].charges == CHARGES_MAX - 1.0
    assert any(e[0] == "spent" for e in events)

    twin = world.clone()
    twin.record = True
    damage, _ = aimed(twin, tower.id, dmg * shots - 1.0)
    assert damage == dmg   # dies under normal fire anyway: kept
    assert twin.towers[tower.id].charges == CHARGES_MAX

    twin = world.clone()
    twin.record = True
    damage, _ = aimed(twin, tower.id, dmg)
    assert damage == dmg   # the normal shot kills: kept

    twin = world.clone()
    twin.record = True
    damage, _ = aimed(twin, tower.id, 500.0)
    assert damage == dmg   # hopeless even empowered: kept


def test_attunement_is_taught_in_the_forge_and_attunes_per_tower(tmp_path):
    camp = Campaign(tmp_path / "data", planner=planner.smart, demo_player=Adaptive, seed=3)
    assert camp.forge_view()["strategies"][-1]["key"] == "attune"
    with pytest.raises(Refusal, match="salvage"):
        camp.forge("attune")
    camp.progress.salvage = 10
    camp.forge("attune")
    assert camp.progress.attune
    assert camp.progress.salvage == 10 - ATTUNE.salvage_cost
    battle = Battle(LOCATIONS["tristram"], planner=None, attune_unlocked=camp.progress.attune)
    assert battle.start()["attune"] == {"unlocked": True, "gold": ATTUNE_GOLD}
    battle.world.gold = 10000
    tile = next((x, y) for y in range(20) for x in range(30) if battle.world.buildable(x, y))
    battle.order("build", {"kind": "arrow", "tile": list(tile)})
    tower = battle.world.tower_at(tile).id
    why, frame = battle.order("attune", {"tower": tower})
    assert why is None and frame is not None
    assert battle.world.towers[tower].attuned
    assert battle.commands[-1][1:] == ["attune", [tile[0], tile[1]]]
    bare = Battle(LOCATIONS["tristram"], planner=None)
    assert bare.start()["attune"] == {"unlocked": False, "gold": ATTUNE_GOLD}
    bare.world.gold = 10000
    tile = next((x, y) for y in range(20) for x in range(30) if bare.world.buildable(x, y))
    bare.order("build", {"kind": "arrow", "tile": list(tile)})
    why, _ = bare.order("attune", {"tower": bare.world.tower_at(tile).id})
    assert why is not None and "not taught" in why


def test_an_attunement_replays():
    world = arena()
    tile = floor(world)
    world.build("arrow", tile)
    hands = Hands(world, 0.0)
    assert issue(world, hands, "attune", (list(tile),))
    assert world.tower_at(tile).attuned
    assert not issue(world, hands, "attune", ([0, 0],))


def test_attunement_is_for_shots_that_spend_charges():
    world = arena()
    fresh = tiles(world)
    for kind in ("arrow", "ballista", "knife", "pyre", "storm", "frost", "plague"):
        tower = world.build(kind, next(fresh))
        world.attune(tower.id)
        assert tower.attuned
    for kind in ("hook", "altar", "grove", "idol", "censer", "well", "effigy"):
        tower = world.build(kind, next(fresh))
        gold = world.gold
        with pytest.raises(Refused, match="never spends charges"):
            world.attune(tower.id)
        assert (tower.attuned, world.gold) == (False, gold)


def test_spare_gold_attunes_the_highest_ranked_striker():
    from hellward.sim.skills import NO_PERKS
    world = arena()
    world.perks = replace(NO_PERKS, ranks=(("arrow", 1),))
    fresh = tiles(world)
    low = world.build("arrow", next(fresh))
    high = world.build("arrow", next(fresh))
    world.upgrade(high.id)
    hook = world.build("hook", next(fresh))
    grove = world.build("grove", next(fresh))
    world.gold = ATTUNE_GOLD
    assert attune_spare(world)
    assert (high.attuned, low.attuned, hook.attuned, grove.attuned) == (True, False, False, False)
    world.gold = ATTUNE_GOLD
    assert attune_spare(world)
    assert low.attuned
    world.gold = ATTUNE_GOLD
    assert not attune_spare(world)   # the hook drags and the grove sings: nothing left spends
    third = world.build("arrow", next(fresh))
    world.gold = ATTUNE_GOLD
    assert not attune_spare(world, reserve=ATTUNE_GOLD)   # the reserve is kept, not attuned
    assert not third.attuned
    world.gold = ATTUNE_GOLD - 1
    assert not attune_spare(world)


def test_a_defender_with_nothing_to_buy_attunes_its_striker():
    world = arena()
    tower = world.build("arrow", next(tiles(world)))
    world.gold = ATTUNE_GOLD
    Ordinary()._spend(world)   # no plan, no buyable rank: the spare gold attunes
    assert tower.attuned


def test_the_frames_say_whose_shots_spend_charges():
    from hellward.server.protocol import towers
    world = arena()
    fresh = tiles(world)
    arrow = world.build("arrow", next(fresh))
    hook = world.build("hook", next(fresh))
    grove = world.build("grove", next(fresh))
    by_id = {entry[0]: entry for entry in towers(world)}
    assert by_id[arrow.id][10] is True
    assert by_id[hook.id][10] is False
    assert by_id[grove.id][10] is False
