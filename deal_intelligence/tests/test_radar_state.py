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


def test_mandate_pass_no_headcount_still_gets_a_cadence_window():
    # CHANGED 2026-07-29: this used to assert hotness is None, because a
    # company with no Apollo headcount had no window estimate at all. The
    # cadence model (capital_clock.cadence_window_open) needs only a round
    # date, so such a company now gets a real window -- and therefore a real
    # hot/cold classification -- off round cadence alone. Strictly better
    # than the old blank; burn/runway are still honestly reported as None.
    index = rm.build_tier1_index(TIER1)
    result = rs.compute_radar_state(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
         "roundSize": 32_000_000, "roundDate": "2026-02-10", "top10VC": True},
        tier1_index=index, headcount=None, headcount_checked_at=None,
        last_scan_at=None, scan_count=0, today=date(2026, 8, 5),
    )
    assert result["mandate"]["pass"] is True
    assert result["clock"]["estMonthlyBurn"] is None  # no headcount -> still no burn estimate
    assert result["clock"]["runwayMonths"] is None
    assert result["clock"]["predictedWindowOpen"] is not None  # ...but a cadence window exists
    assert result["clock"]["windowBasis"] == "cadence"
    assert result["hotness"] in ("hot", "cold")  # classifiable now, not unknown
    assert result["schedule"]["nextScanAt"] is not None  # opening sequence still computable off roundDate alone


def test_hotness_still_unknown_with_neither_headcount_nor_round_date():
    # The genuine no-information case -- nothing to anchor either model to,
    # so hotness must stay None rather than guessing.
    index = rm.build_tier1_index(TIER1)
    result = rs.compute_radar_state(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
         "roundSize": 32_000_000, "roundDate": None, "top10VC": True},
        tier1_index=index, headcount=None, headcount_checked_at=None,
        last_scan_at=None, scan_count=0, today=date(2026, 8, 5),
    )
    assert result["clock"]["predictedWindowOpen"] is None
    assert result["hotness"] is None


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


def test_end_to_end_hypergrowth_screen_beats_an_identical_quiet_company():
    """The framework's whole point, end to end (2026-07-29). Two companies
    identical in every deterministic input -- same round, same size, same
    date, same headcount -- differing ONLY in what their Stage 1 screen
    found. The hypergrowth one must come out hotter AND with an earlier
    window, driven by evidence the fit rubric scored as a 2.

    Modeled on the real Paper screen: revenue_growth scored 2 (the rubric's
    "no disclosed figure" anchor) with finding text "ARR grew 25x".
    """
    index = rm.build_tier1_index(TIER1)
    fields = {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
              "roundSize": 60_000_000, "roundDate": "2026-05-01", "top10VC": True}
    common = dict(tier1_index=index, headcount=70, headcount_checked_at="2026-07-20",
                  last_scan_at=None, scan_count=0, today=date(2026, 7, 29))

    quiet_screen = {
        "date": "2026-07-29",
        "dimensions": [{"key": "fundamentals", "evidence": "", "subcategories": [
            {"key": "revenue_growth", "score": 2, "finding": "No revenue disclosed; no usable estimate."},
        ]}],
        "rationale": "Solid company, thin disclosure.",
    }
    hypergrowth_screen = {
        "date": "2026-07-29",
        "dimensions": [
            {"key": "fundamentals", "evidence": "", "subcategories": [
                # SAME score as the quiet company -- the difference is the text.
                {"key": "revenue_growth", "score": 2, "finding": "ARR grew 25x post-launch; no $ figure."},
            ]},
            {"key": "lead_round_dynamics", "evidence": "", "subcategories": [
                {"key": "timing_motivation", "score": 4, "finding": "Multiple term sheets, company controlling process."},
            ]},
        ],
        "rationale": "Hypergrowth, raising opportunistically.",
    }

    quiet = rs.compute_radar_state(fields, latest_screen=quiet_screen, **common)
    hot = rs.compute_radar_state(fields, latest_screen=hypergrowth_screen, **common)

    # Hotter, on identical deterministic inputs.
    assert hot["hazard"]["heatPoints"] > quiet["hazard"]["heatPoints"]
    # And meaningfully so -- not a rounding difference.
    assert hot["hazard"]["heatPoints"] > quiet["hazard"]["heatPoints"] * 2
    # Growth tier was recovered from text the rubric scored as a 2.
    assert hot["hazard"]["growthTier"] == "hypergrowth"
    assert quiet["hazard"]["growthTier"] is None
    # Multiple independent families -> the guardrail passes and confidence rises.
    assert hot["hazard"]["twoFamilyPass"] is True
    assert hot["hazard"]["confidence"] == "high"
    # Window pulled in by the cadence model, not the runway model.
    assert hot["clock"]["predictedWindowOpen"] < quiet["clock"]["predictedWindowOpen"]
    assert hot["clock"]["windowBasis"] == "cadence"
    # Evidence is carried so the hub can explain the number.
    assert hot["hazard"]["growthEvidence"]
    # Neither is distressed.
    assert hot["hazard"]["distressFlag"] is False


def test_end_to_end_defensive_raise_is_flagged_not_celebrated():
    # §2.2's distress discriminator, end to end: a company whose screen says
    # the raise is defensive must be flagged, even though "raising soon" is
    # technically true -- never escalated as an opportunity.
    index = rm.build_tier1_index(TIER1)
    result = rs.compute_radar_state(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
         "roundSize": 20_000_000, "roundDate": "2025-06-01", "top10VC": True},
        tier1_index=index, headcount=45, headcount_checked_at="2026-07-20",
        last_scan_at=None, scan_count=0, today=date(2026, 7, 29),
        latest_screen={
            "date": "2026-07-29",
            "dimensions": [{"key": "lead_round_dynamics", "evidence": "", "subcategories": [
                {"key": "timing_motivation", "score": 1, "finding": "Defensive raise; runway extension pressure."},
            ]}],
            "rationale": "Down-round risk.",
        },
    )
    assert result["hazard"]["distressFlag"] is True
    assert "defensive_raise" in result["hazard"]["distressSignals"]


def test_default_watch_floor_never_catches_a_company_with_zero_active_signals():
    # Regression: 2026-07-29 production incident -- DEFAULT_WATCH_FLOOR
    # shipped at 25, but a company with NO active signals (no headcount
    # growth, no job-board hits -- the normal state for a brand-new or
    # genuinely-quiet-but-fine company) can only ever reach ~7-9.5
    # heatPoints off the baseline hazard alone. Every passing company on
    # Radar auto-dropped within DROP_STREAK_THRESHOLD scans, same day. This
    # asserts the invariant directly: the worst-case (furthest-out, i.e.
    # months_until_window=None -> baseline_hazard's lowest bucket)
    # zero-signal company must clear the default floor, so lowScoreStreak
    # never starts climbing for a company that simply hasn't been sensed
    # yet.
    index = rm.build_tier1_index(TIER1)
    result = rs.compute_radar_state(
        {"name": "Northwind Systems", "hq": "Boston, MA", "series": "Series A",
         "roundSize": 30_000_000, "roundDate": "2026-07-01", "top10VC": True},
        tier1_index=index, headcount=None, headcount_checked_at=None,  # no Apollo data -> months_until_window None -> lowest baseline bucket
        last_scan_at=None, scan_count=0, today=date(2026, 8, 5),
        headcount_growth=None, job_signals=None,  # zero active signals
    )
    assert result["hazard"]["heatPoints"] >= rs.DEFAULT_WATCH_FLOOR
    assert result["lowScoreStreak"] == 0
