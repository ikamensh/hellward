"""Everything one defence starts from, as one Kit; and plans that cannot go stale.

A World built from a Kit replays an order log to the same events as the defence it came from; a Kit
round-trips through JSON, and a location outside the campaign is refused. A clone copies the derived perks
and baked ranks instead of rebuilding them. A stored plan searched on another map, waves or prices is
refused, by the players and by the margin tool.
"""

import json

import pytest

from hellward.sim import planner
from hellward.sim.campaign import LOCATIONS, ORDER
from hellward.sim.content import WAVE_BREAK
from hellward.sim.items import EMPTY_LOADOUT
from hellward.sim.kit import Kit
from hellward.sim.model import SIM_DT, START_LIVES, Refused, World
from hellward.sim.xp import xp_next
from hellward.sim.players import planned, warden
from hellward.sim.players.ghost import Ghost
from hellward.sim.players.hands import Hands, defend, react_for, reference_kit
from tools.margin import wins


class Recorder:
    """A simple opening defence, logged as it plays: a few Arrow Towers and early wave calls."""

    name = "recorder"

    def __init__(self) -> None:
        self.commands: list = []
        self.tiles: list[tuple[int, int]] | None = None

    def draft(self, location, sigils):
        return frozenset()

    def act(self, hands):
        world = hands.world
        if self.tiles is None:
            self.tiles = [(x, y) for y in range(world.level.height) for x in range(world.level.width)
                          if world.level.buildable(x, y)][:3]
        for tile in self.tiles:
            if world.tower_at(tile) is None:
                if world.gold >= world.cost("arrow"):
                    try:
                        world.build("arrow", tile)
                    except Refused:
                        pass
                    else:
                        self.commands.append([world.time, "build", "arrow", list(tile)])
                break
        if world.can_call_wave and world.break_left is not None and world.break_left < WAVE_BREAK - 2:
            world.call_wave()
            self.commands.append([world.time, "call_wave"])


def kinds(world: World) -> list:
    return [e[0] for e in world.events]


def test_a_world_from_a_kit_replays_to_the_same_events():
    recorder = Recorder()
    seen: list = []
    original, _ = defend(reference_kit(LOCATIONS["tristram"], recorder.draft(LOCATIONS["tristram"], 0), 1),
                         recorder, planner=planner.smart, watch=lambda w: seen.extend(kinds(w)))
    log = {"version": 2, "location": "tristram", "seed": 1, "skills": [], "loadout": [],
           "commands": recorder.commands}
    kit = Kit(LOCATIONS["tristram"], frozenset(), EMPTY_LOADOUT, LOCATIONS["tristram"].start_gold,
              START_LIVES, 1)
    world = kit.world(planner=planner.smart)
    ghost, hands = Ghost(log), Hands(world, react_for(1))
    replayed: list = []
    while world.outcome is None and world.time < 3000.0:
        ghost.act(hands)
        world.step(SIM_DT)
        replayed.extend(kinds(world))
        hands.observe(world.events)
        world.events.clear()
    assert world.outcome == original.outcome
    assert (world.lives, world.time) == (original.lives, original.time)
    assert replayed == seen


def test_a_kit_round_trips_through_json_and_refuses_a_foreign_location():
    kit = Kit(LOCATIONS["caves"], frozenset({"adept_arrow"}), EMPTY_LOADOUT, 100, 17, 7)
    again = Kit.from_json(json.loads(json.dumps(kit.to_json())))
    assert again == kit
    assert Kit.from_json({"location": "tristram"}).gold == LOCATIONS["tristram"].start_gold
    with pytest.raises(ValueError):
        Kit.from_json({"location": "mordor"})


def test_a_kit_carries_the_runs_xp_and_reckons_what_is_missing():
    kit = Kit(LOCATIONS["caves"], xp=5.0, level=3)
    assert kit.xp_next == xp_next(3)
    assert Kit.from_json(json.loads(json.dumps(kit.to_json()))) == kit
    bare = Kit.from_json({"location": "tristram"})
    assert (bare.xp, bare.level, bare.xp_next) == (0.0, 1, xp_next(1))
    world = kit.world()
    assert (world.xp, world.xp_level) == (5.0, 3)


def test_a_clone_copies_the_derived_perks_and_baked_ranks():
    world = World(LOCATIONS["tristram"], seed=3)
    clone = world.clone()
    assert clone.perks == world.perks and clone.tower_levels is world.tower_levels


def test_the_kit_deals_the_arsenal_the_world_reads():
    from hellward.sim.campaign import Arsenal
    deal = Arsenal(("arrow",), False, ("smite",))
    world = Kit(LOCATIONS["tristram"], arsenal=deal).world()
    assert world.arsenal == deal
    assert world.clone().arsenal == deal
    assert Kit(LOCATIONS["tristram"]).arsenal == LOCATIONS["tristram"].arsenal


def test_a_plan_searched_on_something_else_is_refused(tmp_path, monkeypatch):
    assert planned.check(LOCATIONS["tristram"]).map == planned.fingerprint(LOCATIONS["tristram"])
    monkeypatch.setattr(planned, "PLANS", tmp_path)
    with pytest.raises(ValueError):
        planned.check(LOCATIONS["tristram"])
    (tmp_path / "tristram.json").write_text(json.dumps({"skills": [], "steps": [], "calls": []}))
    with pytest.raises(ValueError):
        planned.check(LOCATIONS["tristram"])
    with pytest.raises(ValueError):
        wins("planned", "tristram", 1000, 0, "smart", 1.0)


def test_the_margin_tool_refuses_a_stale_warden_plan(tmp_path, monkeypatch):
    location = LOCATIONS["tristram"]
    warden.check(location, 0)   # nothing stored: the draft plays, which is allowed
    row = {"skills": [], "steps": [], "early": {}, "map": "stale"}
    (tmp_path / "warden.json").write_text(json.dumps({f"tristram/0": row}))
    monkeypatch.setattr(warden, "PLANS", tmp_path / "warden.json")
    with pytest.raises(ValueError):
        warden.check(location, 0)
    with pytest.raises(ValueError):
        wins("warden", "tristram", 1000, 0, "smart", 1.0)
