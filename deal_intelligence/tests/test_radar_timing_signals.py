"""Unit tests for radar_timing_signals.py -- the fit-screen -> timing-signal
bridge. Fabricated screen dicts, zero mocking, no I/O."""
from deal_intelligence import radar_timing_signals as rts


# ── Growth extraction from findings TEXT ─────────────────────────────────
# The whole reason this module exists: the fit rubric scores undisclosed
# hypergrowth as a 2 ("no usable figure"), so the score is the WRONG input
# and the text is the right one. These tests pin that behavior.

def test_extracts_hypergrowth_from_an_arr_multiple(): # the real Paper case, 2026-07-29
    tier, evidence = rts.extract_growth_tier(["ARR grew 25x post-Desktop launch; no $ figure."])
    assert tier == "hypergrowth"
    assert evidence  # must return WHY, not just the verdict


def test_extracts_hypergrowth_from_a_large_arr_dollar_figure():
    tier, _ = rts.extract_growth_tier(["$100M ARR disclosed, from $0 in ~9 months."])
    assert tier == "hypergrowth"


def test_extracts_strong_from_a_mid_arr_figure():
    tier, _ = rts.extract_growth_tier(["[ESTIMATED] ~$30M ARR via headcount triangulation."])
    assert tier == "strong"


def test_extracts_hypergrowth_from_a_high_percent_growth():
    tier, _ = rts.extract_growth_tier(["Revenue up 140% YoY per press coverage."])
    assert tier == "hypergrowth"


def test_extracts_strong_from_a_moderate_percent_growth():
    tier, _ = rts.extract_growth_tier(["Roughly 80% YoY growth reported."])
    assert tier == "strong"


def test_small_multiple_is_not_hypergrowth():
    # "2x" is below HYPERGROWTH_MULTIPLE -- must not trip the top tier.
    tier, _ = rts.extract_growth_tier(["Valuation up 2x from the bridge round."])
    assert tier != "hypergrowth"


def test_no_growth_evidence_returns_none_not_weak():
    # RADAR_SIGNAL_ENGINE.md §4.3: absence of signal is not evidence of
    # absence. Must be None (no contribution), never a negative signal.
    tier, evidence = rts.extract_growth_tier(["NDR not disclosed; no usable estimate found."])
    assert tier is None
    assert evidence == []


def test_extract_growth_tier_tolerates_empty_and_none_entries():
    tier, _ = rts.extract_growth_tier([None, "", "nothing quantitative here"])
    assert tier is None


def test_hypergrowth_wins_over_strong_when_both_present():
    tier, _ = rts.extract_growth_tier(["~$30M ARR estimated", "ARR grew 25x last year"])
    assert tier == "hypergrowth"


# ── Timing-bearing subcategory mapping ───────────────────────────────────

def _screen(sub_key, score, dim_key="lead_round_dynamics", finding="", **kw):
    base = {
        "date": "2026-07-29",
        "dimensions": [{"key": dim_key, "evidence": "", "subcategories": [
            {"key": sub_key, "score": score, "finding": finding},
        ]}],
        "rationale": "",
    }
    base.update(kw)
    return base


def test_timing_motivation_top_anchor_fires_process_visible():
    result = rts.extract(_screen("timing_motivation", 4))
    assert {"key": "process_visible", "monthsSinceEvent": 0} in result["signals"]


def test_timing_motivation_bottom_anchor_fires_defensive_raise_distress():
    result = rts.extract(_screen("timing_motivation", 1))
    assert {"key": "defensive_raise", "monthsSinceEvent": 0} in result["signals"]


def test_timing_motivation_mid_score_fires_nothing():
    result = rts.extract(_screen("timing_motivation", 3))
    assert result["signals"] == []


def test_institutional_momentum_top_anchor_fires_insiders_following():
    result = rts.extract(_screen("institutional_momentum", 4))
    assert {"key": "insiders_following", "monthsSinceEvent": 0} in result["signals"]


def test_non_timing_subcategory_is_ignored_entirely():
    # `moat_durability` is a fit concern with no timing meaning -- a 4 there
    # must not manufacture a timing signal.
    result = rts.extract(_screen("moat_durability", 4, dim_key="fundamentals"))
    assert result["signals"] == []


def test_months_since_screen_becomes_the_kernel_age():
    result = rts.extract(_screen("timing_motivation", 4), months_since_screen=5.0)
    assert result["signals"][0]["monthsSinceEvent"] == 5.0


def test_growth_signal_is_added_from_subcategory_finding_text():
    result = rts.extract(_screen("revenue_growth", 2, dim_key="fundamentals",
                                  finding="ARR grew 25x post-launch"))
    # score 2 (the rubric's "no data" anchor) but the TEXT says 25x --
    # exactly the inversion this module exists to correct.
    assert result["growthTier"] == "hypergrowth"
    assert {"key": "hypergrowth_revenue", "monthsSinceEvent": 0} in result["signals"]


def test_low_confidence_screen_gets_the_discounted_growth_kernel():
    screen = _screen("revenue_growth", 2, dim_key="fundamentals",
                      finding="ARR grew 25x post-launch", confidence="low")
    result = rts.extract(screen)
    assert result["growthTier"] == "hypergrowth"  # the READ is still hypergrowth
    assert result["growthVerified"] is False       # but flagged unverified
    assert {"key": "hypergrowth_revenue_unverified", "monthsSinceEvent": 0} in result["signals"]
    assert {"key": "hypergrowth_revenue", "monthsSinceEvent": 0} not in result["signals"]


def test_medium_or_high_confidence_gets_the_full_strength_kernel():
    for level in ("medium", "high"):
        screen = _screen("revenue_growth", 2, dim_key="fundamentals",
                          finding="ARR grew 25x post-launch", confidence=level)
        result = rts.extract(screen)
        assert result["growthVerified"] is True
        assert {"key": "hypergrowth_revenue", "monthsSinceEvent": 0} in result["signals"]


def test_missing_confidence_field_defaults_to_verified_not_distrusted():
    # A legacy screen with no confidence field at all shouldn't be silently
    # discounted -- only an EXPLICIT "low" triggers the weaker kernel.
    result = rts.extract(_screen("revenue_growth", 2, dim_key="fundamentals", finding="ARR grew 25x"))
    assert result["growthVerified"] is True


def test_strong_tier_also_gets_discounted_on_low_confidence():
    screen = _screen("revenue_growth", 3, dim_key="fundamentals",
                      finding="[ESTIMATED] ~$30M ARR", confidence="low")
    result = rts.extract(screen)
    assert {"key": "strong_revenue_growth_unverified", "monthsSinceEvent": 0} in result["signals"]


def test_growth_signal_read_from_the_deal_level_rationale_too():
    screen = _screen("moat_durability", 3, dim_key="fundamentals",
                      rationale="Company reports $80M ARR growing fast.")
    result = rts.extract(screen)
    assert result["growthTier"] == "hypergrowth"


def test_extract_with_no_screen_is_empty_not_an_error():
    result = rts.extract(None)
    assert result == {"signals": [], "growthTier": None, "growthVerified": False, "growthEvidence": [], "sourceScreenDate": None}


def test_extract_tolerates_a_legacy_screen_with_no_subcategories():
    result = rts.extract({"date": "2025-01-01", "dimensions": [{"key": "fundamentals"}]})
    assert result["signals"] == []
    assert result["sourceScreenDate"] == "2025-01-01"


def test_source_screen_date_is_carried_for_provenance():
    result = rts.extract(_screen("timing_motivation", 4))
    assert result["sourceScreenDate"] == "2026-07-29"


def test_growth_evidence_is_capped_to_three_entries():
    texts = [f"ARR grew {n}x this year" for n in range(10, 20)]
    screen = {
        "date": "2026-07-29",
        "dimensions": [{"key": "fundamentals", "evidence": "", "subcategories": [
            {"key": "revenue_growth", "score": 2, "finding": t} for t in texts
        ]}],
    }
    result = rts.extract(screen)
    assert len(result["growthEvidence"]) <= 3
