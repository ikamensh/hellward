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
from hellward.server.protocol import event
from hellward.sim import planner
from hellward.sim.campaign import LOCATIONS, ORDER
from hellward.sim.model import World
from hellward.sim.players import PLAYERS
from hellward.sim.players.ghost import Ghost
from hellward.sim.players.hands import defend


def direct(location: str, player, seed: int) -> tuple[World, list]:
    """A defence played in this process, every event as the server would send it."""
    sent: list = []

    def watch(world: World) -> None:
        sent.extend(event(world, e) for e in world.events)

    world, _ = defend(LOCATIONS[location], player, seed=seed, sigils=3 * ORDER.index(location),
                      planner=planner.smart, watch=watch)
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


def test_a_scripted_defence_through_the_server_is_the_same_defence(client):
    start = client.request("demo", location="tristram", player="ordinary")
    assert start["t"] == "battle" and start["location"]["key"] == "tristram" and start["demo"]
    last, sent = through(client)
    world, expected = direct("tristram", PLAYERS["ordinary"](3), seed=3)
    assert last["state"]["outcome"] == world.outcome and last["state"]["lives"] == world.lives
    assert last["time"] == world.time
    assert sent == expected


def test_a_persons_orders_log_a_defence_whose_ghost_fights_the_same_battle(client, tmp_path):
    """Orders through the protocol, a curse cleansed when one lands: the replay the server writes, played by its
    ghost directly and through the server's demo, gives the same events."""
    grid = client.request("defend", location="tristram")["grid"]
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
            if frame["state"]["can_call"] and (frame["state"]["break_left"] or 0) < 25:
                for f in client.order("call_wave"):
                    sent.extend(f["events"])
            cursed = [t for t in frame["towers"] if t[3]]
            if cursed and frame["state"]["mana"] >= frame["state"]["spell_cost"]["cleanse"]:
                for f in client.order("cleanse", tower=cursed[0][0]):
                    sent.extend(f["events"])
    replays = sorted((tmp_path / "data" / "replays").glob("*-tristram.json"))
    assert len(replays) == 1
    log = json.loads(replays[0].read_text())
    assert log["outcome"] == outcome
    assert any(c[1] == "cleanse" for c in log["commands"]), "a curse landed and was cleansed"
    world, replayed = direct("tristram", Ghost(log), seed=log["seed"])
    assert (world.outcome, world.lives, world.time) == (log["outcome"], log["lives"], log["time"])
    assert replayed == sent
    client.request("demo", replay=log)
    _, ghosted = through(client)
    assert ghosted == sent
