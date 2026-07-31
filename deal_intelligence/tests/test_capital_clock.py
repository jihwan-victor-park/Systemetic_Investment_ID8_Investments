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


def test_cost_per_head_override_wins_when_present():
    overrides = {"NA_medium": 300_000}
    assert cc.cost_per_head("NA", "medium", overrides) == 300_000


def test_cost_per_head_override_falls_back_for_an_unlisted_combo():
    overrides = {"NA_high": 500_000}  # doesn't cover NA_medium
    assert cc.cost_per_head("NA", "medium", overrides) == cc.COST_PER_HEAD[("NA", "medium")]


def test_cost_per_head_empty_overrides_uses_hardcoded_table():
    assert cc.cost_per_head("NA", "medium", {}) == cc.COST_PER_HEAD[("NA", "medium")]
    assert cc.cost_per_head("NA", "medium", None) == cc.COST_PER_HEAD[("NA", "medium")]


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


def test_compute_caps_runway_and_dates_for_an_outsized_round(): # Oscar, 2026-07-29 -- Atoms: $1.7B round / 690 heads computed a 2035 window
    result = cc.compute(
        {"roundSize": 1_700_000_000, "roundDate": "2026-07-23", "region": "NA",
         "radarCategory": "industrial automation"},
        headcount=690, as_of=date(2026, 7, 29),
    )
    assert result["runwayMonths"] == cc.MAX_RUNWAY_MONTHS
    window_open = date.fromisoformat(result["predictedWindowOpen"])
    # Capped runway (36mo) minus the 12mo window-open offset -> at most ~24
    # months out, nowhere near the ~112 months (9+ years) the raw, uncapped
    # arithmetic would have produced.
    assert (window_open - date(2026, 7, 29)).days < 900
    assert "capped" in result["assumptions"]


def test_compute_high_intensity_gets_a_tighter_runway_cap(): # Oscar, 2026-07-29 -- research-grounded, see MAX_RUNWAY_MONTHS_HIGH_INTENSITY's own comment
    result = cc.compute(
        {"roundSize": 400_000_000, "roundDate": "2026-06-01", "region": "NA",
         "radarCategory": "AI infrastructure", "description": "foundation model training"},
        headcount=120, as_of=date(2026, 7, 29),
    )
    assert result["capitalIntensity"] == "high"
    assert result["runwayMonths"] == cc.MAX_RUNWAY_MONTHS_HIGH_INTENSITY
    assert result["runwayMonths"] < cc.MAX_RUNWAY_MONTHS  # meaningfully tighter than the general cap
    assert "high capital-intensity" in result["assumptions"]


def test_compute_medium_intensity_still_uses_the_general_cap_not_the_tight_one():
    # Same outsized-round shape as the Atoms regression test, but classified
    # medium (no high-intensity keywords) -- must NOT get the tight cap.
    result = cc.compute(
        {"roundSize": 1_700_000_000, "roundDate": "2026-07-23", "region": "NA",
         "radarCategory": "industrial automation"},
        headcount=690, as_of=date(2026, 7, 29),
    )
    assert result["capitalIntensity"] == "medium"
    assert result["runwayMonths"] == cc.MAX_RUNWAY_MONTHS


def test_compute_does_not_mention_cap_when_runway_is_reasonable():
    result = cc.compute(
        {"roundSize": 32_000_000, "roundDate": "2026-02-10", "region": "NA"},
        headcount=81, as_of=date(2026, 8, 5),
    )
    assert "capped" not in result["assumptions"]


def test_cadence_window_open_is_tighter_for_hypergrowth_than_for_no_signal():
    round_date = date(2026, 1, 1)
    hyper = cc.cadence_window_open(round_date, "hypergrowth")
    strong = cc.cadence_window_open(round_date, "strong")
    none_tier = cc.cadence_window_open(round_date, None)
    assert hyper < strong < none_tier


def test_cadence_window_open_needs_a_round_date():
    assert cc.cadence_window_open(None, "hypergrowth") is None


def test_no_growth_signal_cadence_respects_the_lengthening_median(): # research: ~20mo trending 28, NOT compressed
    assert cc.CADENCE_MONTHS_BY_GROWTH[None] >= 20


def test_hypergrowth_cadence_pulls_the_window_in_ahead_of_runway():
    # Big round, small team -> runway model says "years from now". A
    # hypergrowth signal must override that: these companies raise on
    # strength long before cash runs low (Anthropic/Cyera/Cursor pattern).
    fields = {"roundSize": 200_000_000, "roundDate": "2026-06-01", "region": "NA",
              "radarCategory": "B2B software"}
    runway_only = cc.compute(fields, headcount=60, as_of=date(2026, 7, 29))
    hypergrowth = cc.compute(fields, headcount=60, as_of=date(2026, 7, 29), growth_tier="hypergrowth")
    assert hypergrowth["windowBasis"] == "cadence"
    assert hypergrowth["predictedWindowOpen"] < runway_only["predictedWindowOpen"]
    assert hypergrowth["growthTier"] == "hypergrowth"
    assert "raising on strength" in hypergrowth["assumptions"]


def test_unverified_hypergrowth_pulls_the_window_in_less_than_verified(): # 2026-07-29 -- the fix that closed the gap the Paper case exposed
    fields = {"roundSize": 200_000_000, "roundDate": "2026-06-01", "region": "NA",
              "radarCategory": "B2B software"}
    verified = cc.cadence_window_open(date(2026, 6, 1), "hypergrowth", growth_verified=True)
    unverified = cc.cadence_window_open(date(2026, 6, 1), "hypergrowth", growth_verified=False)
    no_signal = cc.cadence_window_open(date(2026, 6, 1), None)
    assert verified < unverified < no_signal  # unverified sits strictly between the two, not equal to either


def test_growth_verified_defaults_true_for_backward_compatibility():
    with_default = cc.cadence_window_open(date(2026, 6, 1), "hypergrowth")
    explicit_true = cc.cadence_window_open(date(2026, 6, 1), "hypergrowth", growth_verified=True)
    assert with_default == explicit_true


def test_unverified_flows_through_compute_end_to_end():
    fields = {"roundSize": 200_000_000, "roundDate": "2026-06-01", "region": "NA",
              "radarCategory": "B2B software"}
    verified = cc.compute(fields, headcount=60, as_of=date(2026, 7, 29), growth_tier="hypergrowth", growth_verified=True)
    unverified = cc.compute(fields, headcount=60, as_of=date(2026, 7, 29), growth_tier="hypergrowth", growth_verified=False)
    assert unverified["predictedWindowOpen"] > verified["predictedWindowOpen"]


def test_growth_verified_is_irrelevant_with_no_growth_tier():
    # growth_verified only means something alongside an actual tier -- with
    # growth_tier=None there's nothing to discount.
    with_true = cc.cadence_window_open(date(2026, 6, 1), None, growth_verified=True)
    with_false = cc.cadence_window_open(date(2026, 6, 1), None, growth_verified=False)
    assert with_true == with_false


def test_quiet_company_keeps_the_runway_answer_unchanged():
    # No growth signal + a short runway -> the runway model should still win,
    # so this change can't silently pull every window earlier.
    fields = {"roundSize": 10_000_000, "roundDate": "2026-01-01", "region": "NA"}
    result = cc.compute(fields, headcount=40, as_of=date(2026, 7, 29))
    assert result["windowBasis"] == "runway"


def test_both_window_estimates_are_reported_for_transparency():
    result = cc.compute(
        {"roundSize": 50_000_000, "roundDate": "2026-01-01", "region": "NA"},
        headcount=40, as_of=date(2026, 6, 1), growth_tier="strong",
    )
    assert result["runwayWindowOpen"] is not None
    assert result["cadenceWindowOpen"] is not None
    assert result["windowBasis"] in ("runway", "cadence")


def test_missing_headcount_still_gets_a_cadence_window(): # was a blank "—" in the hub before 2026-07-29
    result = cc.compute(
        {"roundSize": 30_000_000, "roundDate": "2026-03-01", "region": "NA"},
        headcount=None, as_of=date(2026, 7, 29), growth_tier="hypergrowth",
    )
    assert result["predictedWindowOpen"] is not None
    assert result["windowBasis"] == "cadence"
    assert result["runwayMonths"] is None  # still honestly reports no burn estimate


def test_missing_round_date_and_headcount_still_returns_no_window():
    result = cc.compute({"roundSize": 30_000_000, "roundDate": None, "region": "NA"},
                        headcount=None, as_of=date(2026, 7, 29))
    assert result["predictedWindowOpen"] is None


def test_compute_runway_floors_at_zero_capital_remaining():
    # Round long since exhausted at this burn rate -- capitalRemaining should
    # floor at 0, not go negative.
    result = cc.compute(
        {"roundSize": 1_000_000, "roundDate": "2020-01-01", "region": "NA",
         "radarCategory": "B2B SaaS"},
        headcount=50, as_of=date(2026, 8, 5),
    )
    assert result["runwayMonths"] == 0.0
