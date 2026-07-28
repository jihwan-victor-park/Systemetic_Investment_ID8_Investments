"""Unit tests for capital_clock.py's pure burn/cash-out arithmetic -- no
network, no Firestore; everything here runs instantly."""
from datetime import date

from deal_intelligence import capital_clock as cc


def test_classify_capital_intensity_high_keyword():
    assert cc.classify_capital_intensity("Hardware", "builds satellites") == "high"


def test_classify_capital_intensity_low_keyword():
    assert cc.classify_capital_intensity("B2B SaaS", "workflow software for ops teams") == "low"


def test_classify_capital_intensity_defaults_medium():
    assert cc.classify_capital_intensity(None, "a company that does things") == "medium"


def test_classify_capital_intensity_high_wins_over_low_on_conflict():
    # e.g. "AI hardware startup building a software platform" -- high is the
    # costlier, more time-sensitive class, so it's checked first.
    assert cc.classify_capital_intensity("AI hardware", "software platform for chips") == "high"


def test_cost_per_head_known_combo():
    assert cc.cost_per_head("NA", "medium") == 240_000


def test_cost_per_head_unknown_region_falls_back_to_default():
    assert cc.cost_per_head("other", "medium") == cc.DEFAULT_COST_PER_HEAD


def test_add_months_simple():
    assert cc._add_months(date(2026, 2, 10), -12) == date(2025, 2, 10)


def test_add_months_clamps_short_target_month():
    # 31 Mar - 1 month -> Feb has no 31st, clamp to the 28th (2026 not a leap year)
    assert cc._add_months(date(2026, 3, 31), -1) == date(2026, 2, 28)


def test_compute_missing_headcount_returns_partial_with_reason():
    result = cc.compute(
        {"roundSize": 32_000_000, "roundDate": "2026-02-10", "region": "NA"},
        headcount=None, as_of=date(2026, 8, 5),
    )
    assert result["estMonthlyBurn"] is None
    assert "headcount" in result["assumptions"]
    assert result["monthsSinceRound"] is not None  # computable even without headcount


def test_compute_missing_round_date_returns_partial():
    result = cc.compute(
        {"roundSize": 32_000_000, "roundDate": None, "region": "NA"},
        headcount=80, as_of=date(2026, 8, 5),
    )
    assert result["estCashOutDate"] is None
    assert "roundDate" in result["assumptions"]


def test_compute_northwind_worked_example(): # RADAR_PLAN.md §7.1, approximately -- "AI-heavy (own model training)"
    result = cc.compute(
        {"roundSize": 32_000_000, "roundDate": "2026-02-10", "region": "NA",
         "radarCategory": "AI data infrastructure", "description": "in-house model training",
         "headcountCheckedAt": "2026-07-20"},
        headcount=81, as_of=date(2026, 8, 5),
    )
    assert result["capitalIntensity"] == "high"
    assert result["estMonthlyBurn"] > 0
    assert result["runwayMonths"] > 0
    assert result["predictedWindowOpen"] is not None
    assert result["contactByDate"] < result["predictedWindowOpen"]
    assert result["alertAtDate"] < result["contactByDate"]


def test_compute_dates_are_correctly_ordered_backwards_from_cash_out():
    result = cc.compute(
        {"roundSize": 50_000_000, "roundDate": "2026-01-01", "region": "Europe",
         "radarCategory": "B2B SaaS"},
        headcount=40, as_of=date(2026, 6, 1),
    )
    cash_out = date.fromisoformat(result["estCashOutDate"])
    window_open = date.fromisoformat(result["predictedWindowOpen"])
    contact_by = date.fromisoformat(result["contactByDate"])
    alert_at = date.fromisoformat(result["alertAtDate"])
    assert window_open < cash_out
    assert contact_by < window_open
    assert alert_at < contact_by


def test_compute_runway_floors_at_zero_capital_remaining():
    # Round long since exhausted at this burn rate -- capitalRemaining should
    # floor at 0, not go negative.
    result = cc.compute(
        {"roundSize": 1_000_000, "roundDate": "2020-01-01", "region": "NA",
         "radarCategory": "B2B SaaS"},
        headcount=50, as_of=date(2026, 8, 5),
    )
    assert result["runwayMonths"] == 0.0
