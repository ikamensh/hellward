"""Full runs (tools/runs.py) settle every location into the run, write the corpus, and report the criteria."""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import runs  # noqa: E402
from hellward.run import CAMP_HEAL  # noqa: E402


def test_an_immortal_run_settles_two_locations_and_writes_their_kits(tmp_path):
    summaries = runs.main(["--bot", "middling", "--seeds", "1", "--seed0", "123", "--jobs", "1",
                           "--immortal", "--locations", "tristram,graveyard", "--out", str(tmp_path)])
    (summary,) = summaries
    assert summary["reached"] == 2 and summary["won"]
    assert summary["locations"]["tristram"]["won"]
    assert "pool" in summary and "carried" in summary and "tree" in summary
    for key in ("tristram", "graveyard"):
        kit = json.loads((tmp_path / "corpus" / "middling" / "123" / f"{key}.json").read_text())
        assert kit["location"] == key
    stored = json.loads((tmp_path / "summary.json").read_text())
    assert stored[0]["seed"] == 123


def test_the_bonus_rule_weighs_leaks_pool_repeats_margin_and_the_wager_in_hand():
    w1, w2, w3 = (runs._wager(stake) for stake in (1, 2, 3))
    loc = runs.LOCATIONS["tristram"]
    rich = (loc, 7, 0, 99999)
    assert runs._stake("strong", 30, False, 0, 4, 999, *rich) == 3
    assert runs._stake("strong", 30, False, 0, 1, 999, *rich) == 3
    assert runs._stake("middling", 30, False, 0, 4, 999, *rich) == 3
    assert runs._stake("middling", 22, False, 0, 1, 999, *rich) == 3
    assert runs._stake("middling", 19, False, 0, 1, 999, *rich) == 1
    assert runs._stake("middling", 18, False, 0, 1, 999, *rich) == 1
    assert runs._stake("middling", 17, False, 0, 1, 999, *rich) is None
    assert runs._stake("strong", 30, False, 0, 4, w3, *rich) == 3
    assert runs._stake("strong", 30, False, 0, 4, w3 - 1, *rich) == 2
    assert runs._stake("strong", 30, False, 0, 4, w2, *rich) == 2
    assert runs._stake("strong", 30, False, 0, 4, w1, *rich) == 1
    assert runs._stake("strong", 30, False, 0, 4, w1 - 1, *rich) is None
    assert runs._stake("strong", 30, True, 0, 4, 999, *rich) is None
    assert runs._stake("strong", 30, False, 3, 4, 999, *rich) is None
    assert runs._stake("strong", 30, False, 0, 0, 999, *rich) is None
    assert runs._stake("strong", 5, False, 0, 4, 999, *rich) is None
    hp1 = runs._pack_hp(loc, 1, 7, 0, 0, 1)
    hp3 = runs._pack_hp(loc, 3, 7, 0, 0, 1)
    strong, middling = runs.MARGIN["strong"], runs.MARGIN["middling"]
    assert runs._stake("strong", 30, False, 0, 1, 999, loc, 7, 0, 0) is None
    assert runs._stake("strong", 30, False, 0, 1, 999, loc, 7, 0,
                        math.ceil(strong * hp1) - 1) is None
    assert runs._stake("strong", 30, False, 0, 1, 999, loc, 7, 0,
                        math.ceil(strong * hp1)) == 1
    assert runs._stake("strong", 30, False, 0, 1, 999, loc, 7, 0,
                        math.ceil(strong * hp3)) == 3
    thin = math.ceil(middling * hp1)
    assert runs._stake("middling", 30, False, 0, 1, 999, loc, 7, 0, thin) == 1
    assert runs._stake("strong", 30, False, 0, 1, 999, loc, 7, 0, thin) is None


def test_the_bonus_rule_pursuing_the_goal_fights_the_second_stake_lean():
    w1, w2 = runs._wager(1), runs._wager(2)
    loc = runs.LOCATIONS["caves"]
    hp2 = runs._pack_hp(loc, 2, 7, 4, 0, 3)
    lean = math.ceil(runs.MARGIN["strong"] * hp2) - 1   # under the felt margin, over the pursuit's
    assert lean >= runs.PURSUE_MARGIN * hp2
    assert runs._stake("strong", 30, False, 0, 3, w2, loc, 7, 4, lean, 2) == 2
    assert runs._stake("strong", 30, False, 0, 3, w2, loc, 7, 4, lean) == 1
    assert runs._stake("strong", 30, False, 0, 2, w2, loc, 7, 4, lean, 2) is None
    assert runs._reserve("strong", 30, False, 0, 3, 0, (3, 2, 1), loc, 7, 4, lean, 2) == w2
    assert runs._reserve("strong", 30, False, 0, 3, 0, (3, 2, 1), loc, 7, 4, lean) == w1
    assert runs._reserve("strong", 30, False, 0, 2, 2 * w2, (3, 2, 1), loc, 7, 4, lean, 2) == 0
    assert runs._reserve("strong", 30, False, 0, 2, 0, (3, 2, 1), loc, 7, 4, lean, 2) == 0
    assert runs._reserve("strong", 30, False, 0, 2, 0, (3, 2, 1), loc, 7, 4, lean) == 0
    ragged = math.ceil(runs.PURSUE_MARGIN * hp2) - 1   # under the pursuit's bar: no second stake
    assert runs._stake("strong", 30, False, 0, 3, w2, loc, 7, 4, ragged, 2) is None
    assert runs._stake("strong", 24, False, 0, 3, w2, loc, 7, 4, ragged, 2) is None
    assert runs._reserve("strong", 30, False, 0, 3, 0, (3, 2, 1), loc, 7, 4, ragged, 2) == 0
    assert runs._reserve("strong", 24, False, 0, 3, 0, (3, 2, 1), loc, 7, 4, ragged, 2) == 0


def test_the_bonus_rule_never_wagers_a_pack_that_leaves_the_pool_under_its_spare():
    hells = runs.LOCATIONS["hells_gate"]
    lives = {stake: runs._pack_lives(hells, stake, 7, 4, 0, 3) for stake in (1, 2, 3)}
    spare, fat = runs.VETO_SPARE, 99999   # the margin passes every stake: the veto decides
    for stake in (1, 2, 3):
        need = lives[stake] + spare
        assert need - 1 >= runs.POOL_STAKES[3 - stake]   # comfort passes: the veto decides
        wager = runs._wager(stake)
        assert runs._reserve("strong", need, False, 0, 3, 0, (stake,), hells, 7, 4, fat) == wager
        assert runs._reserve("strong", need - 1, False, 0, 3, 0, (stake,), hells, 7, 4, fat) == 0
    assert lives[1] <= lives[2] and lives[1] <= lives[3]
    assert runs._stake("strong", lives[3] + spare, False, 0, 3, 999, hells, 7, 4, fat) == 3
    assert runs._stake("strong", lives[1] + spare - 1, False, 0, 3, 999, hells, 7, 4, fat) is None


def test_the_coming_breaks_wager_is_held_back_from_strength_deep_and_surplus_shallow():
    w1, w2, w3 = (runs._wager(stake) for stake in (1, 2, 3))
    loc = runs.LOCATIONS["tristram"]
    all_stakes = (3, 2, 1)
    strong, middling = "strong", "middling"
    assert runs._reserve(strong, 30, False, 0, 4, 0, all_stakes, loc, 7, 0, 99999) == w3
    assert runs._reserve(strong, 30, False, 0, 3, 0, all_stakes, loc, 7, 0, 99999) == w3
    assert runs._reserve(strong, 30, False, 0, 2, 2 * w3, all_stakes, loc, 7, 0, 99999) == w3
    assert runs._reserve(strong, 30, False, 0, 2, 2 * w3 - 1, all_stakes, loc, 7, 0, 99999) == w2
    assert runs._reserve(strong, 30, False, 0, 2, 2 * w2 - 1, all_stakes, loc, 7, 0, 99999) == w1
    assert runs._reserve(strong, 30, False, 0, 1, 2 * w1, all_stakes, loc, 7, 0, 99999) == w1
    assert runs._reserve(strong, 30, False, 0, 1, 2 * w1 - 1, all_stakes, loc, 7, 0, 99999) == 0
    assert runs._reserve(strong, 30, False, 0, 0, 999, all_stakes, loc, 7, 0, 99999) == 0
    assert runs._reserve(strong, 22, False, 0, 4, 0, all_stakes, loc, 7, 0, 99999) == w3
    caves = runs.LOCATIONS["caves"]
    assert runs._reserve(strong, 19, False, 0, 4, 0, all_stakes, caves, 7, 4, 99999) == w1
    assert runs._reserve(strong, 18, False, 0, 1, 999, all_stakes, loc, 7, 0, 99999) == w1
    assert runs._reserve(strong, 17, False, 0, 1, 999, all_stakes, loc, 7, 0, 99999) == 0
    assert runs._reserve(strong, 5, False, 0, 4, 999, all_stakes, loc, 7, 0, 99999) == 0
    assert runs._reserve(strong, 30, True, 0, 4, 999, all_stakes, loc, 7, 0, 99999) == 0
    assert runs._reserve(strong, 30, False, 3, 4, 999, all_stakes, loc, 7, 0, 99999) == 0
    assert runs._reserve(strong, 30, False, 0, 4, 0, (3,), loc, 7, 0, 99999) == w3
    assert runs._reserve(strong, 19, False, 0, 4, 0, (3,), loc, 7, 0, 99999) == 0
    assert runs._reserve(strong, 30, False, 0, 4, 0, all_stakes, loc, 7, 0, 0) == 0
    thin = math.ceil(runs.MARGIN[middling] * runs._pack_hp(loc, 1, 7, 0, 0, 1))
    assert runs._reserve(middling, 30, False, 0, 1, 999, all_stakes, loc, 7, 0, thin) == w1
    assert runs._reserve(strong, 30, False, 0, 1, 999, all_stakes, loc, 7, 0, thin) == 0


def test_a_run_never_misfires_its_summons(tmp_path):
    (summary,) = runs.main(["--bot", "strong", "--seeds", "1", "--seed0", "1", "--jobs", "1",
                            "--immortal", "--locations", "tristram,graveyard,cathedral",
                            "--out", str(tmp_path)])
    assert summary["misfires"] == 0
    assert isinstance(summary["bonus_net"], int)


def test_a_clean_clear_does_not_resummon_past_the_cap(tmp_path):
    """Seed 0 summons at the cap in the caves: the rule counts its summons and stops at three."""
    (summary,) = runs.main(["--bot", "strong", "--seeds", "1", "--seed0", "0", "--jobs", "1",
                            "--immortal", "--locations", "tristram,graveyard,cathedral,catacombs,caves",
                            "--out", str(tmp_path)])
    assert summary["reached"] == 5
    per_location: dict[str, int] = {}
    for key, _ in summary["summons"]:
        per_location[key] = per_location.get(key, 0) + 1
    assert per_location.get("caves") == 3
    assert max(per_location.values()) <= 3


def test_a_real_run_with_the_stored_plan_wins_tristram(tmp_path):
    (summary,) = runs.main(["--bot", "strong", "--seeds", "1", "--seed0", "7", "--jobs", "1",
                            "--locations", "tristram", "--out", str(tmp_path)])
    assert summary["locations"]["tristram"]["won"]
    lost = summary["locations"]["tristram"]["lives_lost"]
    assert summary["pool"] == 30 - lost + math.ceil(lost * CAMP_HEAL)   # the camp heals its share
