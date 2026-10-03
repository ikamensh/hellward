"""The grind's skip: a surely clean wave is offered, skipped for a bonus, and resumes exactly."""

import pytest

from hellward.run import kit, start
from hellward.server.battle import Battle
from hellward.sim.balance import BALANCE
from hellward.sim.campaign import LOCATIONS
from hellward.sim.level import Tile
from hellward.sim.model import Refused, World


def laneside(world: World) -> list[tuple[int, int]]:
    out = []
    for y in range(world.level.height):
        for x in range(world.level.width):
            if not world.buildable(x, y):
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < world.level.width and 0 <= yy < world.level.height \
                        and world.level.tile(xx, yy) is Tile.PATH:
                    out.append((x, y))
                    break
    return out


def saturated(key: str = "tristram", seed: int = 5) -> World:
    world = World(LOCATIONS[key], seed=seed)
    world.gold = 1000000
    for tile in laneside(world):
        world.build("arrow", tile)
    return world


def fought(world: World) -> World:
    """The first wave called and fully spawned: the grind at its grindiest."""
    world.call_wave()
    while world.schedule:
        world.step()
    return world


def test_a_saturated_wave_is_surely_clean_and_a_naked_one_is_not():
    assert fought(saturated()).predict_clean()
    bare = World(LOCATIONS["tristram"], seed=5)
    assert not fought(bare).predict_clean()


def test_no_offer_on_a_break_while_spawning_or_after_the_fight():
    world = saturated()
    assert not world.predict_clean()   # the break before the first wave
    world.call_wave()
    assert not world.predict_clean() or not world.schedule   # while spawning, unless instant
    while world.schedule or world.monsters:
        world.step()
    assert not world.predict_clean()   # the wave is fought: nothing to skip


def test_the_skip_pays_a_bonus_and_names_the_wave():
    world = fought(saturated())
    gold, lives = world.gold, world.lives
    bonus = world.skip_grind()
    assert bonus == BALANCE.income_unit()
    assert world.gold >= gold + bonus   # the bonus, and the skipped kills' bounties
    assert world.lives == lives
    assert ("skipped", 0, bonus) in world.events
    assert world.break_left is not None   # the wave cleared on the way


def test_the_skip_refuses_a_wave_that_leaks():
    world = fought(World(LOCATIONS["tristram"], seed=5))
    with pytest.raises(Refused, match="not clean"):
        world.skip_grind()


def battle() -> Battle:
    run = start(11)
    return Battle(LOCATIONS["tristram"], planner=None, kit=kit(run))


def offer_of(battle: Battle) -> dict | None:
    battle.world.gold = 1000000
    for tile in laneside(battle.world):
        battle.order("build", {"kind": "arrow", "tile": list(tile)})
    battle.order("call_wave", {})
    frames = []
    while battle.world.schedule:
        frames = battle.advance(20)
    return frames[-1]["state"]["skip_offer"]


def test_the_battle_offers_the_skip_in_its_frames_and_takes_the_order():
    view = battle()
    offer = offer_of(view)
    assert offer == {"wave": 0, "bonus": BALANCE.income_unit()}
    lives = view.world.lives
    why, frame = view.order("skip_grind", {})
    assert why is None and frame is not None
    assert view.world.lives == lives
    assert view.world.break_left is not None
    assert frame["state"]["skip_offer"] is None   # the wave is fought: the offer is gone
    assert any(e[0] == "skipped" for e in frame["events"])


def test_selling_the_defence_takes_the_offer_away():
    view = battle()
    assert offer_of(view) is not None
    for tower in list(view.world.towers.values()):
        view.order("sell", {"tower": tower.id})
    frames = view.advance(1)
    assert frames[-1]["state"]["skip_offer"] is None
    why, _ = view.order("skip_grind", {})
    assert why is not None and "surely clean" in why


def test_a_skip_resumes_from_its_save_exactly():
    view = battle()
    assert offer_of(view) is not None
    view.order("skip_grind", {})
    log = {"commands": [list(e) for e in view.commands], "decisions": {},
           "marks": [round(view.world.time, 3)]}
    twin = battle()
    twin.world.gold = 1000000   # the purse the live defence built from
    twin.resume_from(log, None)
    assert (twin.world.gold, twin.world.lives, twin.world.wave) == \
        (view.world.gold, view.world.lives, view.world.wave)
    assert abs(twin.world.time - view.world.time) < 0.06
