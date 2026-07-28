"""Unit tests for radar_mandate.py's pure mandate-screen math -- no network,
no Firestore, no Attio; everything here runs instantly."""
from deal_intelligence import radar_mandate as rm

TIER1 = [
    {"name": "Sequoia", "deals": [{"company": "Northwind Systems"}]},
    {"name": "Index Ventures", "deals": [{"company": "Northwind Systems"}, {"company": "Halden Compute"}]},
]


def test_classify_region_us_state_abbrev():
    assert rm.classify_region("Boston, MA") == "NA"


def test_classify_region_europe_country():
    assert rm.classify_region("London, United Kingdom") == "Europe"


def test_classify_region_other_country():
    assert rm.classify_region("Singapore, Singapore") == "other"


def test_classify_region_unparseable_is_none():
    assert rm.classify_region("somewhere") is None
    assert rm.classify_region("") is None


def test_build_tier1_index_dedupes_within_a_firm():
    firms = [{"name": "Sequoia", "deals": [{"company": "Acme"}, {"company": "acme"}]}]
    index = rm.build_tier1_index(firms)
    assert index["acme"] == ["Sequoia"]


def test_build_tier1_index_collects_multiple_firms_per_company():
    index = rm.build_tier1_index(TIER1)
    assert index["northwind systems"] == ["Sequoia", "Index Ventures"]


def test_s1_geography_passes_na_and_europe():
    assert rm.s1_geography("Boston, MA")[0] is True
    assert rm.s1_geography("Paris, France")[0] is True


def test_s1_geography_fails_other_region():
    passed, reason = rm.s1_geography("Singapore, Singapore")
    assert passed is False
    assert "outside NA/Europe" in reason


def test_s1_geography_unknown_hq_passes_through():
    passed, reason = rm.s1_geography(None)
    assert passed is True
    assert "unknown" in reason


def test_s2_passes_series_b_and_below():
    for series in ("Seed", "Series A", "Series A2", "Series B", "Series B1"):
        assert rm.s2_next_round_in_mandate(series)[0] is True


def test_s2_fails_series_c_and_above():
    passed, reason = rm.s2_next_round_in_mandate("Series C")
    assert passed is False
    assert "already past Series B" in reason


def test_s3_passes_on_index_match():
    index = rm.build_tier1_index(TIER1)
    passed, firms, reason = rm.s3_tier1_on_cap_table("Northwind Systems", False, index)
    assert passed is True
    assert firms == ["Sequoia", "Index Ventures"]
    assert reason is None


def test_s3_passes_on_top10_flag_even_without_index_match():
    # The flag is OR'd in deliberately -- catches a real Tier-1-backed
    # company the hand-typed topVCs[].deals[] index hasn't caught up to.
    passed, firms, reason = rm.s3_tier1_on_cap_table("Some New Co", True, {})
    assert passed is True
    assert firms == []


def test_s3_fails_with_no_flag_and_no_index_match():
    passed, firms, reason = rm.s3_tier1_on_cap_table("Some New Co", False, {})
    assert passed is False
    assert "no Tier 1" in reason


def test_s4_fails_on_bridge_keyword():
    passed, reason = rm.s4_not_bridge_or_flat("Series B (Bridge)", 5_000_000)
    assert passed is False
    assert "bridge" in reason


def test_s4_fails_on_small_round_for_its_series():
    passed, reason = rm.s4_not_bridge_or_flat("Series B", 2_000_000)
    assert passed is False


def test_s4_passes_normal_round():
    passed, reason = rm.s4_not_bridge_or_flat("Series B", 32_000_000)
    assert passed is True
    assert reason is None


def test_new_tier1_lead_likely_scales_with_firm_count():
    assert rm.new_tier1_lead_likely([])[0] == "low"
    assert rm.new_tier1_lead_likely(["Sequoia"])[0] == "medium"
    assert rm.new_tier1_lead_likely(["Sequoia", "Index"])[0] == "high"


def test_insider_round_risk_high_when_s4_fails():
    assert rm.insider_round_risk("high", False) == "high"


def test_insider_round_risk_low_when_new_tier1_high_and_s4_passes():
    assert rm.insider_round_risk("high", True) == "low"


def test_screen_worked_example_northwind_passes(): # RADAR_PLAN.md §7.1
    index = rm.build_tier1_index(TIER1)
    result = rm.screen(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
         "deal_size": 32_000_000, "top10VC": True},
        index,
    )
    assert result["pass"] is True
    assert result["failReason"] is None
    assert result["tier1Firms"] == ["Sequoia", "Index Ventures"]
    assert result["newTier1LeadLikely"] == "high"


def test_screen_worked_example_halden_fails_s3(): # RADAR_PLAN.md §7.2 -- strong company, no Tier 1
    result = rm.screen(
        {"name": "Halden Compute Standalone", "hq": "Austin, TX", "series": "Series B",
         "deal_size": 18_000_000, "top10VC": False},
        {},  # empty index -- no Tier 1 anywhere on the cap table
    )
    assert result["pass"] is False
    assert result["failReason"] == "S3 no Tier 1 on the cap table"


def test_screen_fail_reason_reports_first_failing_screen_in_order():
    # Fails both S1 (geography) and S3 (no Tier 1) -- S1 should win since it's
    # checked first, matching RADAR_PLAN.md's own S1-before-S3 ordering.
    result = rm.screen(
        {"name": "Somewhere Co", "hq": "Singapore, Singapore", "series": "Series B",
         "deal_size": 20_000_000, "top10VC": False},
        {},
    )
    assert result["failReason"].startswith("S1 geography")
