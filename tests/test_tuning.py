"""The shared life-margin search preserves the tuning tools' bracket conventions."""

from tools.tuning import life_margin


def test_a_checked_margin_reports_an_unwinnable_lower_bound_or_a_winnable_upper_bound():
    assert life_margin(lambda life: life <= 0.1, 0.2, 12.0, check_low=True, check_high=True) == 0.0
    assert life_margin(lambda life: life <= 20.0, 0.2, 12.0, check_low=True, check_high=True) == 12.0


def test_a_margin_inside_the_bracket_is_within_two_percent_of_the_winning_edge():
    for edge in (0.5, 1.0, 2.0, 8.0):
        found = life_margin(lambda life: life <= edge, 0.2, 12.0, check_low=True, check_high=True)
        assert found <= edge < found * 1.02
