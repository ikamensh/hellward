"""The campaign through the real server: what the 2D game's screens did, now as the server's answers.

Each test starts ``python -m hellward.server`` on a scratch save folder (some first write a campaign into it, as a
player's earlier sessions would have) and talks to it as the Godot client does. Defences are fought by the real
rules: a scripted player wins one for the campaign, an empty field loses one.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from hellward.server.client import Client, Refused
from hellward.server.progress import Progress
from hellward.server.saves import Saves
from hellward.sim.campaign import ACTS, LOCATIONS
from hellward.sim.skills import SKILLS


def campaign(data: Path, **state) -> None:
    """Write a campaign into a save folder, as earlier sessions left it."""
    p = Progress(saves=Saves(data / "saves"))
    for name, value in state.items():
        setattr(p, name, value)
    p.save()


def fight(client: Client) -> dict:
    """Play the battle on to its end; its last frame."""
    while True:
        frames = client.advance(400)
        if frames[-1]["state"]["outcome"] is not None:
            return frames[-1]


def lose(client: Client) -> dict:
    """Call every wave onto an empty field."""
    while True:
        last = client.advance(100)[-1]
        if last["state"]["outcome"] is not None:
            return last
        if last["state"]["can_call"]:
            client.order("call_wave")


def lane_side(grid: list[str], count: int) -> list[list[int]]:
    """Bare floor beside the monsters' halls, from the middle out: where an arrow tower reaches them."""
    tiles = [[x, y] for y, row in enumerate(grid) for x, c in enumerate(row) if c == "."
             and any(0 <= y + dy < len(grid) and 0 <= x + dx < len(row) and grid[y + dy][x + dx] == "P"
                     for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    middle = len(grid[0]) / 2
    return sorted(tiles, key=lambda t: abs(t[0] - middle))[:count]


@pytest.fixture
def data(tmp_path: Path) -> Path:
    return tmp_path / "data"


def test_a_new_campaign_owes_the_prologue_and_opens_only_tristram(data):
    with Client(data) as c:
        view = c.request("campaign")
        assert view["prologue"] and view["sigils"] == 0 and view["due"] is None
        act1 = view["acts"][0]
        assert [p["key"] for p in act1["places"]] == list(ACTS[1])
        assert [p["key"] for p in act1["places"] if p["opened"]] == ["tristram"]
        assert [p["key"] for p in act1["places"] if p["next"]] == ["tristram"]
        assert not view["acts"][1]["open"]
        c.request("seen", key="prologue")
        assert not c.request("campaign")["prologue"]
        brief = c.request("briefing", location="tristram")
        assert [m["kind"] for m in brief["host"]] == list(LOCATIONS["tristram"].monsters)
        assert brief["story"]["key"] == "tristram/before", "the first arrival tells the before page"
        c.request("seen", key="tristram/before")
        again = c.request("briefing", location="tristram")
        assert again["story"] is None and again["before"]["key"] == "tristram/before"


def test_profiles_are_created_switched_and_never_mixed(data):
    with Client(data) as c:
        assert c.request("profiles") == {"profiles": ["main"], "current": "main"}
        c.request("seen", key="prologue")
        assert c.request("create_profile", name="Playtest") == {"profiles": ["main", "playtest"], "current": "playtest"}
        assert c.request("campaign")["prologue"], "a new profile starts fresh"
        for name, why in (("MAIN", "exists"), ("9lives", "Start with a letter"), ("x" * 30, "at most 24")):
            with pytest.raises(Refused, match=why):
                c.request("create_profile", name=name)
        c.request("switch_profile", name="main")
        assert not c.request("campaign")["prologue"]
    with Client(data) as c:
        assert c.request("profiles")["profiles"] == ["main", "playtest"]


def test_a_won_defence_earns_sigils_opens_the_way_tells_its_after_page_once_and_lasts(data):
    with Client(data, seed=3) as c:
        start = c.request("defend", location="tristram", player="ordinary")
        assert start["scripted"] and not start["demo"]
        result = fight(c)["result"]
        assert result["won"] and result["title"] == "The Sanctuary Holds"
        assert result["earned"] == result["gained"] >= 1
        assert ["holy", "The way down to the Graveyard is open."] in result["extra"]
        way = c.request("leave", again=False)
        assert way["story"]["key"] == "tristram/after" and way["then"] == "map"
        view = c.request("campaign")
        assert [p["key"] for p in view["acts"][0]["places"] if p["opened"]] == ["tristram", "graveyard"]
        c.request("defend", location="tristram", player="ordinary")
        assert fight(c)["result"]["gained"] == 0
        assert c.request("leave", again=True) == {"story": None, "then": "intro", "location": "tristram"}
    with Client(data) as c:
        assert c.request("campaign")["sigils"] == result["earned"]


def test_a_won_defence_is_kept_when_the_player_leaves_before_the_reckoning(data):
    with Client(data, seed=3) as c:
        c.request("defend", location="tristram", player="ordinary")
        fight(c)
        c.request("abandon")
        assert c.request("campaign")["sigils"] >= 1


def test_a_fall_earns_nothing_writes_its_replay_and_again_returns_to_the_intro(data):
    with Client(data) as c:
        c.request("defend", location="tristram")
        last = lose(c)
        assert last["state"]["outcome"] == "defeat"
        assert last["result"]["gained"] == 0 and last["result"]["title"] == "The Sanctuary Has Fallen"
        assert c.request("leave", again=True) == {"story": None, "then": "intro", "location": "tristram"}
        assert c.request("campaign")["sigils"] == 0
    replays = list((data / "replays").glob("*-tristram.json"))
    assert len(replays) == 1 and json.loads(replays[0].read_text())["outcome"] == "defeat"


def test_what_a_location_does_not_offer_or_has_not_reached_is_refused_with_why(data):
    with Client(data) as c:
        with pytest.raises(Refused, match="The way to the Cathedral is not open yet"):
            c.request("defend", location="cathedral")
        c.request("defend", location="tristram")
        with pytest.raises(Refused, match="Not in Tristram: it arrives in the Cathedral"):
            c.order("build", kind="pyre", tile=lane_side(c.request("defend", location="tristram")["grid"], 1)[0])
        with pytest.raises(Refused, match="Battle Hymn is not yet yours: you learn it for the Graveyard"):
            c.order("hymn", tower=0)


def test_the_tree_learns_what_free_sigils_pay_for_says_why_not_and_unlearns_for_free(data):
    campaign(data, won={"tristram": 3})
    with Client(data) as c:
        tree = c.request("skills")
        assert tree["sigils"] == 3 and tree["free"] == 3 and not tree["any"]
        with pytest.raises(Refused, match="needs Adept of Steel first"):
            c.request("learn", key="master_arrow")
        tree = c.request("learn", key="adept_arrow")
        assert tree["free"] == 3 - SKILLS["adept_arrow"].cost and tree["any"]
        with pytest.raises(Refused, match="costs .* sigils"):
            c.request("learn", key="master_arrow")
        with pytest.raises(Refused, match="opens in"):
            c.request("learn", key="fire_ball")
        start = c.request("defend", location="tristram")
        assert start["skills"] == ["adept_arrow"], "the learned skills go into the defence"
        assert c.request("unlearn_all")["free"] == 3


def test_a_skill_learned_later_is_dormant_at_an_earlier_location_and_counted_as_waste(data):
    campaign(data, won={key: 3 for key in ACTS[1]} | {"docks": 3, "spider_forest": 3, "jungle": 3},
             learned=frozenset({"adept_fire", "master_fire", "fire_ball"}))
    with Client(data) as c:
        nodes = {n["key"]: n for n in c.request("skills", location="tristram")["nodes"]}
        assert nodes["fire_ball"]["dormant"] and "Inactive in Tristram" in nodes["fire_ball"]["tip"]
        assert nodes["adept_fire"]["dormant"] and "Nothing to work on here" in nodes["adept_fire"]["tip"]
        assert not {n["key"]: n for n in c.request("skills")["nodes"]}["fire_ball"]["dormant"]
        waste = c.request("briefing", location="tristram")["waste"]
        assert waste is not None and "sigils sit in skills that do nothing here" in waste


def test_hymn_quickens_the_tower_it_is_cast_on_and_no_spell_is_cast_while_paused(data):
    campaign(data, won={"tristram": 3})
    with Client(data) as c:
        start = c.request("defend", location="graveyard")
        assert {"smite", "hymn"} <= set(start["arsenal"]["spells"]) and "cleanse" not in start["spells"]
        tile = lane_side(start["grid"], 1)[0]
        tower = c.order("build", kind="arrow", tile=tile)[-1]["towers"][0]
        with pytest.raises(Refused, match="That tower is gone"):
            c.order("hymn", tower=tower[0] + 1)
        last = c.advance(1)[-1]
        while last["state"]["mana"] < last["state"]["spell_cost"]["hymn"]:
            last = c.advance(20)[-1]
        frame = c.order("hymn", tower=tower[0])[-1]
        assert ["hymn", tower[0]] in frame["events"]
        assert frame["state"]["mana"] == pytest.approx(last["state"]["mana"] - last["state"]["spell_cost"]["hymn"])
        assert frame["towers"][0][4] == start["spells"]["hymn"]["lasting"] > 0, "the tower carries Hymn's seconds"
        assert 0 < c.advance(20)[-1]["towers"][0][4] < frame["towers"][0][4]
        c.order("pause", paused=True)
        with pytest.raises(Refused, match="resume it first"):
            c.order("smite", monster=0)


def test_a_breach_is_offered_chosen_and_a_forfeited_trophy_stays_forfeited(data):
    campaign(data, won={"tristram": 3})
    with Client(data) as c:
        start = c.request("defend", location="graveyard")
        assert start["breach"]["name"] == "The Ash Crypt" and start["breach"]["claimed"] is None
        for tile in lane_side(start["grid"], 8):
            try:
                c.order("build", kind="arrow", tile=tile)
            except Refused:
                break
        while True:
            last = c.advance(20)[-1]
            assert last["state"]["outcome"] is None, "the defence lasted until the breach was offered"
            if last["state"]["breach"]["offered"]:
                break
            if last["state"]["can_call"] and last["state"]["wave"] < start["breach"]["after_wave"]:
                c.order("call_wave")
        events = [e for f in c.order("breach", mode="cash") for e in f["events"]]
        assert events == [["breach_choice", "cash"]]
        assert c.advance(1)[-1]["state"]["breach"]["mode"] == "cash"
    campaign(data / "forfeited", won={"tristram": 3}, breach_claims={"graveyard": "cash"})
    with Client(data / "forfeited") as c:
        assert c.request("defend", location="graveyard")["breach"]["claimed"] == "cash"


def test_act_one_held_owes_its_ending_once_and_opens_act_two(data):
    campaign(data, won={key: 2 for key in ACTS[1]}, seen=frozenset({"prologue"}))
    with Client(data) as c:
        view = c.request("campaign")
        assert view["due"]["key"] == "act1/end" and view["acts"][1]["open"]
        c.request("seen", key="act1/end")
        assert c.request("campaign")["due"] is None, "a finished act's after pages wait in the Chronicle"
        chronicle = [s["key"] for s in c.request("chronicle")["stories"]]
        assert "act1/end" in chronicle and "tristram/after" in chronicle and "docks/before" in chronicle


def test_the_forge_forges_equips_and_unequips_and_says_what_it_lacks(data):
    campaign(data, won={"tristram": 3, "graveyard": 3}, salvage=5)
    with Client(data) as c:
        cards = {card["key"]: card for card in c.request("forge_view")["cards"]}
        assert cards["honed_string"]["label"] == "Forge and equip" and cards["honed_string"]["enabled"]
        assert cards["laminated_limbs"]["label"] == "Need more drops"
        view = c.request("forge", key="honed_string")
        card = {card["key"]: card for card in view["cards"]}["honed_string"]
        assert card["owned"] and card["equipped"] and view["salvage"] == 2
        card = {card["key"]: card for card in c.request("forge", key="honed_string")["cards"]}["honed_string"]
        assert card["owned"] and not card["equipped"]
        with pytest.raises(Refused, match="needs"):
            c.request("forge", key="laminated_limbs")


@pytest.mark.skipif(os.name == "nt", reason="pgrep and SIGKILL")
def test_the_planners_workers_end_with_the_server_however_it_ends(data):
    c = Client(data)
    c.request("defend", location="tristram")
    workers = subprocess.run(["pgrep", "-P", str(c.process.pid)], capture_output=True, text=True).stdout.split()
    assert workers, "the server keeps worker processes for the leaders"
    os.kill(c.process.pid, signal.SIGKILL)
    c.process.wait()
    for _ in range(100):
        alive = [pid for pid in workers if subprocess.run(["kill", "-0", pid], capture_output=True).returncode == 0]
        if not alive:
            break
        time.sleep(0.05)
    assert not alive, "the workers end with their server"
