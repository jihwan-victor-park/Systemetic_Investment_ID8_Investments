"""Unit tests for radar_market_heat.py's pure scoring functions -- fabricated
inputs, no Firestore/network I/O, same convention as test_radar_hazard.py /
test_capital_clock.py."""
from datetime import date

from deal_intelligence import radar_market_heat as rmh


def test_weights_sum_to_100():
    assert abs(sum(rmh.WEIGHTS.values()) - 100) < 1e-9


# ── raise_probability (#1+#2 -> #3) ─────────────────────────────────────

def test_raise_probability_high_band_scores_10():
    raw, band, _ = rmh.raise_probability("Series B", "2023-01-01", as_of=date(2026, 8, 5))
    assert band == "high"
    assert raw == 10.0


def test_raise_probability_low_band_scores_0():
    raw, band, _ = rmh.raise_probability("Series B", "2026-07-01", as_of=date(2026, 8, 5))
    assert band == "low"
    assert raw == 0.0


def test_raise_probability_medium_band_scores_5():
    # ~20mo since a Series B close sits inside the 18-24mo pre-C cadence window.
    raw, band, _ = rmh.raise_probability("Series B", "2024-12-01", as_of=date(2026, 8, 5))
    assert band == "medium"
    assert raw == 5.0


def test_raise_probability_no_round_date_is_none_not_a_fabricated_medium():
    raw, band, context = rmh.raise_probability("Series B", None, as_of=date(2026, 8, 5))
    assert raw is None
    assert band is None
    assert "no" in context.lower()


# ── mom_employee_growth (#5) ────────────────────────────────────────────

def test_mom_employee_growth_bands():
    assert rmh.mom_employee_growth(0.08) == 10.0   # >5%
    assert rmh.mom_employee_growth(0.03) == 7.0    # 2-5%
    assert rmh.mom_employee_growth(0.01) == 5.0    # 0-2%
    assert rmh.mom_employee_growth(0.0) == 5.0
    assert rmh.mom_employee_growth(-0.02) == 0.0   # declining


def test_mom_employee_growth_none_rate_is_none_not_zero():
    assert rmh.mom_employee_growth(None) is None


def test_mom_employee_growth_boundary_at_5pct_is_the_7_band():
    # rubric: 10 = >5% MoM -- exactly 5% falls into the 2-5% band, not the top one.
    assert rmh.mom_employee_growth(0.05) == 7.0


# ── job_posting_velocity (#6) ───────────────────────────────────────────

def test_job_posting_velocity_zero_open_roles_scores_0_regardless_of_rate():
    assert rmh.job_posting_velocity(0.9, 0) == 0.0
    assert rmh.job_posting_velocity(None, 0) == 0.0


def test_job_posting_velocity_bands():
    assert rmh.job_posting_velocity(0.30, 12) == 10.0   # >25%
    assert rmh.job_posting_velocity(0.15, 12) == 7.0    # 10-25%
    assert rmh.job_posting_velocity(0.0, 12) == 5.0     # flat +-10%
    assert rmh.job_posting_velocity(-0.05, 12) == 5.0   # still inside the flat band
    assert rmh.job_posting_velocity(-0.30, 12) == 3.0   # declining


def test_job_posting_velocity_no_rate_yet_but_roles_exist_is_none():
    assert rmh.job_posting_velocity(None, 12) is None


# ── tier1_investor_count (#16) ───────────────────────────────────────────

def test_tier1_investor_count_bands():
    assert rmh.tier1_investor_count(["Sequoia", "Index", "a16z"]) == (10.0, 3)
    assert rmh.tier1_investor_count(["Sequoia", "Index"]) == (7.0, 2)
    assert rmh.tier1_investor_count(["Sequoia"]) == (4.0, 1)
    assert rmh.tier1_investor_count([]) == (0.0, 0)
    assert rmh.tier1_investor_count(None) == (0.0, 0)


# ── compute() orchestration ─────────────────────────────────────────────

def test_compute_only_wired_signals_are_computed():
    result = rmh.compute(
        {"series": "Series B", "roundDate": "2026-07-01", "tier1Firms": ["Sequoia", "Index"]},
        {"headcountMomRate": 0.06, "openRolesMomRate": 0.20, "currentOpenRoles": 9},
        as_of=date(2026, 8, 5),
    )
    for key in ("raiseProbability", "momEmployeeGrowth", "jobPostingVelocity", "tier1InvestorCount"):
        assert result["signals"][key]["computed"] is True
    for key in result["notComputed"]:
        assert result["signals"][key]["computed"] is False
    assert set(result["notComputed"]) == set(rmh.WEIGHTS) - rmh._WIRED


def test_compute_points_available_matches_wired_weights():
    result = rmh.compute(
        {"series": "Series B", "roundDate": "2026-07-01", "tier1Firms": ["Sequoia", "Index"]},
        {"headcountMomRate": 0.06, "openRolesMomRate": 0.20, "currentOpenRoles": 9},
        as_of=date(2026, 8, 5),
    )
    expected = sum(rmh.WEIGHTS[k] for k in rmh._WIRED)
    assert result["pointsAvailable"] == expected


def test_compute_score_never_a_fabricated_number_when_nothing_computable():
    # No round date, no rates, no tier1 firms at all -- every wired signal
    # legitimately returns None too (raise_probability has nothing to
    # anchor to, tier1_investor_count degrades to a real 0, not None).
    result = rmh.compute(
        {"series": "Series B", "roundDate": None, "tier1Firms": []},
        {"headcountMomRate": None, "openRolesMomRate": None, "currentOpenRoles": None},
        as_of=date(2026, 8, 5),
    )
    # tier1InvestorCount still computes (0 firms is a real, valid 0) --
    # score/normalizedScore reflect that rather than reading as "nothing at all."
    assert result["signals"]["tier1InvestorCount"]["computed"] is True
    assert result["pointsAvailable"] == rmh.WEIGHTS["tier1InvestorCount"]
    assert result["score"] == 0.0
    assert result["normalizedScore"] == 0.0


def test_compute_normalized_score_rescales_to_points_available():
    # Only tier1 (weight 10) and raiseProbability (weight 15) computable,
    # both landing at their top band -- raw contribution = 25/100, but
    # normalized to the 25 points actually measured, it's a perfect 100.
    result = rmh.compute(
        {"series": "Series B", "roundDate": "2023-01-01", "tier1Firms": ["Sequoia", "Index", "a16z"]},
        {"headcountMomRate": None, "openRolesMomRate": None, "currentOpenRoles": None},
        as_of=date(2026, 8, 5),
    )
    assert result["score"] == 25.0
    assert result["normalizedScore"] == 100.0
    assert result["pointsAvailable"] == 25


# ── industry_growth / google_trends_search_interest (#4, #11) ──────────

def test_industry_growth_bands():
    assert rmh.industry_growth({"pctChange": 30}) == 10.0    # >25%
    assert rmh.industry_growth({"pctChange": 15}) == 7.0     # 10-25%
    assert rmh.industry_growth({"pctChange": 0}) == 5.0      # flat +-10%
    assert rmh.industry_growth({"pctChange": -25}) == 0.0    # down >10%


def test_industry_growth_missing_trends_read_is_none():
    assert rmh.industry_growth(None) is None
    assert rmh.industry_growth({"pctChange": None}) is None


def test_google_trends_search_interest_same_bucket_scale():
    assert rmh.google_trends_search_interest({"pctChange": 30}) == 10.0
    assert rmh.google_trends_search_interest(None) is None


# ── news_volume / step_up / website_visits_growth (#9, #7, #10) ────────

def test_news_volume_bands():
    assert rmh.news_volume("high") == 10.0
    assert rmh.news_volume("steady") == 5.0
    assert rmh.news_volume("low") == 0.0
    assert rmh.news_volume(None) is None


def test_step_up_bands_never_maxed():
    assert rmh.step_up("up") == 8.0   # short of 10 -- categorical, not a confirmed multiple
    assert rmh.step_up("flat") == 4.0
    assert rmh.step_up("down") == 1.0
    assert rmh.step_up(None) is None


def test_website_visits_growth_bands():
    assert rmh.website_visits_growth("rising") == 7.0
    assert rmh.website_visits_growth("flat") == 4.0
    assert rmh.website_visits_growth("declining") == 0.0
    assert rmh.website_visits_growth(None) is None


# ── crunchbase_proxy (shared by 3 rows) / yoy_revenue_growth (#8) ──────

def test_crunchbase_proxy_bands():
    assert rmh.crunchbase_proxy("strong") == 10.0
    assert rmh.crunchbase_proxy("moderate") == 5.0
    assert rmh.crunchbase_proxy("weak") == 0.0
    assert rmh.crunchbase_proxy(None) is None


def test_yoy_revenue_growth_bands():
    assert rmh.yoy_revenue_growth("hypergrowth") == 10.0
    assert rmh.yoy_revenue_growth("strong") == 7.0
    assert rmh.yoy_revenue_growth(None) is None
    assert rmh.yoy_revenue_growth("weak") is None  # no such tier -- missing, not a fabricated 0


# ── timing_urgency_multiplier ───────────────────────────────────────────

def test_timing_urgency_multiplier_neutral_when_no_estimate_or_far_out():
    assert rmh.timing_urgency_multiplier(None) == 1.0
    assert rmh.timing_urgency_multiplier(12) == 1.0
    assert rmh.timing_urgency_multiplier(24) == 1.0


def test_timing_urgency_multiplier_maxes_at_window_open():
    assert rmh.timing_urgency_multiplier(0) == rmh.MAX_URGENCY_BOOST


def test_timing_urgency_multiplier_holds_flat_past_the_window():
    assert rmh.timing_urgency_multiplier(-1) == rmh.MAX_URGENCY_BOOST
    assert rmh.timing_urgency_multiplier(-12) == rmh.MAX_URGENCY_BOOST


def test_timing_urgency_multiplier_ramps_linearly_between_12_and_0():
    assert rmh.timing_urgency_multiplier(6) == round(1.0 + (rmh.MAX_URGENCY_BOOST - 1.0) * 0.5, 4)


# ── compute() with the new signals wired ────────────────────────────────

def test_compute_new_signals_stay_unwired_when_no_new_inputs_supplied():
    # Every pre-2026-08-05 caller keeps IDENTICAL behavior -- market_research/
    # trends/growth_tier/months_until_window/round_announced all default to
    # values that are no-ops.
    result = rmh.compute(
        {"series": "Series B", "roundDate": "2026-07-01", "tier1Firms": ["Sequoia", "Index"]},
        {"headcountMomRate": 0.06, "openRolesMomRate": 0.20, "currentOpenRoles": 9},
        as_of=date(2026, 8, 5),
    )
    for key in ("industryGrowth", "googleTrendsSearchInterest", "newsVolume", "stepUp",
                "websiteVisitsGrowth", "crunchbaseGrowthScore", "crunchbaseHeatScore",
                "crunchbaseSurgeScore", "yoyRevenueGrowth"):
        assert result["signals"][key]["computed"] is False
    assert result["timingUrgencyMultiplier"] == 1.0
    assert result["roundAnnouncedFlag"] is False


def test_compute_wires_new_signals_when_inputs_supplied():
    result = rmh.compute(
        {"series": "Series B", "roundDate": "2026-07-01", "tier1Firms": ["Sequoia", "Index"]},
        {"headcountMomRate": 0.06, "openRolesMomRate": 0.20, "currentOpenRoles": 9},
        as_of=date(2026, 8, 5),
        market_research={"newsVolume": "high", "valuationStepUp": "up",
                          "websiteTrafficTrend": "rising", "publicMomentum": "strong"},
        trends={"industry": {"pctChange": 30}, "company": {"pctChange": 15}},
        growth_tier="hypergrowth",
    )
    assert result["signals"]["newsVolume"]["raw"] == 10.0
    assert result["signals"]["stepUp"]["raw"] == 8.0
    assert result["signals"]["websiteVisitsGrowth"]["raw"] == 7.0
    assert result["signals"]["industryGrowth"]["raw"] == 10.0
    assert result["signals"]["googleTrendsSearchInterest"]["raw"] == 7.0
    assert result["signals"]["yoyRevenueGrowth"]["raw"] == 10.0
    # All 3 Crunchbase-branded rows share the SAME proxy read, and all carry
    # a proxyNote so nobody mistakes it for Crunchbase's own number.
    for key in ("crunchbaseGrowthScore", "crunchbaseHeatScore", "crunchbaseSurgeScore"):
        assert result["signals"][key]["raw"] == 10.0
        assert "not Crunchbase" in result["signals"][key]["proxyNote"]


def test_compute_urgency_boosts_score_as_window_approaches():
    kwargs = dict(
        fields={"series": "Series B", "roundDate": "2026-07-01", "tier1Firms": ["Sequoia", "Index", "a16z"]},
        rates={"headcountMomRate": None, "openRolesMomRate": None, "currentOpenRoles": None},
        as_of=date(2026, 8, 5),
    )
    far = rmh.compute(**kwargs, months_until_window=12)
    near = rmh.compute(**kwargs, months_until_window=0)
    assert far["score"] == 10.0  # tier1InvestorCount alone, urgency neutral at >=12mo
    assert near["score"] == round(10.0 * rmh.MAX_URGENCY_BOOST, 1)
    assert near["score"] > far["score"]


def test_compute_score_never_exceeds_100_even_at_max_rubric_and_max_urgency():
    result = rmh.compute(
        {"series": "Series B", "roundDate": "2023-01-01", "tier1Firms": ["Sequoia", "Index", "a16z"]},
        {"headcountMomRate": 0.10, "openRolesMomRate": 0.30, "currentOpenRoles": 20},
        as_of=date(2026, 8, 5),
        market_research={"newsVolume": "high", "valuationStepUp": "up",
                          "websiteTrafficTrend": "rising", "publicMomentum": "strong"},
        trends={"industry": {"pctChange": 30}, "company": {"pctChange": 30}},
        growth_tier="hypergrowth",
        months_until_window=0,
    )
    assert result["score"] <= 100
    assert result["normalizedScore"] <= 100


def test_compute_round_announced_caps_score_and_sets_flag():
    result = rmh.compute(
        {"series": "Series B", "roundDate": "2023-01-01", "tier1Firms": ["Sequoia", "Index", "a16z"]},
        {"headcountMomRate": 0.10, "openRolesMomRate": 0.30, "currentOpenRoles": 20},
        as_of=date(2026, 8, 5),
        market_research={"newsVolume": "high", "publicMomentum": "strong"},
        months_until_window=0,
        round_announced=True,
    )
    assert result["roundAnnouncedFlag"] is True
    assert result["score"] <= rmh.ROUND_ANNOUNCED_CEILING
    assert result["normalizedScore"] <= rmh.ROUND_ANNOUNCED_CEILING
    # The underlying breakdown stays fully inspectable -- suppression caps
    # the headline number, it doesn't hide the evidence.
    assert result["signals"]["newsVolume"]["raw"] == 10.0


def test_compute_signal_entries_carry_weight_and_contribution():
    result = rmh.compute(
        {"series": "Series B", "roundDate": "2026-07-01", "tier1Firms": ["Sequoia"]},
        {"headcountMomRate": None, "openRolesMomRate": None, "currentOpenRoles": None},
        as_of=date(2026, 8, 5),
    )
    tier1_entry = result["signals"]["tier1InvestorCount"]
    assert tier1_entry["weight"] == 10
    assert tier1_entry["raw"] == 4.0
    assert tier1_entry["contribution"] == 4.0  # 4/10 * 10
    unwired_entry = result["signals"]["crunchbaseHeatScore"]
    assert unwired_entry["computed"] is False
    assert unwired_entry["raw"] is None
    assert unwired_entry["contribution"] is None
    assert unwired_entry["weight"] == rmh.WEIGHTS["crunchbaseHeatScore"]
