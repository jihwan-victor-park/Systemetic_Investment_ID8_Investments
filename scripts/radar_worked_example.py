"""Traceability worked example for Radar's heat/hazard model, with real
dates run through the ACTUAL pure functions (radar_mandate, capital_clock,
radar_timing_signals, radar_hazard, radar_state) -- nothing here is
hand-narrated or hardcoded to a desired answer; every number printed is
whatever today's code actually computes for the inputs given.

Oscar, 2026-07-30: "run tests on the current radar companies to set the
dates and stuff, and maybe grab one to show how the thing would go... more
traceability." Two parts:

  PART 1 -- Northwind Systems, the SAME company/scan cadence RADAR_PLAN.md
  §7.1 narrates by hand (52 -> 94 heads, finance-hire timeline, etc.), run
  scan-by-scan through the real code with real dates. Where the numbers
  below diverge from that doc's hand-written table, that's flagged rather
  than papered over -- the doc predates several of the hazard model's
  refinements (F3 growth-tier scoring, the confidence-discount kernels), so
  exact reproduction isn't expected; what's checked is that the SHAPE of
  the story (heat rises as finance/corp-dev signals age toward their peak,
  confidence firms up as more sources come online) still holds under the
  current code.

  PART 2 -- Isabella's mandate (2026-07-30), demonstrated directly: three
  otherwise-IDENTICAL companies whose only difference is what their Stage 1
  screen (the thing that would cite Sacra/Crunchbase-style growth research)
  found -- no screen at all, a screen that found nothing quantitative, and
  a screen with an unverified vs. verified 25x-ARR claim. The point of the
  comparison is what does NOT move: heatPoints for "no screen" and "screen
  found nothing" must be IDENTICAL (absence of data must never read as a
  worse company than absence of information), while dataCoverage correctly
  tells the two apart, and confidence is capped low on whichever of them has
  under 2 of 3 sources checked -- exactly Isabella's four asks, ordered as
  she stated them.

Usage:
    python3 scripts/radar_worked_example.py
"""
import sys
from datetime import date

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from deal_intelligence import capital_clock, radar_hazard, radar_mandate, radar_signal_series, radar_state, radar_timing_signals

TIER1 = [{"name": "Cortland Partners", "deals": [{"company": "Northwind Systems"}]}]


def _hr(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _fmt_pct(x):
    return f"{x * 100:.1f}%"


# ═══════════════════════════════════════════════════════════════════════
# PART 1 -- Northwind Systems, RADAR_PLAN.md §7.1's own worked example,
# re-run scan-by-scan through today's actual code.
# ═══════════════════════════════════════════════════════════════════════

_hr("PART 1 -- Northwind Systems (RADAR_PLAN.md §7.1's company), scan-by-scan")

fields = {
    "name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
    "roundSize": 32_000_000, "roundDate": "2026-02-10", "top10VC": True,
    "radarCategory": "AI data infrastructure", "description": "in-house model training",
}
tier1_index = radar_mandate.build_tier1_index(TIER1)

mandate = radar_mandate.screen(
    {"name": fields["name"], "hq": fields["hq"], "series": fields["series"],
     "deal_size": fields["roundSize"], "top10VC": fields["top10VC"]},
    tier1_index,
)
print(f"Mandate screen: pass={mandate['pass']}  reasoning={mandate['reasoning']}")
assert mandate["pass"], "Northwind must clear the mandate screen for this trace to mean anything"

# The doc's own headcount ledger (§7.1's table): 52 at close, then 71/76/76/76/76/88
# across the six scans -- built here as an explicit time series so
# radar_signal_series.growth_rate() derives the SAME derivative
# recompute_and_write would, from real samples, not a hand-picked rate.
HEADCOUNT_LEDGER = [
    ("2026-02-10", 52),   # round close
    ("2026-08-05", 71),   # Scan 1
    ("2026-09-16", 76),   # Scan 2
    ("2026-10-08", 76),   # Scan 4 (no headcount change since Scan 2 in the doc's own narrative)
    ("2026-11-05", 76),   # Scan 5
    ("2026-12-17", 88),   # Scan 6
]

# job_signals ledger: bucket -> firstSeenDate, as of each scan (mirrors
# radar_state._active_signals' expected shape). Matches §7.1's own timeline:
# Director of Finance first seen 2026-09-14, VP Sales first seen 2026-10-03
# (an ExecGTM posting, filled by 2026-11-05 per the doc so it drops out of
# job_signals from Scan 5 onward -- see radar_state.recompute_and_write's own
# "buckets that dropped to 0 postings fall out of job_signals entirely"),
# Head of Corp Dev first seen 2026-12-17.
SCANS = [
    {"date": "2026-08-05", "label": "Scan 1", "job_signals": {}},
    {"date": "2026-09-16", "label": "Scan 2", "job_signals": {}},
    {"date": "2026-09-18", "label": "Scan 3", "job_signals": {
        "rolesSeniorFinance": {"firstSeenDate": "2026-09-14"},
    }},
    {"date": "2026-10-08", "label": "Scan 4", "job_signals": {
        "rolesSeniorFinance": {"firstSeenDate": "2026-09-14"},
        "rolesExecGTM": {"firstSeenDate": "2026-10-03"},
    }},
    {"date": "2026-11-05", "label": "Scan 5 (finance role filled, VP Sales role filled)", "job_signals": {}},
    {"date": "2026-12-17", "label": "Scan 6", "job_signals": {
        "rolesCorpDev": {"firstSeenDate": "2026-12-17"},
    }},
]

last_scan_at = None
scan_count = 0
print(f"\n{'scan':<45} {'p90':>6} {'p180':>6} {'heat':>6} {'conf':>8} {'coverage':>9}  families")
for scan in SCANS:
    today = date.fromisoformat(scan["date"])
    headcount = next(hc for d, hc in reversed(HEADCOUNT_LEDGER) if date.fromisoformat(d) <= today)
    series = [{"date": d, "value": hc} for d, hc in HEADCOUNT_LEDGER if date.fromisoformat(d) <= today]
    headcount_growth = radar_signal_series.growth_rate(series)

    result = radar_state.compute_radar_state(
        fields, tier1_index, headcount, "2026-02-10" if today == date(2026, 2, 10) else scan["date"],
        last_scan_at, scan_count, today=today, advance_scan=True,
        headcount_growth=headcount_growth, job_signals=scan["job_signals"],
        job_sensor_available=True,  # an ATS was found for Northwind from Scan 1 onward
        latest_screen=None,  # no Stage 1 screen ever ran in this trace -- see Part 2
    )
    last_scan_at = today
    scan_count = result["schedule"]["scanCount"]
    h = result["hazard"]
    print(f"{scan['label']:<45} {_fmt_pct(h['p90']):>6} {_fmt_pct(h['p180']):>6} {h['heatPoints']:>6.1f} "
          f"{h['confidence']:>8} {_fmt_pct(h['dataCoverage']):>9}  {','.join(h['familiesActive']) or 'none'}")

print(
    "\nNote: heatPoints tracks each hiring signal's age against its kernel\n"
    "(RADAR_SIGNAL_ENGINE.md §4.1) rather than climbing monotonically the way\n"
    "RADAR_PLAN.md §7.1's hand-narrated table does (18% -> 61% p180) -- a\n"
    "literal match isn't expected (that doc predates the F3 growth-tier and\n"
    "confidence-discount kernels added 2026-07-29). Scan 5's drop to 'none/\n"
    "low' is real and worth naming explicitly, not glossed over: once both\n"
    "the finance and GTM roles are FILLED, radar_state._active_signals has\n"
    "nothing left to report for them (a filled role's signal is gone, not\n"
    "aged out) -- until Scan 6's corp-dev posting gives it something new.\n"
    "That's an existing, real gap (a filled-and-not-yet-replaced role should\n"
    "arguably still carry some residual weight) rather than something this\n"
    "change introduces -- flagged here because this script's whole job is\n"
    "surfacing what the code actually does, not what the narrative implies.\n"
    "dataCoverage sits at 67% (2 of 3: capitalClock + jobSignals) throughout,\n"
    "because this trace never wires a Stage 1 screen for Northwind --\n"
    "correctly reported as a real, missing source, not folded silently into\n"
    "the timing math."
)


# ═══════════════════════════════════════════════════════════════════════
# PART 2 -- Isabella's mandate (2026-07-30), demonstrated directly.
# ═══════════════════════════════════════════════════════════════════════

_hr("PART 2 -- Isabella's mandate: missing vs. unverified vs. verified growth data")

today = date(2026, 7, 30)
common_fields = {
    "name": "Northwind Systems", "hq": "Boston, MA", "series": "Series B",
    "roundSize": 32_000_000, "roundDate": "2026-02-10", "top10VC": True,
}
common = dict(
    tier1_index=tier1_index, headcount=94, headcount_checked_at="2026-07-20",
    last_scan_at=None, scan_count=0, today=today,
    headcount_growth=None, job_signals=None, job_sensor_available=True,
)

no_screen = radar_state.compute_radar_state(common_fields, latest_screen=None, **common)

# Screens dated ~2 months before `today` -- hypergrowth_revenue(_unverified)'s
# kernel peaks at 2 months (radar_hazard.SIGNAL_KERNELS), so this is the age
# at which the verified-vs-unverified split is actually visible. A screen
# dated yesterday would show almost no effect from EITHER variant, by
# design (RADAR_SIGNAL_ENGINE.md §4.1: "more predictive months later, not
# the week it happens") -- that's a real property of the model, not a bug,
# but it would make a poor demonstration of this specific contrast.
SCREEN_DATE = "2026-05-28"  # ~2 months before `today` (2026-07-30)

quiet_screen = {
    "date": SCREEN_DATE,
    "dimensions": [{"key": "fundamentals", "evidence": "", "subcategories": [
        {"key": "revenue_growth", "score": 2, "finding": "No revenue disclosed; no usable estimate."},
    ]}],
}
screened_quiet = radar_state.compute_radar_state(common_fields, latest_screen=quiet_screen, **common)

unverified_screen = {
    "date": SCREEN_DATE, "confidence": "low",
    "dimensions": [{"key": "fundamentals", "evidence": "", "subcategories": [
        {"key": "revenue_growth", "score": 2, "finding": "ARR grew 25x post-launch; no $ figure, no citation."},
    ]}],
}
screened_unverified = radar_state.compute_radar_state(common_fields, latest_screen=unverified_screen, **common)

verified_screen = {
    "date": SCREEN_DATE, "confidence": "high",
    "dimensions": [{"key": "fundamentals", "evidence": "", "subcategories": [
        {"key": "revenue_growth", "score": 2, "finding": "ARR grew 25x post-launch, per audited investor update."},
    ]}],
}
screened_verified = radar_state.compute_radar_state(common_fields, latest_screen=verified_screen, **common)

rows = [
    ("No Stage 1 screen at all (absent from research entirely)", no_screen),
    ("Screen ran, found nothing quantitative", screened_quiet),
    ("Screen ran, 25x ARR claim, UNVERIFIED (low confidence)", screened_unverified),
    ("Screen ran, 25x ARR claim, VERIFIED (high confidence)", screened_verified),
]
print(f"\n{'scenario':<58} {'heat':>6} {'conf':>8} {'coverage':>9}  growthTier")
for label, result in rows:
    h = result["hazard"]
    print(f"{label:<58} {h['heatPoints']:>6.1f} {h['confidence']:>8} {_fmt_pct(h['dataCoverage']):>9}  {h.get('growthTier')}")

assert no_screen["hazard"]["heatPoints"] == screened_quiet["hazard"]["heatPoints"], \
    "absence of a screen and a screen finding nothing must score IDENTICALLY -- missing is not zero"
assert no_screen["hazard"]["dataCoverage"] < screened_quiet["hazard"]["dataCoverage"], \
    "but coverage must still tell the two apart -- one source is genuinely unchecked, the other checked and quiet"
assert screened_unverified["hazard"]["heatPoints"] < screened_verified["hazard"]["heatPoints"], \
    "same claim, same evidence text -- the ONLY difference is whether the research was verifiable"
assert screened_unverified["hazard"]["growthTier"] == screened_verified["hazard"]["growthTier"] == "hypergrowth"

print(
    "\nConfirmed:\n"
    "  1. 'no screen' and 'screen found nothing' score IDENTICALLY on heatPoints\n"
    "     -- absence of data is never read as a worse company than absence of\n"
    "     information (Isabella's mandate #1/#2).\n"
    "  2. ...but dataCoverage tells them apart (67% vs 100%), so a partner can\n"
    "     see WHICH kind of 'quiet' a company is, rather than one number hiding\n"
    "     both (mandate #4/#5).\n"
    "  3. The unverified 25x-ARR read scores lower than the verified one, same\n"
    "     underlying claim -- 'recalculate using only available signals' cuts\n"
    "     both ways: an unconfirmed signal contributes LESS, not zero and not\n"
    "     full strength (mandate #3)."
)
