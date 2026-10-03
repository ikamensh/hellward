"""The run on the server: one run per profile, saved after every camp.

A run starts, camps, learns and unlearns through the wire; the run's state survives a server restart;
the briefing at the run's location names its goals, the worst case against the pool, and the answers
the roster's standout has. Profile mode (no run) is untouched.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from hellward.run import LIFE, start
from hellward.server.campaign import Campaign, Refusal, answers_line, worst_line
from hellward.server.client import Client
from hellward.server.client import Refused as WireRefused
from hellward.sim import planner
from hellward.sim.campaign import LOCATIONS
from hellward.sim.players.adaptive import Adaptive


@pytest.fixture
def client(tmp_path):
    with Client(tmp_path / "data", seed=3) as c:
        yield c


def campaign_at(data, profile="main"):
    return Campaign(data, planner=planner.smart, demo_player=Adaptive, seed=3, profile=profile)


def test_a_run_starts_camps_and_abandons_through_the_wire(client):
    assert client.request("run") == {"active": False}
    view = client.request("start_run", seed=11)
    assert (view["active"], view["location"], view["pool"], view["pool_max"]) == (True, "tristram", LIFE, LIFE)
    assert len(view["drawn"]) == 3 and all(line["line"] for line in view["drawn"])
    with pytest.raises(WireRefused, match="already going"):
        client.request("start_run")
    camped = client.request("camp")
    assert camped["pool"] == LIFE   # a full pool mends to itself
    assert client.request("abandon") == {"banked": 0}
    assert client.request("run") == {"active": False}


def test_learning_in_a_run_spends_points_and_unlearning_spends_reskill(tmp_path):
    campaign = campaign_at(tmp_path / "data")
    campaign.start_run(seed=11)
    assert campaign.run is not None
    campaign.run = replace(campaign.run, skill_points=4, reskill_points=1)
    tree = campaign.learn("warmth")
    assert campaign.run.skill_points == 1 and "warmth" in campaign.run.learned
    assert tree["free"] == 1 and tree["reskill"] == 1
    assert any(n["key"] == "warmth" and n["unlearnable"] for n in tree["nodes"])
    campaign.run = replace(campaign.run, reskill_points=0)
    with pytest.raises(Refusal, match="reskill"):
        campaign.unlearn("sorcery")
    campaign.run = replace(campaign.run, reskill_points=1)
    tree = campaign.unlearn("sorcery")
    assert campaign.run.skill_points == 4 and "warmth" not in campaign.run.learned
    assert campaign.run.reskill_points == 0
    with pytest.raises(Refusal, match="reskill"):
        campaign.unlearn_all()
    campaign.run = replace(campaign.run, skill_points=0)
    with pytest.raises(Refusal, match="costs"):
        campaign.learn("warmth")


def test_unlearning_outside_a_run_is_free_and_unlearn_needs_one(tmp_path):
    campaign = campaign_at(tmp_path / "data")
    with pytest.raises(Refusal, match="unlearn all"):
        campaign.unlearn("sorcery")
    assert campaign.unlearn_all()["free"] == campaign.progress.free


def test_a_run_survives_a_server_restart(tmp_path):
    data = tmp_path / "data"
    first = campaign_at(data)
    first.start_run(seed=11)
    assert first.run is not None
    first.run = replace(first.run, skill_points=4)
    first.learn("warmth")
    second = campaign_at(data)
    assert second.run is not None
    assert (second.run.seed, second.run.learned, second.run.skill_points) == (11, frozenset({"warmth"}), 1)
    second.abandon()
    assert campaign_at(data).run is None


def test_runs_do_not_leak_between_profiles(tmp_path):
    data = tmp_path / "data"
    campaign = campaign_at(data)
    campaign.start_run(seed=11)
    campaign.create_profile("second")
    assert campaign.run is None
    campaign.switch_profile("main")
    assert campaign.run is not None and campaign.run.seed == 11


def test_the_briefing_at_the_runs_location_names_goals_worst_case_and_answers(tmp_path):
    campaign = campaign_at(tmp_path / "data")
    plain = campaign.briefing("tristram")
    assert plain["goals"] == [] and plain["worst"] is None and plain["threat_answers"] is None
    campaign.start_run(seed=11)
    briefed = campaign.briefing("tristram")
    assert [g["key"] for g in briefed["goals"]] == [g.key for g in campaign.run.drawn]
    assert briefed["worst"].startswith("Worst case: ") and str(LIFE) in briefed["worst"]
    assert briefed["threat_answers"] is None or "Answers:" in briefed["threat_answers"]
    elsewhere = campaign.briefing("caves")
    assert elsewhere["goals"] == [] and elsewhere["worst"] is None


def test_a_runs_defence_settles_into_the_run_through_the_wire(client):
    client.request("start_run", seed=11)
    started = client.request("defend", location="tristram", player="warden")
    assert started["run"] is True and len(started["goals"]) == 3
    assert started["state"]["lives"] == LIFE
    result = None
    while result is None:
        for frame in client.advance(200):
            result = frame.get("result", result)
    assert result["won"] is True
    assert set(result) >= {"met", "missed", "run"}
    view = client.request("run")
    assert (view["index"], view["location"]) == (1, "graveyard")
    assert view["records"] and view["records"][0]["location"] == "tristram"
    assert client.request("leave", again=False)["then"] == "camp"


def test_defend_in_a_run_guards_its_location_and_its_fight(client):
    client.request("start_run", seed=11)
    with pytest.raises(WireRefused, match="run is at"):
        client.request("defend", location="caves")
    with pytest.raises(WireRefused, match="run's wager"):
        client.request("summon_preview")
    client.request("defend", location="tristram")
    with pytest.raises(WireRefused, match="Finish the defence"):
        client.request("defend", location="tristram")
    assert len(client.request("summon_preview")["stakes"]) == 3
    assert client.request("abandon") == {"banked": 0}   # the defence waits in the save
    assert client.request("run")["active"] is True
    assert client.request("abandon") == {"banked": 0}   # at the camp, the run ends
    assert client.request("run") == {"active": False}


def test_the_bonus_preview_names_every_stake_and_summoning_too_early_refuses(tmp_path):
    campaign = campaign_at(tmp_path / "data")
    campaign.start_run(seed=11)
    battle = campaign.defend("tristram")
    table = campaign.summon_preview()
    assert [s["stake"] for s in table["stakes"]] == [1, 2, 3]
    assert all(s["wager"] > 0 and s["profit"] > 0 and "Stake" in s["words"] for s in table["stakes"])
    why, _ = battle.order("summon", {"stake": 1})
    assert why is not None   # no break is open yet


def test_a_lost_defence_ends_the_run_and_banks_its_salvage(tmp_path):
    from hellward.sim.model import World
    campaign = campaign_at(tmp_path / "data")
    campaign.start_run(seed=11)
    battle = campaign.defend("tristram")
    world = battle.world
    assert isinstance(world, World)
    world.lives, world.outcome = 0, "defeat"
    result = campaign._keep_run(world)
    assert result["won"] is False and campaign.run.lost
    assert campaign.progress.runs_lost == 1
    assert campaign.leave(False)["then"] == "summary"


def test_goal_events_reach_the_client_as_verdicts_change(tmp_path):
    campaign = campaign_at(tmp_path / "data")
    campaign.start_run(seed=11)
    battle = campaign.defend("tristram", player="warden")
    goals = []
    while battle.world.outcome is None:
        for frame in battle.advance(200):
            goals.extend(e for e in frame["events"] if e[0] == "goal")
    assert goals   # the warden's many towers fail the lean goal, live
    assert battle.result is not None and "met" in battle.result


def test_an_order_that_would_fail_a_goal_warns_first(tmp_path):
    from dataclasses import replace as dc_replace

    from hellward.run import kit as deal_kit
    from hellward.run.goals import Drawn
    from hellward.server.battle import Battle
    campaign = campaign_at(tmp_path / "data")
    campaign.start_run(seed=11)
    assert campaign.run is not None
    campaign.run = dc_replace(campaign.run, drawn=(Drawn("lean", "0"),))
    dealt = deal_kit(campaign.run)
    battle = Battle(dealt.location, planner=planner.smart, kit=dealt, run_seed=11, run_index=0,
                    drawn=campaign.run.drawn)
    tile = next((x, y) for y in range(dealt.location.level.height) for x in range(dealt.location.level.width)
                if dealt.location.level.buildable(x, y))
    why, frame = battle.order("build", {"kind": "arrow", "tile": list(tile)})
    assert why is None
    assert any("at most 0 towers" in w for w in frame.get("warnings", []))
    assert ["goal", "lean", "failed"] in frame["events"]


def test_the_save_mid_defence_holds_the_kit_and_the_log(tmp_path):
    from hellward.server.saves import Saves
    data = tmp_path / "data"
    campaign = campaign_at(data)
    campaign.start_run(seed=11)
    battle = campaign.defend("tristram")
    battle.advance(250)   # past the first second mark
    saved = Saves(data / "saves").load("run")
    assert saved is not None
    assert saved["state"]["kit"] is not None and saved["state"]["kit"]["location"] == "tristram"
    assert saved["state"]["log"]["marks"]


def _snapshot(world):
    """The defence's state, rounded past float dust: a resume must match it exactly."""
    return {
        "time": round(world.time, 6), "gold": world.gold, "lives": world.lives, "kills": world.kills,
        "wave": world.wave, "mana": round(world.mana, 3), "xp": round(world.xp_total, 3),
        "towers": sorted((t.kind.key, t.tile, t.level, round(t.cooldown, 3), t.spent)
                         for t in world.towers.values()),
        "monsters": sorted((m.kind.key, round(m.hp, 2), round(m.s, 3), m.route,
                            round(m.cooldown, 3)) for m in world.monsters),
    }


def test_a_saves_resume_replays_the_log_exactly_mid_wave_included(tmp_path):
    from hellward.server.saves import Saves
    data = tmp_path / "data"
    first = campaign_at(data)
    first.start_run(seed=11)
    battle = first.defend("tristram")
    level = battle.location.level
    tiles = [(x, y) for y in range(level.height) for x in range(level.width) if level.buildable(x, y)]
    assert battle.order("build", {"kind": "arrow", "tile": list(tiles[0])})[0] is None
    assert battle.order("build", {"kind": "arrow", "tile": list(tiles[1])})[0] is None
    assert battle.order("call_wave", {})[0] is None
    battle.advance(200)   # ten seconds in, mid first wave
    assert battle.world.wave == 0 and battle.world.monsters
    before = _snapshot(battle.world)
    saved = Saves(data / "saves").load("run")
    assert saved is not None and saved["state"]["log"]["marks"]

    second = campaign_at(data)
    assert second.battle is None and second.run is not None
    started = second.resume()
    assert started["run"] is True
    resumed = second.battle
    assert resumed is not None
    assert _snapshot(resumed.world) == before
    assert resumed.log["decisions"] == saved["state"]["log"]["decisions"]
    battle.advance(100)
    resumed.advance(100)
    assert _snapshot(resumed.world) == _snapshot(battle.world)


def test_defend_returns_to_a_waiting_defence_instead_of_a_fresh_one(tmp_path):
    data = tmp_path / "data"
    first = campaign_at(data)
    first.start_run(seed=11)
    battle = first.defend("tristram")
    battle.advance(250)
    at_quit = battle.world.time
    assert at_quit > 1.0
    first.abandon()
    assert first.run is not None   # quitting keeps the run
    second = campaign_at(data)
    back = second.defend("tristram")   # not resume: defend itself returns
    assert back.world.time > 0.0 and back.world.time <= at_quit
    assert back.world.time >= at_quit - 1.0   # never more than a second rewound


def test_resume_refuses_without_a_run_a_defence_or_a_quiet_battle(tmp_path):
    campaign = campaign_at(tmp_path / "data")
    with pytest.raises(Refusal, match="No run"):
        campaign.resume()
    campaign.start_run(seed=11)
    with pytest.raises(Refusal, match="No defence"):
        campaign.resume()
    campaign.defend("tristram")
    with pytest.raises(Refusal, match="already being fought"):
        campaign.resume()


def test_the_threats_label_names_armor_flyers_tags_boss_and_curses():
    from hellward.server.campaign import threats
    assert threats(LOCATIONS["tristram"])["boss"] is None
    assert threats(LOCATIONS["hells_gate"])["boss"] == "Azazel the Flayer"
    assert threats(LOCATIONS["catacombs"])["armor"] == 2
    assert "Gargoyle" in threats(LOCATIONS["caves"])["flyers"]
    assert threats(LOCATIONS["cathedral"])["weaknesses"] == []
    assert threats(LOCATIONS["tristram"])["curses"]


def test_the_worst_case_counts_the_roster_and_a_bosss_strikes():
    assert worst_line(LOCATIONS["tristram"], 30).startswith("Worst case: ")
    assert "strikes at 5" in worst_line(LOCATIONS["temple"], 30)


def test_the_answers_line_names_what_beats_the_standout_or_nothing_to_answer():
    assert answers_line(LOCATIONS["tristram"], frozenset()) is None   # nothing wears armor there
    assert answers_line(LOCATIONS["cathedral"], frozenset()) is None   # arrows already deal the most
    line = answers_line(LOCATIONS["catacombs"], frozenset())
    assert line is not None and "your Arrow Towers deal 1" in line
    assert "Answers: Ballista (locked)." in line
    witches = answers_line(LOCATIONS["caves"], frozenset())
    assert witches is not None and witches.startswith("Blood Witches:")
