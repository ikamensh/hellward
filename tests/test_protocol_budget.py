"""The protocol stays cheap: tools/protocol_bench.py's measures of a real defence through the server, held to a
budget with room for a busy machine (measured 2026-10-01 on the M4: Tristram's frames 883 B mean, 2.2 KB at most,
encoded in 19 us; a round trip 50 us). The client's parse time is held in Godot (tests/run.gd)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "tools" / "protocol_bench.py"


def test_a_defence_through_the_server_stays_within_the_protocols_budget(tmp_path):
    out = tmp_path / "bench.json"
    # its own process: the bench runs the compiled simulation, which must be attached before the rules are imported
    subprocess.run([sys.executable, str(BENCH), "--locations", "tristram", "--out", str(out)], check=True,
                   capture_output=True)
    result = json.loads(out.read_text())
    row = result["locations"]["tristram"]
    assert row["bytes_mean"] < 2048 and row["bytes_max"] < 8192, row
    assert row["encode_us_mean"] < 200, row
    assert result["round_trip_us_p99"] < 5000, result
