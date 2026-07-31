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
