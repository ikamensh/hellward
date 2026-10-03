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
