"""The campaign's balance table (tools/campaign_balance.py) runs end to end, fills every column, and plays the
campaign in order with the sigils B* has earned."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import campaign_balance  # noqa: E402


def test_two_defences_make_table_rows_with_every_column_and_the_second_has_the_sigils_the_first_earned(tmp_path):
    campaign_balance.main(["--players", "ordinary", "--locations", "tristram,graveyard", "--difficulties", "normal",
                           "--seeds", "1000", "--jobs", "1", "--out", str(tmp_path)])
    lines = (tmp_path / "table.md").read_text().splitlines()
    header = lines.index("| " + " | ".join(campaign_balance.COLUMNS) + " |")
    tristram, graveyard = ([cell.strip() for cell in line.strip("|").split("|")] for line in lines[header + 2:header + 4])
    assert len(tristram) == len(graveyard) == len(campaign_balance.COLUMNS)
    assert tristram[:4] == ["tristram", "normal", "ordinary B*", "0"]
    assert tristram[4] in ("0/1", "1/1")
    runs = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert [r["location"] for r in runs] == ["tristram", "graveyard"]
    run = runs[0]
    assert run["player"] == "ordinary" and run["seed"] == 1000 and run["leaders"] == "smart"
    assert run["outcome"] in ("victory", "defeat")
    assert run["lives"] + run["lost"] == 20
    assert run["chants"] >= run["landed"] > 0 and run["decide_ms"]
    assert run["chants"] >= run["broken_chants"] and run["broken"] >= run["broken_chants"]
    assert len(run["leaks"]) == 5 and sum(run["leaks"]) >= run["lost"]
    assert graveyard[:4] == ["graveyard", "normal", "ordinary B*", str(run["earned"])]
    assert runs[1]["sigils"] == run["earned"]


def test_the_sigils_follow_the_campaign_so_a_later_location_alone_needs_a_fixed_budget(tmp_path):
    with pytest.raises(SystemExit):
        campaign_balance.main(["--locations", "cathedral", "--out", str(tmp_path)])
    assert not (tmp_path / "table.md").exists()


def fake_run(player, location, difficulty, seed, sigils, **_):
    """B* ("a") keeps more lives and earns 1, 2, 3 or 9 sigils by seed; "b" would earn 3 every time."""
    earned = {1: 1, 2: 2, 3: 3, 4: 9}[seed] if player == "a" else 3
    return {"player": player, "location": location, "difficulty": difficulty, "seed": seed, "sigils": sigils,
            "outcome": "victory", "lives": 20 if player == "a" else 10, "earned": earned,
            "chants": 4, "broken": 3, "broken_chants": 1, "leaders_spawned": 2, "curse_seconds": 5.0,
            "spells": {}, "mana_capped": 0.0, "decide_ms": [1.0]}


class InProcess:
    """An executor that runs each job in this process, in order."""

    map = staticmethod(map)


def test_each_stage_gets_the_sum_of_b_stars_median_low_sigils_before_it_and_hell_carries_normals_total(monkeypatch):
    monkeypatch.setattr(campaign_balance, "play", fake_run)
    order = campaign_balance.campaign_order()
    stages = campaign_balance.play_campaign(InProcess(), ["a", "b"], order, [1, 2, 3, 4], None)
    assert [(s.difficulty, s.location) for s in stages] == order
    assert {s.best for s in stages} == {"a"}
    assert [s.sigils for s in stages] == [2 * i for i in range(len(order))]   # median_low of 1, 2, 3, 9 is 2
    assert [r["sigils"] for r in stages[-1].runs] == [2 * (len(order) - 1)] * 8
    fixed = campaign_balance.play_campaign(InProcess(), ["a", "b"], order[:3], [1, 2, 3, 4], 7)
    assert [s.sigils for s in fixed] == [7, 7, 7]


def test_chants_broken_are_the_broken_chants_among_all_chants_begun_not_the_broken_ponderings(monkeypatch):
    monkeypatch.setattr(campaign_balance, "play", fake_run)
    stages = campaign_balance.play_campaign(InProcess(), ["a"], campaign_balance.campaign_order()[:1], [1, 2], None)
    (row,) = campaign_balance.rows(stages, ["a"])
    assert row["broken_share"] == 0.25
    assert row["curse_per_leader"] == 2.5


@pytest.mark.parametrize("edge", [0.1, 0.7, 1.37, 2.5, 10.0])
def test_the_margin_is_bisected_to_two_percent_inside_its_bracket(monkeypatch, edge):
    played = []

    def up_to_edge(player, location, difficulty, seed, sigils, *, hp):
        played.append(hp)
        return {"outcome": "victory" if hp <= edge else "defeat", "hp": hp}

    monkeypatch.setattr(campaign_balance, "play", up_to_edge)
    m, runs = campaign_balance.margin("a", "tristram", "normal", 1000, 0)
    low, high = campaign_balance.MARGIN_RANGE
    assert [r["hp"] for r in runs] == played and len(played) == 7   # 2% of a tenfold bracket
    assert all(low < hp < high for hp in played)
    shown = campaign_balance.show_margin(m)
    if edge < low:
        assert m == low and shown == "<0.41"
    elif edge > high:
        assert m * campaign_balance.MARGIN_STEP >= high and shown.startswith(">")
    else:
        assert m <= edge < m * campaign_balance.MARGIN_STEP and shown == f"{m:.2f}"


def test_leader_impact_is_the_lives_lost_to_smart_leaders_beyond_random_ones_and_its_share():
    stage = campaign_balance.Stage("cathedral", "normal", 6, [], "a", uncapped={
        "smart": [{"lost": 10}, {"lost": 20}], "random": [{"lost": 5}, {"lost": 5}]})
    delta, share = campaign_balance.impact(stage)
    assert delta == 10 and share == pytest.approx(2 / 3)


def test_b_star_has_the_best_median_lives_then_more_wins_then_more_mean_lives():
    def runs(player, *lives, falls=0):
        return [{"player": player, "lives": n, "outcome": "defeat" if i < falls else "victory"} for i, n in enumerate(lives)]

    assert campaign_balance.best(runs("a", 20, 0, 20) + runs("b", 15, 15, 15), ["a", "b"]) == "a"
    assert campaign_balance.best(runs("a", 0, 10, 20, falls=1) + runs("b", 10, 10, 10), ["a", "b"]) == "b"
    assert campaign_balance.best(runs("a", 10, 10, 10) + runs("b", 10, 10, 13), ["a", "b"]) == "b"
