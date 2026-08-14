"""Builds `deal_intelligence/data/radar-companies-research-input.json` for a
fresh Heat Score Signal Framework research pass (see
docs/RADAR_HEAT_SCORE_RUN.md / docs/RADAR_HEAT_SCORE_RULES.md) from a
companies snapshot (deal_intelligence/export_companies_snapshot.py's output
-- this script reads that file only, no Firestore access needed, so it runs
fine in this sandbox).

Root bug this fixes (Oscar, 2026-08-14, the Atoms case): the 2026-08-06 input
file computed `predictedWindowOpen` fresh via generic cadence math for every
company, even ones that already had a REAL radar.clock from the Apollo-backed
Python pipeline (radar_state.py) -- so the manual research pass's own copy of
the date (baked into marketHeat.predictedWindowOpen and the raiseProbability
signal's evidence text) silently diverged from the table's actual Predicted
Window column, which always reads radar.clock.predictedWindowOpen. Atoms:
real clock said Jan 2027, the manual pass's stale copy said Feb 2028.

Fix: for every company, if `radar.clock` already exists, carry its
predictedWindowOpen/windowBasis/assumptions through UNCHANGED -- never
recompute. Only a company with no radar.clock at all gets a fresh cadence-only
estimate (capital_clock.compute() with headcount=None, same fallback
radar_state.py itself would produce). Either way there is only ever ONE
source of truth for this date per company, so the two copies structurally
cannot disagree again.

Usage:
    python3 -m deal_intelligence.build_radar_research_input
        [--snapshot deal_intelligence/data/companies-snapshot.json]
        [--out deal_intelligence/data/radar-companies-research-input.json]
"""
import argparse
import json
from datetime import date, timedelta

from . import capital_clock, radar_mandate, radar_schedule

DEFAULT_SNAPSHOT = "deal_intelligence/data/companies-snapshot.json"
DEFAULT_OUT = "deal_intelligence/data/radar-companies-research-input.json"

# Second bug this fixes (2026-08-14): raiseProbability and tier1InvestorCount
# are documented as "given, don't re-derive" (RADAR_HEAT_SCORE_RULES.md rows
# 3/16) but the 2026-08-06 pass still had each research agent turn
# predictedWindowOpen into a 0-10 raw score by its own free-form judgment --
# comparing that batch's output, companies with nearly identical
# monthsUntilWindow (~18.5mo) landed anywhere from 0 to 10 with no
# reconstructable rule. Precomputing both here, once, with one fixed
# formula, removes per-agent judgment from the two signals the rubric
# already says shouldn't need any.
RAISE_PROBABILITY_BANDS = [  # (months_until_window <= threshold, raw)
    (3, 10.0), (6, 8.0), (9, 6.0), (12, 4.0), (18, 2.0),
]
RAISE_PROBABILITY_FAR_OUT_RAW = 0.0  # > 18 months out


def _raise_probability_raw(months_until_window):
    if months_until_window is None:
        return None
    if months_until_window <= 0:
        return 10.0
    for threshold, raw in RAISE_PROBABILITY_BANDS:
        if months_until_window <= threshold:
            return raw
    return RAISE_PROBABILITY_FAR_OUT_RAW


def _tier1_investor_count_raw(tier1_firms):
    n = len(tier1_firms or [])
    if n >= 3:
        return 10.0
    if n == 2:
        return 7.0
    if n == 1:
        return 4.0
    return 0.0


def _months_until(target_iso, as_of):
    if not target_iso:
        return None
    try:
        target = date.fromisoformat(target_iso[:10])
    except ValueError:
        return None
    return round((target - as_of).days / 30.44, 1)

# Static per RADAR_HEAT_SCORE_RULES.md -- identical for every company, so
# just carried through rather than rebuilt per row.
SIGNALS_NEEDING_WEB_RESEARCH = {
    "newsVolume": "high|steady|low -- press coverage volume, last ~90 days",
    "publicMomentum": "strong|moderate|weak -- funding rumors, hires, launches, partnerships (feeds crunchbaseGrowthScore/crunchbaseHeatScore/crunchbaseSurgeScore identically)",
    "valuationStepUp": "up|flat|down -- vs prior round's valuation, ONLY if both are publicly disclosed",
    "websiteTrafficTrend": "rising|flat|declining -- only if a public source explicitly reports it",
    "industryGrowthPctChange": "% change in public search/press interest in this company's industry vs last month",
    "companySearchInterestPctChange": "% change in public search interest in this company's name vs last month",
    "yoyRevenueGrowthTier": "hypergrowth (>=100% YoY or $50M+ ARR) | strong (>=$25M ARR or >=70% YoY) | none-found",
    "redditActivity": "clear sustained uptick | steady baseline | little-to-none -- Reddit discussion volume/growth",
}


def _active_radar_companies(companies):
    return [
        c for c in companies
        if (c.get("stage") == "radar" or "radar" in (c.get("tags") or []))
        and not (c.get("radar") or {}).get("droppedAt")
    ]


def _clock_fields(c, as_of):
    """(predictedWindowOpen, windowBasis, assumptions, source, new_clock,
    new_schedule). `new_clock`/`new_schedule` are None ONLY when the
    company already has a clock built from REAL Apollo headcount data
    (radar_apply_heat_scores.py protects exactly that case, and no other --
    see that module's 2026-08-14 fix). Every other company -- no clock at
    all, or a clock that's itself just the same generic cadence-only
    fallback with no headcount -- gets a freshly computed one, using the
    exact same fallback (capital_clock.compute(), headcount=None) and
    mandatory-sweep schedule (radar_schedule.next_mandatory_sweep()) the
    real pipeline itself uses for a company with no Apollo lookup / no scan
    history yet. Note this is provably a no-op for the fallback-only case:
    cadence_window_open() is a pure function of round_date + growth_tier,
    not of `as_of`, so recomputing it today reproduces the exact same date
    -- this isn't silently changing anything, just letting the apply
    script actually write the (unchanged) value instead of skipping it."""
    clock = (c.get("radar") or {}).get("clock")
    if clock and clock.get("headcountCheckedAt"):
        return clock["predictedWindowOpen"], clock.get("windowBasis"), clock.get("assumptions"), "existing Apollo-verified radar.clock", None, None

    hq = (c.get("origin") or {}).get("hq")
    fields = {
        "roundSize": c.get("roundSize"),
        "roundDate": c.get("roundDate"),
        "region": radar_mandate.classify_region(hq),
        "radarCategory": None,
        "description": c.get("description"),
    }
    new_clock = capital_clock.compute(fields, headcount=None)
    # Same seasonality shift radar_state.py itself applies after
    # capital_clock.compute() (predictedWindowOpen shifts LATER out of a
    # dead zone, contactByDate EARLIER, alertAtDate re-derived from the
    # shifted contactByDate) -- skipping this step is what produced the one
    # real mismatch found when cross-checking this rewrite against
    # production (AltaClaro: this function alone gives 2027-08-01, which
    # falls inside the Aug dead zone; the real pipeline had already shifted
    # it to 2027-09-05, which is the value on file and the value this now
    # reproduces).
    if new_clock["predictedWindowOpen"]:
        shifted_open = radar_schedule.shift_out_of_dead_zone(date.fromisoformat(new_clock["predictedWindowOpen"]), "later")
        new_clock["predictedWindowOpen"] = shifted_open.isoformat()
    if new_clock["contactByDate"]:
        shifted_contact = radar_schedule.shift_out_of_dead_zone(date.fromisoformat(new_clock["contactByDate"]), "earlier")
        new_clock["contactByDate"] = shifted_contact.isoformat()
        new_clock["alertAtDate"] = (shifted_contact - timedelta(weeks=6)).isoformat()
    sweep = radar_schedule.next_mandatory_sweep(as_of)
    new_schedule = {
        "nextScanAt": sweep.isoformat(),
        "nextScanReason": f"mandatory sweep ({sweep.isoformat()})",
        "scanCount": 1,
        "lastScanAt": as_of.isoformat(),
    }
    return (new_clock["predictedWindowOpen"], new_clock.get("windowBasis"), new_clock.get("assumptions"),
            "freshly computed (no radar.clock yet)", new_clock, new_schedule)


def build_entry(c, as_of=None):
    as_of = as_of or date.today()
    hq = (c.get("origin") or {}).get("hq")
    (predicted_window_open, window_basis, assumptions, window_source,
     new_clock, new_schedule) = _clock_fields(c, as_of)
    tier1_firms = c.get("tier1_33Investors") or []
    months_until_window = _months_until(predicted_window_open, as_of)
    return {
        "id": c["id"],
        "name": c.get("name"),
        "website": c.get("website"),
        "hq": hq,
        "region": radar_mandate.classify_region(hq),
        "capitalIntensity": capital_clock.classify_capital_intensity(None, c.get("description")),
        "description": c.get("description"),
        "round": c.get("round"),
        "roundDate": c.get("roundDate"),
        "roundSize": c.get("roundSize"),
        "investors": c.get("investors") or [],
        "top10Investors": c.get("top10Investors") or [],
        "tier1_33Investors": tier1_firms,
        "top10VC": bool(c.get("top10VC")),
        "tier1FirmsOnCapTable": tier1_firms,
        "predictedWindowOpen": predicted_window_open,
        "windowBasis": window_basis,
        "capitalClockAssumptions": assumptions,
        "predictedWindowOpenSource": window_source,
        "monthsUntilWindow": months_until_window,
        # Non-null only for a company with no existing radar.clock -- these
        # get passed straight through to radar_apply_heat_scores.py's
        # entry["clock"]/entry["schedule"], which only writes them when the
        # company doesn't already have real ones (never overwrites).
        "newClock": new_clock,
        "newSchedule": new_schedule,
        # Fully resolved -- score, weight, and contribution -- so the agent
        # never touches these two signals at all, just includes them as-is
        # in its output (see prompt template / RADAR_HEAT_SCORE_RULES.md
        # rows 3 and 16, both explicitly "given, don't re-derive").
        "precomputedSignals": {
            "raiseProbability": {
                "computed": months_until_window is not None,
                "raw": _raise_probability_raw(months_until_window),
                "weight": 15,
                "evidence": (
                    f"{months_until_window} months to predicted window ({predicted_window_open}, "
                    f"{window_basis} basis)" if months_until_window is not None
                    else "no predictedWindowOpen available"
                ),
            },
            "tier1InvestorCount": {
                "computed": True,
                "raw": _tier1_investor_count_raw(tier1_firms),
                "weight": 10,
                "evidence": f"{len(tier1_firms)} Tier 1 firm(s) on cap table: {', '.join(tier1_firms) or 'none'}",
            },
            "momEmployeeGrowth": {"computed": False, "raw": None, "weight": 2.5, "evidence": "No Apollo/ATS access this pass."},
            "jobPostingVelocity": {"computed": False, "raw": None, "weight": 2.5, "evidence": "No Apollo/ATS access this pass."},
        },
        "signalsNeedingWebResearch": SIGNALS_NEEDING_WEB_RESEARCH,
    }


def run(snapshot_path=DEFAULT_SNAPSHOT, out_path=DEFAULT_OUT):
    with open(snapshot_path) as f:
        companies = json.load(f)
    active = _active_radar_companies(companies)
    entries = [build_entry(c) for c in active]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    carried = sum(1 for e in entries if e["predictedWindowOpenSource"] == "existing Apollo-verified radar.clock")
    fresh = len(entries) - carried
    print(f"{len(entries)} active Radar companies written to {out_path}")
    print(f"  {carried} carried their predictedWindowOpen through from an existing Apollo-verified radar.clock (protected, not recomputed)")
    print(f"  {fresh} got a freshly computed clock (either had none, or only a generic cadence-only fallback with no real headcount)")
    return entries


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()
    run(snapshot_path=args.snapshot, out_path=args.out)


if __name__ == "__main__":
    main()
