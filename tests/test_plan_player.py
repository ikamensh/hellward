"""The plan search must select builds for the defence people actually play."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import plan_player  # noqa: E402


def test_finalist_selection_prefers_the_real_difficulty():
    """A build that excels only in the search's raised or lowered HP trial cannot displace a better real build."""
    actual_scores = [18.0, 27.0, 27.0]
    challenge_scores = [35.0, 30.0, 33.0]

    assert plan_player.best_finalist(actual_scores, challenge_scores) == 2


def test_search_never_trains_on_easier_enemy_health_than_the_game():
    """When a build struggles, the search keeps improving it at ordinary HP instead of lowering the bar."""
    assert plan_player.next_life(1.0, plan_player.FALTER - 1) == 1.0
    assert plan_player.next_life(1.2, plan_player.FALTER - 1) >= 1.0
