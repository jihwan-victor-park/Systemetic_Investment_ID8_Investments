"""Unit tests for radar_signal_series.growth_rate's pure math -- fabricated
series, zero mocking. append_sample/read_series are thin Firestore I/O
wrappers with no logic of their own to unit-test in isolation; they're
exercised for real by `python -m deal_intelligence.radar_backfill --dry-run`
against the local emulator (see that command's own docs)."""
from deal_intelligence import radar_signal_series as rss


def test_growth_rate_fewer_than_two_samples_is_none():
    assert rss.growth_rate([]) is None
    assert rss.growth_rate([{"date": "2026-01-01", "value": 40}]) is None


def test_growth_rate_worked_example_from_the_doc(): # RADAR_SIGNAL_ENGINE.md §3: 45 -> 94 heads, 17 months -- here scoped to a 90-day window
    series = [
        {"date": "2026-01-01", "value": 61},
        {"date": "2026-04-01", "value": 94},  # 90 days later
    ]
    rate = rss.growth_rate(series, window_days=90)
    assert rate > 0.4  # well over the 40% annualized headcount_growth_40 threshold


def test_growth_rate_decline_is_negative():
    series = [
        {"date": "2026-01-01", "value": 100},
        {"date": "2026-02-01", "value": 85},
    ]
    rate = rss.growth_rate(series, window_days=90)
    assert rate < 0


def test_growth_rate_flat_is_zero():
    series = [
        {"date": "2026-01-01", "value": 50},
        {"date": "2026-03-01", "value": 50},
    ]
    assert rss.growth_rate(series) == 0.0


def test_growth_rate_falls_back_to_full_series_when_younger_than_window():
    # Only 20 days of history exists at all -- shouldn't refuse to compute
    # just because it's short of the 90-day window.
    series = [
        {"date": "2026-01-01", "value": 40},
        {"date": "2026-01-21", "value": 44},
    ]
    assert rss.growth_rate(series, window_days=90) is not None


def test_growth_rate_ignores_samples_older_than_the_window():
    series = [
        {"date": "2020-01-01", "value": 1000},  # ancient outlier, should be excluded by the 90-day window
        {"date": "2026-01-01", "value": 50},
        {"date": "2026-03-01", "value": 55},
    ]
    rate = rss.growth_rate(series, window_days=90)
    assert rate > 0  # would be wildly different (near -1) if the ancient sample leaked in
    assert rate < 5


def test_growth_rate_zero_oldest_value_is_none_not_a_crash():
    series = [
        {"date": "2026-01-01", "value": 0},
        {"date": "2026-02-01", "value": 5},
    ]
    assert rss.growth_rate(series) is None


def test_mom_growth_rate_fewer_than_two_samples_is_none():
    assert rss.mom_growth_rate([]) is None
    assert rss.mom_growth_rate([{"date": "2026-01-01", "value": 40}]) is None


def test_mom_growth_rate_positive():
    series = [
        {"date": "2026-01-01", "value": 100},
        {"date": "2026-02-01", "value": 106},  # 31 days later, +6%
    ]
    assert rss.mom_growth_rate(series) == 0.06


def test_mom_growth_rate_negative():
    series = [
        {"date": "2026-01-01", "value": 100},
        {"date": "2026-02-05", "value": 90},
    ]
    assert rss.mom_growth_rate(series) < 0


def test_mom_growth_rate_picks_closest_prior_sample_not_the_oldest():
    series = [
        {"date": "2025-01-01", "value": 10},   # ancient -- should NOT be used
        {"date": "2026-01-01", "value": 100},  # ~31 days before latest -- the real "last month" reading
        {"date": "2026-02-01", "value": 110},
    ]
    assert rss.mom_growth_rate(series) == 0.1  # (110-100)/100, not (110-10)/10


def test_mom_growth_rate_no_prior_sample_old_enough_is_none():
    # Two reads only a week apart -- no real "last month" comparison exists yet.
    series = [
        {"date": "2026-01-01", "value": 40},
        {"date": "2026-01-08", "value": 44},
    ]
    assert rss.mom_growth_rate(series) is None


def test_mom_growth_rate_zero_prior_value_is_none_not_a_crash():
    series = [
        {"date": "2026-01-01", "value": 0},
        {"date": "2026-02-01", "value": 5},
    ]
    assert rss.mom_growth_rate(series) is None
