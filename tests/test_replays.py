"""A person's logged defence, and the ghost that replays it.

A defence played through the battle scene writes one replay file; a ghost built from a log of a scripted
Tristram defence wins it the same way; a refused command is retried, then dropped, without an exception.
"""

import json
from pathlib import Path

import pytest
from saga2d import Game

from hellward.__main__ import build
from hellward.sim import planner
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import WAVE_BREAK
from hellward.sim.model import SIM_DT, Refused, World
from hellward.sim.players.ghost import Ghost
from hellward.sim.players.hands import Hands, defend, react_for
from hellward.sim.skills import perks
from hellward.ui.battle import HEIGHT, WIDTH, BattleScene
from hellward.ui.hud import BUILD, SLOT, SLOT_X, TOP
from hellward.ui.view import MAP_X, MAP_Y, T


@pytest.fixture(scope="module")
def cache(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("cache")


@pytest.fixture
def game(cache, tmp_path):
    g = Game("Hellward", backend="mock", resolution=(WIDTH, HEIGHT), asset_path=cache, save_dir=tmp_path / "saves")
    yield g, build(g, cache), tmp_path
    g.close()


def slot_centre(key: str) -> tuple[int, int]:
    i = BUILD.index(key)
    return SLOT_X + i * (SLOT + 10) + SLOT // 2, TOP + 16 + SLOT // 2


def tile_centre(x: int, y: int) -> tuple[int, int]:
    return int(MAP_X + (x + 0.5) * T), int(MAP_Y + (y + 0.5) * T)


def test_a_persons_defence_is_logged_to_a_replay_file(game):
    g, art, tmp_path = game
    scene = BattleScene(art, LOCATIONS["tristram"], perks=perks({"adept_fire"}), learned={"adept_fire"},
                        seed=1, planner=planner.smart)
    g.push(scene)
    g.tick(SIM_DT)
    g.backend.inject_click(*slot_centre("pyre"))
    g.tick(SIM_DT)
    g.backend.inject_click(*tile_centre(7, 5))
    g.tick(SIM_DT)
    g.backend.inject_click(*slot_centre("frost"))
    g.tick(SIM_DT)
    g.backend.inject_click(*tile_centre(8, 6))
    g.tick(SIM_DT)
    assert scene.world.tower_at((7, 5)) is not None and scene.world.tower_at((8, 6)) is not None
    path_tile = scene.world.level.path_tiles[5]   # refused: towers stand on the bare floor
    g.backend.inject_click(*slot_centre("pyre"))
    g.tick(SIM_DT)
    g.backend.inject_click(*tile_centre(*path_tile))
    g.tick(SIM_DT)
    scene.speed = 10.0
    for _ in range(3000):
        if scene.world.can_call_wave:
            scene.call_wave()
        g.tick(0.1)
        if scene.world.outcome is not None:
            break
    assert scene.world.outcome is not None
    for _ in range(3):   # the outcome is kept the moment it is known, whatever ticks follow
        g.tick(0.1)
    files = sorted((tmp_path / "replays").glob("*-tristram.json"))
    assert len(files) == 1
    log = json.loads(files[0].read_text())
    assert log["version"] == 1
    assert log["location"] == "tristram" and log["seed"] == 1 and log["skills"] == ["adept_fire"]
    assert log["outcome"] == scene.world.outcome and log["lives"] == scene.world.lives
    assert log["time"] == scene.world.time
    builds = [c for c in log["commands"] if c[1] == "build"]
    assert [c[2] for c in builds] == ["pyre", "frost"]
    assert [tuple(c[3]) for c in builds] == [(7, 5), (8, 6)]
    assert not [c for c in builds if tuple(c[3]) == tuple(path_tile)]   # refused commands are not recorded
    assert any(c[1] == "call_wave" for c in log["commands"])
    assert [c[0] for c in log["commands"]] == sorted(c[0] for c in log["commands"])


TILES = [(7, 6), (11, 8), (15, 8), (19, 7), (11, 9), (15, 9), (16, 8), (18, 7),
         (19, 6), (7, 5), (8, 6), (10, 8), (16, 9), (18, 6)]


class Recorder:
    """A simple Tristram defence, logged as it plays: a Pyre and a Frost Shrine early, then more of
    both as the gold comes in, ranks with what is left, and the next wave whenever the break allows."""

    name = "recorder"

    def __init__(self) -> None:
        self.commands: list = []

    def skills(self, location, sigils):
        return frozenset()

    def act(self, hands):
        world = hands.world
        for i, tile in enumerate(TILES):
            kind = "pyre" if i % 2 == 0 else "frost"
            if world.tower_at(tile) is None:
                if world.gold >= world.cost(kind):
                    try:
                        world.build(kind, tile)
                    except Refused:
                        pass
                    else:
                        self.commands.append([world.time, "build", kind, list(tile)])
                break
        else:
            for tower in sorted(world.towers.values(), key=lambda t: t.id):
                price = world.upgrade_cost(tower)
                if price is not None and world.gold >= price:
                    try:
                        world.upgrade(tower.id)
                    except Refused:
                        pass
                    else:
                        self.commands.append([world.time, "upgrade", list(tower.tile)])
                    break
        if world.can_call_wave and world.break_left is not None and world.break_left < WAVE_BREAK - 2:
            world.call_wave()
            self.commands.append([world.time, "call_wave"])


def test_a_ghost_replays_a_logged_tristram_defence_the_same_way():
    recorder = Recorder()
    original, _ = defend(LOCATIONS["tristram"], recorder, seed=1, sigils=0, planner=planner.smart)
    assert original.outcome == "victory"
    log = {"version": 1, "location": "tristram", "seed": 1, "skills": [],
           "outcome": original.outcome, "lives": original.lives, "time": original.time,
           "commands": recorder.commands}
    replayed, _ = defend(LOCATIONS["tristram"], Ghost(log), seed=1, sigils=0, planner=planner.smart, hp=1.0)
    assert replayed.outcome == original.outcome == "victory"
    assert replayed.lives == original.lives and replayed.time == original.time


def test_a_refused_command_is_retried_then_dropped_without_an_error():
    path_tile = list(LOCATIONS["tristram"].level.path_tiles[5])
    log = {"version": 1, "location": "tristram", "seed": 1, "skills": ["adept_fire"], "outcome": "victory",
           "lives": 20, "time": 12.0,
           "commands": [[0.0, "build", "pyre", path_tile],   # nowhere to stand: refused for ten seconds, then let go
                        [11.0, "build", "pyre", [7, 5]],
                        [12.0, "upgrade", [7, 5]]]}
    world = World(LOCATIONS["tristram"], perks=perks({"adept_fire"}), seed=1)
    hands = Hands(world, react_for(1))
    ghost = Ghost(log)
    while world.time < 30.0:
        ghost.act(hands)
        world.step(SIM_DT)
        hands.observe(world.events)
        world.events.clear()
    tower = world.tower_at((7, 5))
    assert tower is not None and tower.level == 1   # the dropped command held nothing back


def test_a_ghost_learns_its_logs_skills_or_says_they_cost_too_much():
    log = {"version": 1, "location": "tristram", "seed": 1, "skills": ["adept_fire", "fire_ball"],
           "outcome": "victory", "lives": 20, "time": 0.0, "commands": []}
    ghost = Ghost(log)
    assert ghost.skills(LOCATIONS["tristram"], 3) == frozenset({"adept_fire", "fire_ball"})
    with pytest.raises(ValueError):
        ghost.skills(LOCATIONS["tristram"], 0)
