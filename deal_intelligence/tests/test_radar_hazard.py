"""Unit tests for radar_hazard.py's pure kernel/peak-decay math -- no
network, no Firestore; everything here runs instantly. Mirrors
RADAR_SIGNAL_ENGINE.md §4's worked reasoning (peak-effect delay, not decay;
composite cap; two-family guardrail)."""
from deal_intelligence import radar_hazard as rh


def test_baseline_hazard_none_uses_unscored_base_rate():
    assert rh.baseline_hazard(None) == 0.20


def test_baseline_hazard_rises_as_window_approaches():
    far = rh.baseline_hazard(18)
    mid = rh.baseline_hazard(6)
    critical = rh.baseline_hazard(2)
    overdue = rh.baseline_hazard(-3)
    assert far < mid < critical < overdue


def test_signal_multiplier_at_t0_below_peak_month_is_baseline():
    kernel = rh.SIGNAL_KERNELS["senior_finance_role"]
    assert rh.signal_multiplier(kernel, 0) == 1.0


def test_signal_multiplier_rises_to_peak_at_peak_month(): # the "more predictive 4 months later, not the week it happens" claim
    kernel = rh.SIGNAL_KERNELS["senior_finance_role"]
    at_peak = rh.signal_multiplier(kernel, 4)
    at_week_one = rh.signal_multiplier(kernel, 0.25)
    assert at_peak == kernel["peak_mult"]
    assert at_peak > at_week_one


def test_signal_multiplier_fades_back_to_baseline_by_fade_month():
    kernel = rh.SIGNAL_KERNELS["corp_dev_role"]  # peak 2mo, fades by 6mo
    assert rh.signal_multiplier(kernel, 6) == 1.0
    assert rh.signal_multiplier(kernel, 10) == 1.0  # stays at baseline past fade, doesn't go negative/undefined


def test_signal_multiplier_immediate_peak_month_zero_signal():
    kernel = rh.SIGNAL_KERNELS["headcount_growth_40"]  # concurrent, peak_month 0
    assert rh.signal_multiplier(kernel, 0) == kernel["peak_mult"]


def test_signal_multiplier_none_age_never_detected_is_no_effect():
    kernel = rh.SIGNAL_KERNELS["senior_finance_role"]
    assert rh.signal_multiplier(kernel, None) == 1.0


def test_negative_signal_pulls_composite_below_one():
    kernel = rh.SIGNAL_KERNELS["headcount_decline_10"]
    assert rh.signal_multiplier(kernel, 0) < 1.0


def test_combine_multipliers_is_a_product():
    assert rh.combine_multipliers([2.0, 1.5]) == 3.0


def test_combine_multipliers_caps_at_composite_cap():
    assert rh.combine_multipliers([2.5, 2.2, 1.6, 1.4]) == rh.COMPOSITE_CAP


def test_combine_multipliers_empty_is_one():
    assert rh.combine_multipliers([]) == 1.0


def test_hazard_p180_greater_than_p90_same_inputs(): # longer horizon, same rate -> higher probability
    p90 = rh.hazard_p90(0.5, 2.0)
    p180 = rh.hazard_p180(0.5, 2.0)
    assert p180 > p90


def test_hazard_zero_multiplier_and_zero_h0_is_zero():
    assert rh.hazard_p90(0.0, 1.0) == 0.0


def test_heat_points_rescales_p180_to_0_100():
    assert rh.heat_points(0.5) == 50.0
    assert rh.heat_points(0.0) == 0.0


def test_two_family_guardrail_requires_two_distinct_families():
    assert rh.two_family_guardrail(["F2", "F2", "F2"]) is False
    assert rh.two_family_guardrail(["F2", "negative"]) is True
    assert rh.two_family_guardrail([]) is False


def test_confidence_level_no_signals_is_low():
    assert rh.confidence_level([], None) == "low"


def test_confidence_level_two_families_is_high():
    assert rh.confidence_level(["F2", "negative"], 1) == "high"


def test_confidence_level_one_fresh_family_is_medium():
    assert rh.confidence_level(["F2"], 2) == "medium"


def test_confidence_level_one_stale_family_is_low():
    assert rh.confidence_level(["F2"], 9) == "low"


def test_compute_pipeline_no_active_signals_is_baseline_only():
    result = rh.compute(0.5, [])
    assert result["compositeMultiplier"] == 1.0
    assert result["familiesActive"] == []
    assert result["twoFamilyPass"] is False
    assert result["confidence"] == "low"
    assert 0 < result["p90"] < result["p180"] < 1


def test_compute_pipeline_single_f2_signal_at_peak_scores_higher_than_no_signal():
    baseline = rh.compute(0.5, [])
    with_signal = rh.compute(0.5, [{"key": "senior_finance_role", "monthsSinceEvent": 4}])
    assert with_signal["p180"] > baseline["p180"]
    assert with_signal["twoFamilyPass"] is False  # still only F2 -- matches this pass's known limitation


def test_two_family_guardrail_is_now_actually_reachable(): # 2026-07-29 -- was inert while every signal was F2
    # F3 (growth, from the Stage 1 screen) + F2 (hiring) are distinct
    # families, so a company with both finally passes the guardrail §4.2
    # designed as the main defense against one noisy sensor.
    result = rh.compute(0.5, [
        {"key": "hypergrowth_revenue", "monthsSinceEvent": 2},
        {"key": "senior_finance_role", "monthsSinceEvent": 4},
    ])
    assert result["twoFamilyPass"] is True
    assert set(result["familiesActive"]) == {"F2", "F3"}
    assert result["confidence"] == "high"


def test_hypergrowth_outweighs_a_single_hiring_signal():
    # The research point in code form: for the AI tier, revenue momentum is
    # stronger timing evidence than hiring preparation.
    growth = rh.compute(0.5, [{"key": "hypergrowth_revenue", "monthsSinceEvent": 2}])
    hiring = rh.compute(0.5, [{"key": "senior_gtm_burst", "monthsSinceEvent": 3}])
    assert growth["p180"] > hiring["p180"]


def test_process_visible_is_the_strongest_single_signal():
    # F4 process leakage -- "very high" precision, 0-3mo lead (§2's table).
    process = rh.compute(0.5, [{"key": "process_visible", "monthsSinceEvent": 0}])
    growth = rh.compute(0.5, [{"key": "hypergrowth_revenue", "monthsSinceEvent": 2}])
    assert process["p180"] > growth["p180"]


def test_process_visible_fades_fast():
    kernel = rh.SIGNAL_KERNELS["process_visible"]
    assert rh.signal_multiplier(kernel, 0) == kernel["peak_mult"]
    assert rh.signal_multiplier(kernel, 6) == 1.0  # worthless half a year later


def test_distress_flag_set_by_a_defensive_raise():
    result = rh.compute(0.5, [{"key": "defensive_raise", "monthsSinceEvent": 0}])
    assert result["distressFlag"] is True
    assert "defensive_raise" in result["distressSignals"]


def test_distress_flag_absent_on_a_healthy_company():
    result = rh.compute(0.5, [{"key": "hypergrowth_revenue", "monthsSinceEvent": 2}])
    assert result["distressFlag"] is False
    assert result["distressSignals"] == []


def test_distress_flag_survives_alongside_positive_signals():
    # §2.2: a growing-but-defensive company must still be flagged, not
    # laundered clean by its positive signals.
    result = rh.compute(0.5, [
        {"key": "hypergrowth_revenue", "monthsSinceEvent": 2},
        {"key": "layoffs", "monthsSinceEvent": 1},
    ])
    assert result["distressFlag"] is True


def test_compute_pipeline_heat_points_present_and_matches_p180():
    result = rh.compute(0.5, [{"key": "senior_finance_role", "monthsSinceEvent": 4}])
    assert result["heatPoints"] == rh.heat_points(result["p180"])


# ── Data coverage (Isabella, 2026-07-30) ──────────────────────────────────
# "Don't automatically penalize a company because it is absent from Sacra or
# a coverage database... treat unavailable data as missing, not zero...
# require a minimum data-coverage threshold... display a confidence score
# beside the heat score."

def test_data_coverage_full_when_all_sources_available():
    result = rh.data_coverage({"capitalClock": True, "jobSignals": True, "screen": True})
    assert result["coverage"] == 1.0
    assert result["missing"] == []
    assert set(result["available"]) == {"capitalClock", "jobSignals", "screen"}


def test_data_coverage_zero_when_nothing_available():
    result = rh.data_coverage({})
    assert result["coverage"] == 0.0
    assert set(result["missing"]) == {"capitalClock", "jobSignals", "screen"}
    assert result["available"] == []


def test_data_coverage_partial_reports_which_source_is_missing():
    result = rh.data_coverage({"capitalClock": True, "jobSignals": False, "screen": True})
    assert result["coverage"] == round(2 / 3, 3)
    assert result["missing"] == ["jobSignals"]


def test_confidence_level_defaults_to_full_coverage_unchanged_behavior():
    # No `coverage` arg passed -- every caller written before 2026-07-30
    # keeps today's behavior exactly, this is the regression pin.
    assert rh.confidence_level(["F2", "negative"], 1) == "high"


def test_confidence_level_capped_low_below_min_coverage_even_with_two_families():
    # Isabella's mandate #4: thin coverage must not be laundered into
    # "high" confidence just because the one or two sources that DID
    # return data happen to look great.
    thin_coverage = round(1 / 3, 3)  # one of three sources checked
    assert rh.confidence_level(["F2", "negative"], 1, coverage=thin_coverage) == "low"


def test_confidence_level_not_capped_at_two_of_three_sources():
    two_of_three = round(2 / 3, 3)
    assert rh.confidence_level(["F2", "negative"], 1, coverage=two_of_three) == "high"


def test_compute_defaults_to_full_coverage_when_data_sources_omitted():
    # No data_sources arg -- every pre-2026-07-30 test call site (including
    # every test above this one in this file) must see identical behavior.
    result = rh.compute(0.5, [
        {"key": "hypergrowth_revenue", "monthsSinceEvent": 2},
        {"key": "senior_finance_role", "monthsSinceEvent": 4},
    ])
    assert result["dataCoverage"] == 1.0
    assert result["confidence"] == "high"


def test_compute_reports_missing_sources_without_zeroing_the_score():
    # A company absent from every wired source except headcount/round data
    # (no ATS found, no Stage 1 screen yet) still gets its real hazard
    # score computed off the capital clock alone -- heatPoints is NOT forced
    # to 0 or otherwise penalized for the missing sources; only confidence
    # reflects the thin footprint.
    thin = rh.compute(0.5, [], data_sources={"capitalClock": True, "jobSignals": False, "screen": False})
    full = rh.compute(0.5, [], data_sources={"capitalClock": True, "jobSignals": True, "screen": True})
    assert thin["p180"] == full["p180"]  # identical score -- same h0, same (empty) active signals
    assert thin["heatPoints"] == full["heatPoints"]
    assert thin["dataCoverage"] == round(1 / 3, 3)
    assert thin["dataSourcesMissing"] == ["jobSignals", "screen"]
    assert full["dataCoverage"] == 1.0


def test_compute_low_coverage_caps_confidence_even_with_active_signals():
    # Two active families would normally read "high" (see the two-family
    # test above) -- but if only one of the three sources was ever checked,
    # confidence must not overstate how well-observed this company is.
    result = rh.compute(0.5, [
        {"key": "hypergrowth_revenue", "monthsSinceEvent": 2},
        {"key": "senior_finance_role", "monthsSinceEvent": 4},
    ], data_sources={"capitalClock": False, "jobSignals": True, "screen": False})
    assert result["twoFamilyPass"] is True  # the signal-family read is unaffected...
    assert result["confidence"] == "low"    # ...but confidence reflects the thin footprint
    assert result["dataCoverage"] == round(1 / 3, 3)
