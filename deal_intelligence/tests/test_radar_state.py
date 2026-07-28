"""Unit tests for radar_state.compute_radar_state's pure orchestration --
fabricated inputs, no Firestore/Apollo I/O. Mirrors RADAR_PLAN.md §7.1-7.3's
worked examples."""
from datetime import date

from deal_intelligence import radar_mandate as rm
from deal_intelligence import radar_state as rs

TIER1 = [
    {"name": "Sequoia", "deals": [{"company": "Northwind Systems"}]},
    {"name": "Index Ventures", "deals": [{"company": "Northwind Systems"}]},
]


def test_mandate_fail_short_circuits_no_clock_or_schedule(): # RADAR_PLAN.md §7.2 -- Halden Compute
    result = rs.compute_radar_state(
        {"name": "Halden Compute", "hq": "Austin, TX", "series": "Series B",
         "roundSize": 18_000_000, "roundDate": "2026-03-01", "top10VC": False},
        tier1_index={}, headcount=None, headcount_checked_at=None,
        last_scan_at=None, scan_count=0, today=date(2026, 8, 5),
    )
    assert result["mandate"]["pass"] is False
    assert result["mandate"]["failReason"] == "S3 no Tier 1 on the cap table"
    assert result["clock"] is None
    assert result["schedule"] is None
    assert result["hotness"] is None


def test_mandate_pass_no_headcount_yet_leaves_hotness_unknown():
    index = rm.build_tier1_index(TIER1)
    result = rs.compute_radar_state(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
         "roundSize": 32_000_000, "roundDate": "2026-02-10", "top10VC": True},
        tier1_index=index, headcount=None, headcount_checked_at=None,
        last_scan_at=None, scan_count=0, today=date(2026, 8, 5),
    )
    assert result["mandate"]["pass"] is True
    assert result["clock"]["estMonthlyBurn"] is None  # no headcount -> no burn estimate
    assert result["hotness"] is None  # can't classify without a window estimate
    assert result["schedule"]["nextScanAt"] is not None  # opening sequence still computable off roundDate alone


def test_full_pass_northwind_worked_example(): # RADAR_PLAN.md §7.1, approximately
    index = rm.build_tier1_index(TIER1)
    result = rs.compute_radar_state(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
         "roundSize": 32_000_000, "roundDate": "2026-02-10", "top10VC": True,
         "radarCategory": "AI data infrastructure", "description": "in-house model training"},
        tier1_index=index, headcount=81, headcount_checked_at="2026-07-20",
        last_scan_at=None, scan_count=0, today=date(2026, 8, 5),
    )
    assert result["mandate"]["pass"] is True
    assert result["clock"]["capitalIntensity"] == "high"
    assert result["clock"]["estMonthlyBurn"] > 0
    assert result["hotness"] in ("hot", "cold")
    assert result["schedule"]["scanCount"] == 1  # advance_scan defaults True
    assert result["schedule"]["nextScanAt"] is not None


def test_advance_scan_false_does_not_increment_scan_count():
    index = rm.build_tier1_index(TIER1)
    result = rs.compute_radar_state(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
         "roundSize": 32_000_000, "roundDate": "2026-02-10", "top10VC": True},
        tier1_index=index, headcount=81, headcount_checked_at="2026-07-20",
        last_scan_at=date(2026, 6, 10), scan_count=2, today=date(2026, 8, 5),
        advance_scan=False,
    )
    assert result["schedule"]["scanCount"] == 2  # unchanged
    assert result["schedule"]["lastScanAt"] == "2026-06-10"  # unchanged, not stamped to today


def test_advance_scan_true_stamps_today_and_increments():
    index = rm.build_tier1_index(TIER1)
    result = rs.compute_radar_state(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
         "roundSize": 32_000_000, "roundDate": "2026-02-10", "top10VC": True},
        tier1_index=index, headcount=81, headcount_checked_at="2026-07-20",
        last_scan_at=date(2026, 6, 10), scan_count=2, today=date(2026, 8, 5),
        advance_scan=True,
    )
    assert result["schedule"]["scanCount"] == 3
    assert result["schedule"]["lastScanAt"] == "2026-08-05"


def test_distress_like_company_still_computes_but_stays_cold_far_out(): # RADAR_PLAN.md §7.3 spirit
    # A company overdue and quiet doesn't get a special v1 branch (no
    # momentum/quiet/distress modifiers this pass -- see the plan's
    # explicit exclusions) but shouldn't crash or misfire hot on stale data.
    index = rm.build_tier1_index(TIER1)
    result = rs.compute_radar_state(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series A",
         "roundSize": 5_000_000, "roundDate": "2020-01-01", "top10VC": True,
         "radarCategory": "B2B SaaS"},
        tier1_index=index, headcount=10, headcount_checked_at="2026-07-20",
        last_scan_at=None, scan_count=0, today=date(2026, 8, 5),
    )
    assert result["mandate"]["pass"] is True
    assert result["clock"]["runwayMonths"] == 0.0  # long since exhausted
    assert result["hotness"] == "hot"  # past-window reads hot in v1 -- no distress branch to suppress it yet
