"""A person's logged defence, and the ghost that replays it.

A ghost built from a log of a scripted Tristram defence wins it the same way; a refused command is retried, then
dropped, without an exception. (The server writing a person's log: tests/test_server.py.)
"""

import json
from pathlib import Path

import pytest

from hellward.sim import planner
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import WAVE_BREAK
from hellward.sim.model import SIM_DT, Refused, World
from hellward.sim.players.ghost import Ghost
from hellward.sim.players.hands import Hands, defend, react_for, reference_kit
from hellward.sim.skills import perks


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
            kind = "arrow"
            if world.tower_at(tile) is None:
                if world.gold >= world.cost(kind):
                    try:
                        world.build(kind, tile)
                    except Refused:
                        pass
                    else:
                        self.commands.append([world.time, "build", kind, list(tile)])
                break
        if world.can_call_wave and world.break_left is not None and world.break_left < WAVE_BREAK - 2:
            world.call_wave()
            self.commands.append([world.time, "call_wave"])


def test_a_ghost_replays_a_logged_tristram_defence_the_same_way():
    recorder = Recorder()
    original, _ = defend(reference_kit(LOCATIONS["tristram"], recorder.draft(LOCATIONS["tristram"], 0), 1),
                         recorder, planner=planner.smart)
    log = {"version": 2, "location": "tristram", "seed": 1, "skills": [], "loadout": [],
           "outcome": original.outcome, "lives": original.lives, "time": original.time,
           "commands": recorder.commands}
    ghost = Ghost(log)
    replayed, _ = defend(reference_kit(LOCATIONS["tristram"], ghost.draft(LOCATIONS["tristram"], 0), 1,
                                       loadout=ghost.loadout),
                         ghost, planner=planner.smart, hardness=1.0)
    assert replayed.outcome == original.outcome
    assert replayed.lives == original.lives and replayed.time == original.time


def test_a_refused_command_is_retried_then_dropped_without_an_error():
    level = LOCATIONS["tristram"].level
    path_tile = list(level.path_tiles[5])
    tile = next((x, y) for y in range(level.height) for x in range(level.width) if level.buildable(x, y))
    log = {"version": 2, "location": "tristram", "seed": 1, "skills": [], "loadout": [], "outcome": "victory",
           "lives": 20, "time": 12.0,
           "commands": [[0.0, "build", "arrow", path_tile],   # nowhere to stand: refused for ten seconds, then let go
                        [11.0, "build", "arrow", list(tile)]]}
    world = World(LOCATIONS["tristram"], seed=1)
    hands = Hands(world, react_for(1))
    ghost = Ghost(log)
    while world.time < 30.0:
        ghost.act(hands)
        world.step(SIM_DT)
        hands.observe(world.events)
        world.events.clear()
    tower = world.tower_at(tile)
    assert tower is not None and tower.level == 0   # the dropped command held nothing back


def test_a_ghost_learns_its_logs_skills_or_says_they_cost_too_much():
    log = {"version": 2, "location": "tristram", "seed": 1, "skills": ["adept_arrow"], "loadout": [],
           "outcome": "victory", "lives": 20, "time": 0.0, "commands": []}
    ghost = Ghost(log)
    assert ghost.draft(LOCATIONS["tristram"], 3) == frozenset({"adept_arrow"})
    with pytest.raises(ValueError):
        ghost.draft(LOCATIONS["tristram"], 0)
