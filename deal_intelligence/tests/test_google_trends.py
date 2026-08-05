"""Unit tests for google_trends.py's pure math -- _pct_change_vs_prior_period
never touches the network; the fetch functions themselves aren't tested here
(no live Trends calls in a test suite), matching this codebase's convention
of not testing I/O-heavy wrappers directly."""
from deal_intelligence.google_trends import _pct_change_vs_prior_period


class TestPctChangeVsPriorPeriod:
    def test_needs_at_least_8_weeks_of_history(self):
        assert _pct_change_vs_prior_period([1, 2, 3, 4, 5, 6, 7]) is None

    def test_computes_recent_4_weeks_vs_prior_4_weeks(self):
        # prior mean = 10, recent mean = 20 -> +100%
        series = [10, 10, 10, 10, 20, 20, 20, 20]
        assert _pct_change_vs_prior_period(series) == 100.0

    def test_flat_interest_is_zero_percent(self):
        series = [50] * 8
        assert _pct_change_vs_prior_period(series) == 0.0

    def test_zero_prior_baseline_returns_none_not_infinite(self):
        series = [0, 0, 0, 0, 5, 5, 5, 5]
        assert _pct_change_vs_prior_period(series) is None

    def test_decline_reads_negative(self):
        series = [20, 20, 20, 20, 10, 10, 10, 10]
        assert _pct_change_vs_prior_period(series) == -50.0
