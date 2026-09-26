"""The campaign's balance table (tools/campaign_balance.py) runs end to end and fills every column."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import campaign_balance  # noqa: E402


def test_one_defence_makes_a_table_row_with_every_column_and_a_recorded_run(tmp_path):
    campaign_balance.main(["--players", "ordinary", "--locations", "tristram", "--difficulties", "normal",
                           "--seeds", "1000", "--jobs", "1", "--out", str(tmp_path)])
    lines = (tmp_path / "table.md").read_text().splitlines()
    header = lines.index("| " + " | ".join(campaign_balance.COLUMNS) + " |")
    row = [cell.strip() for cell in lines[header + 2].strip("|").split("|")]
    assert len(row) == len(campaign_balance.COLUMNS)
    assert row[:4] == ["tristram", "normal", "ordinary B*", "0"]
    assert row[4] in ("0/1", "1/1")
    runs = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert len(runs) == 1
    run = runs[0]
    assert run["player"] == "ordinary" and run["seed"] == 1000 and run["leaders"] == "smart"
    assert run["outcome"] in ("victory", "defeat")
    assert run["lives"] + run["lost"] == 20
    assert run["chants"] >= run["landed"] > 0 and run["decide_ms"]
    assert len(run["leaks"]) == 5 and sum(run["leaks"]) >= run["lost"]


def test_the_sigils_follow_the_campaign_so_a_later_location_alone_needs_a_fixed_budget(tmp_path):
    with pytest.raises(SystemExit):
        campaign_balance.main(["--locations", "cathedral", "--out", str(tmp_path)])
    assert not (tmp_path / "table.md").exists()
