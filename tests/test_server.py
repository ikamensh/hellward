"""The server adds transport, never a different battle.

A defence played through ``python -m hellward.server`` (a real process over a loopback socket, driven by the Python
stand-in client) is held to the same defence played by :func:`hellward.sim.players.hands.defend` directly: event for
event, and the same end. The person's path is held the same way: orders sent through the protocol make a replay log,
and that log's ghost, played directly, fights the identical battle.
"""

from __future__ import annotations

import json

import pytest

from hellward.server.client import Client, Refused
from hellward.server.progress import Progress
from hellward.server.protocol import event
from hellward.server.saves import Saves
from hellward.sim import planner
from hellward.sim.campaign import ACTS, LOCATIONS, ORDER
from hellward.sim.content import MONSTERS, TOWERS, felt_hit
from hellward.sim.model import World
from hellward.sim.players import PLAYERS
from hellward.sim.players.ghost import Ghost
from hellward.sim.players.hands import defend, reference_kit
from hellward.sim.skills import perks


def direct(location: str, player, seed: int) -> tuple[World, list]:
    """A defence played in this process, every event as the server would send it."""
    sent: list = []

    def watch(world: World) -> None:
        sent.extend(event(world, e) for e in world.events)

    loc = LOCATIONS[location]
    world, _ = defend(reference_kit(loc, player.draft(loc, 3 * ORDER.index(location)), seed),
                      player, planner=planner.smart, watch=watch)
    return world, json.loads(json.dumps(sent))


def through(client: Client) -> tuple[dict, list]:
    """Play the client's battle to its end; its last frame and every event it sent."""
    sent: list = []
    while True:
        frames = client.advance(200)
        for frame in frames:
            sent.extend(frame["events"])
        if frames[-1]["state"]["outcome"] is not None:
            return frames[-1], sent


@pytest.fixture
def client(tmp_path):
    with Client(tmp_path / "data", seed=3) as c:
        yield c


def test_spawn_and_built_reach_the_client_as_id_and_facts():
    """The sim's kinds are for the server's folds; the wire keeps [name, id, facts]."""
    world = World(LOCATIONS["tristram"], seed=1)
    world.gold = 1000
    tile = next((x, y) for y in range(world.level.height) for x in range(world.level.width)
                if world.buildable(x, y))
    tower = world.build("arrow", tile)
    built = event(world, ("built", tower.id, "arrow"))
    assert built[0] == "built" and built[1] == tower.id
    assert built[2]["kind"] == "arrow" and built[2]["tile"] == [tile[0], tile[1]]
    world.call_wave()
    while not world.monsters:
        world.step()
    m = world.monsters[0]
    spawned = event(world, ("spawn", m.id, m.kind.key))
    assert spawned[0] == "spawn" and spawned[1] == m.id
    assert spawned[2]["kind"] == m.kind.key


def test_a_scripted_defence_through_the_server_is_the_same_defence(client):
    start = client.request("demo", location="tristram", player="ordinary")
    assert start["t"] == "battle" and start["location"]["key"] == "tristram" and start["demo"]
    last, sent = through(client)
    world, expected = direct("tristram", PLAYERS["ordinary"](3), seed=3)
    assert last["state"]["outcome"] == world.outcome and last["state"]["lives"] == world.lives
    assert last["time"] == world.time
    assert sent == expected


def test_a_persons_orders_log_a_defence_whose_ghost_fights_the_same_battle(tmp_path):
    """Orders through the protocol, Battle Hymn cast on a tower whenever it is ready: the replay the server writes,
    played by its ghost directly and through the server's demo, gives the same events."""
    data = tmp_path / "data"
    Progress(saves=Saves(data / "saves"), won={"tristram": 3}).save()   # the Graveyard, where Hymn is learned, is open
    with Client(data, seed=3) as client:
        client.request("learn", key="unlock_hymn")
        grid = client.request("defend", location="graveyard")["grid"]
        tiles = [[x, y] for y, row in enumerate(grid) for x, c in enumerate(row) if c == "."]
        sent: list = []
        with pytest.raises(Refused, match="bare floor"):
            client.order("build", kind="arrow", tile=[0, 8])
        for tile in (tiles[40], tiles[120], tiles[200]):
            for frame in client.order("build", kind="arrow", tile=tile):
                sent.extend(frame["events"])
        outcome = None
        while outcome is None:
            for frame in client.advance(1):
                sent.extend(frame["events"])
                outcome = frame["state"]["outcome"]
                state = frame["state"]
                if state["can_call"] and (state["break_left"] or 0) < 25:
                    for f in client.order("call_wave"):
                        sent.extend(f["events"])
                if (outcome is None and state["mana"] >= state["spell_cost"]["hymn"]
                        and state["recharge"].get("hymn", 0) <= 0):
                    try:
                        for f in client.order("hymn", tower=frame["towers"][0][0]):
                            sent.extend(f["events"])
                    except Refused:
                        pass   # the shown mana rounds up past the cost: the next frame affords it
        replays = sorted((data / "replays").glob("*-graveyard.json"))
        assert len(replays) == 1
        log = json.loads(replays[0].read_text())
        assert log["outcome"] == outcome
        assert any(c[1] == "hymn" for c in log["commands"]) and any(e[0] == "hymn" for e in sent)
        world, replayed = direct("graveyard", Ghost(log), seed=log["seed"])
        assert (world.outcome, world.lives, world.time) == (log["outcome"], log["lives"], log["time"])
        assert replayed == sent
        client.request("demo", replay=log)
        _, ghosted = through(client)
        assert ghosted == sent


def test_the_battle_start_tells_each_kind_its_armor_its_tags_and_the_hits_it_takes(tmp_path):
    """The hover's table comes from the simulation's own felt hit: one entry per rank of every tower here that strikes
    blows, whole and at least 1. The frames carry each monster's movers' bits last."""
    data = tmp_path / "data"
    Progress(saves=Saves(data / "saves"), won={key: 3 for key in ACTS[1]}).save()
    with Client(data, seed=3) as client:
        for key in ("unlock_hook", "unlock_knife", "unlock_hymn"):
            client.request("learn", key=key)
        start = client.request("defend", location="docks")
        world = World(LOCATIONS["docks"], perks=perks(frozenset(), ORDER.index("docks")), seed=3, planner=None)
        striking = [k for k in start["arsenal"]["towers"] if TOWERS[k].attack not in ("amplify", "aura")]
        assert {"hook", "knife"} <= set(striking)
        for key, table in start["monsters"].items():
            kind = MONSTERS[key]
            assert (table["armor"], table["boss"]) == (kind.armor, kind.boss)
            assert (table["protected"], table["vulnerable"]) == ([e.value for e in kind.protected],
                                                                 [e.value for e in kind.vulnerable])
            assert list(table["hits"]) == striking
            for tower, ranks in table["hits"].items():
                assert ranks == [felt_hit(lv.damage, TOWERS[tower].element, kind) for lv in world.tower_levels[tower]]
                assert all(isinstance(hit, int) and hit >= 1 for hit in ranks)
        assert start["spells"]["hymn"]["aim"] == "tower"
        client.order("call_wave")
        frames = client.advance(200)
        monsters = [m for f in frames for m in f["monsters"]]
        assert monsters and all(len(m) == 9 and isinstance(m[8], int) for m in monsters)
