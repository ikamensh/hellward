"""S3: the leaders' curses go for the hymned tower (tools/balance.py measures the lift)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import balance  # noqa: E402


def test_the_lift_is_hymned_aimed_towers_over_the_hymned_share_in_reach():
    assert balance.chant_lift([(1, 0.5), (0, 0.5), (1, 0.25)]) == (1.6, 2, 1.25)
    assert balance.chant_lift([]) == (0.0, 0, 0)


def test_a_random_curser_reads_one_by_construction():
    chants = [c for i in range(4) for c in balance.match("random", i, 8, "caves")["chants"]]
    lift, hymned, expected = balance.chant_lift(chants)
    assert 0.5 < lift < 1.5 and expected >= 2.0


def test_smart_curses_a_hymned_tower_twice_as_often():
    chants = [c for i in range(4) for c in balance.match("smart", i, 8, "caves")["chants"]]
    lift, hymned, expected = balance.chant_lift(chants)
    assert lift >= 1.5 and expected >= 2.0
