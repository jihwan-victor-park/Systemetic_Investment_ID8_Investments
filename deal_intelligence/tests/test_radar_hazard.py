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


def test_compute_pipeline_heat_points_present_and_matches_p180():
    result = rh.compute(0.5, [{"key": "senior_finance_role", "monthsSinceEvent": 4}])
    assert result["heatPoints"] == rh.heat_points(result["p180"])
