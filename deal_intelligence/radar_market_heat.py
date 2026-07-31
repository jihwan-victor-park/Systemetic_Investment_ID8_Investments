"""Radar's market-heat score ("Heat Score Signal Framework", Oscar
2026-07-31 -- a 16-signal weighted scorecard he supplied as a spreadsheet
rubric, `Heat Score Signal Framework.xlsx`).

DELIBERATELY a separate number from `radar.hazard.heatPoints`
(radar_hazard.py's hazard/probability model, which drives auto-drop and
scan cadence) and from hub-next's older `radarHeatScore.js` placeholder
(timing+fit, 0-12 scale). This codebase already had two things informally
called "heat score" before this one; adding a third under the same name
would make an already-confusing situation worse. Stored as
`radar.marketHeat` -- this module never writes to `radar.hazard` and
nothing reads `radar.marketHeat` back into the hazard model or the scan
scheduler. It answers "is the market paying attention to this company
right now" (buzz/momentum), not "when will they raise" -- RADAR_SIGNAL_
ENGINE.md §4 explicitly argues against a flat 0-100 scorecard for THAT
question, and this module doesn't relitigate that; it's a second,
independent read for a different purpose (Oscar, 2026-07-31: scoped to the
same Radar-tracked population, not hub-wide).

Only computed for companies that already pass Radar's mandate screen
(radar_state.py calls this inside the mandate-pass branch only) -- same
population radar_mandate.screen() already gates everything else to.

v1 status: 4 of the rubric's 16 signals are wired (raiseProbability,
momEmployeeGrowth, jobPostingVelocity, tier1InvestorCount -- 30 of the 100
weighted points). The other 12 need a vendor that isn't licensed yet
(Google Trends, Crunchbase, Sacra, Reddit -- see the pricing findings
Oscar was given 2026-07-31) or, for stepUp, a prior-round-valuation field
this pipeline doesn't carry today. Every unwired signal reports
`computed: False, raw: None` -- NEVER a silent 0, which would read as "the
market is cold on this company" instead of "we haven't measured this
yet." `score` is the sum of contributions from whatever IS computed (so it
grows as more signals come online, never shrinks); `normalizedScore`
rescales that same sum to the weight actually computed, for an
apples-to-apples read while most of the rubric is still unwired.

Same pure-function idiom as rubric.py/radar_mandate.py/radar_hazard.py/
capital_clock.py: plain data in, plain data out, no I/O. Every input here
is something radar_state.py has already resolved (a rate, a firm list, a
count) -- this module never touches a raw time series or makes a network
call itself, matching capital_clock.compute()'s "resolved inputs in"
convention.
"""
from datetime import date

from . import portfolio_timing

# Heat Score Signal Framework.xlsx "Weight" column, keyed to this module's
# signal names. Sums to 100 -- the two "Input only" rows (Latest Round,
# Estimated Time Between Rounds) aren't scored signals in their own right,
# they're just the inputs `raiseProbability` derives from, so they don't
# get a WEIGHTS entry.
WEIGHTS = {
    "raiseProbability": 15,
    "industryGrowth": 10,
    "momEmployeeGrowth": 2.5,
    "jobPostingVelocity": 2.5,
    "crunchbaseGrowthScore": 5,
    "stepUp": 5,
    "yoyRevenueGrowth": 5,
    "newsVolume": 10,
    "websiteVisitsGrowth": 5,
    "googleTrendsSearchInterest": 10,
    "redditActivity": 5,
    "crunchbaseHeatScore": 10,
    "crunchbaseSurgeScore": 5,
    "tier1InvestorCount": 10,
}
assert abs(sum(WEIGHTS.values()) - 100) < 1e-9  # guards against a future edit silently drifting off the rubric's own 100-point total

# Signals wired this pass -- everything else in WEIGHTS reports
# computed=False until its vendor/data gap closes (see module docstring).
_WIRED = frozenset({"raiseProbability", "momEmployeeGrowth", "jobPostingVelocity", "tier1InvestorCount"})


def raise_probability(series, round_date, as_of=None):
    """Signals #1+#2 -> #3: 'Raise Probability', High/Med/Low mapped to
    10/5/0. Reuses portfolio_timing.base_rate()'s stage-cadence-vs-months-
    elapsed band -- the SAME mechanism the rubric's own signal #2
    describes ("typical/estimated gap between rounds for this company at
    this stage"), not capital_clock.py's separate growth-tier cadence
    table (a different, Radar-specific mechanism built for burn/window
    prediction, see that module's docstring). Reusing rather than adding a
    THIRD "typical time between rounds" table that would disagree with
    the other two.

    Returns (raw_score, band, context) -- raw_score/band are None when
    base_rate() has no round date to anchor to at all (its own "no
    financing date on file" fallback), never a fabricated medium."""
    result = portfolio_timing.base_rate({"latestRound": series, "latestRoundDate": round_date}, as_of=as_of)
    if result.months_since is None:
        return None, None, result.context
    raw = {"high": 10.0, "medium": 5.0, "low": 0.0}[result.band]
    return raw, result.band, result.context


def mom_employee_growth(rate):
    """Signal #5, given an already-computed MoM rate (radar_signal_series.
    mom_growth_rate() on the `headcount` sensor series radar_state.py
    already maintains for the hazard model). 10 = >5% MoM; 7 = 2-5%; 5 =
    0-2%; 0 = flat or declining. `rate=None` (fewer than 2 headcount
    samples yet) returns None, not 0."""
    if rate is None:
        return None
    if rate > 0.05:
        return 10.0
    if rate >= 0.02:
        return 7.0
    if rate >= 0:
        return 5.0
    return 0.0


def job_posting_velocity(rate, current_open_roles):
    """Signal #6, given an already-computed MoM rate on TOTAL open roles
    (radar_signal_series.mom_growth_rate() on the new `openRoles` sensor
    series -- distinct from radar_jobs.py's per-BUCKET counts, which only
    cover finance/corp-dev/GTM/recruiting titles and feed the hazard
    model's kernels, not this literal "total postings" trend).

    `current_open_roles is None` (jobs sensor never ran -- no ATS detected,
    or gated below the watch floor) returns None: we don't know the count,
    which is not the same claim as "confirmed zero." `current_open_roles ==
    0` (sensor DID run, found nothing open) scores 0 outright -- the
    rubric's own "no open roles / hiring freeze" case, checked before the
    trend since a freeze IS the signal regardless of what the rate says.
    Otherwise: 10 = >25% growth; 7 = 10-25%; 5 = flat (+-10%); 3 =
    declining. `rate=None` with roles > 0 (no prior reading yet) also
    returns None."""
    if current_open_roles is None:
        return None
    if current_open_roles == 0:
        return 0.0
    if rate is None:
        return None
    if rate > 0.25:
        return 10.0
    if rate >= 0.10:
        return 7.0
    if rate >= -0.10:
        return 5.0
    return 3.0


def tier1_investor_count(tier1_firms):
    """Signal #16. 10 = 3+ Tier 1 investors; 7 = 2; 4 = 1. The rubric's own
    table doesn't state a 0-investor row explicitly, but every other
    signal's lowest band floors at 0, so 0 firms scores 0 here by the same
    pattern -- reachable in practice via the top10VC-flag S3 pass with an
    empty tier1_firms list (radar_mandate.s3_tier1_on_cap_table()'s own
    documented edge case), not just a defensive default.

    tier1_firms: radar.mandate.tier1Firms, already resolved by
    radar_mandate against the topVCs index. The rubric's source column
    says 'Webscraping'; this codebase answers the same question (which
    Tier 1s are on the cap table) via a name-match against the admin-
    maintained topVCs Firestore collection instead of literal scraping."""
    n = len(tier1_firms or [])
    if n >= 3:
        return 10.0, n
    if n == 2:
        return 7.0, n
    if n == 1:
        return 4.0, n
    return 0.0, n


def _entry(raw, weight, **extra):
    computed = raw is not None
    return {
        "computed": computed,
        "raw": raw,
        "weight": weight,
        "contribution": round(raw / 10 * weight, 3) if computed else None,
        **extra,
    }


def compute(fields, rates, as_of=None):
    """The pipeline radar_state.py calls, from inside the mandate-pass
    branch only.

    fields: {series, roundDate, tier1Firms}.
    rates: {headcountMomRate, openRolesMomRate, currentOpenRoles} --
    already-derived numbers, none of them raw series (see module
    docstring's "resolved inputs in" note).

    Returns {signals: {key: {computed, raw, weight, contribution, ...}},
    score, normalizedScore, pointsAvailable, notComputed, computedAt}."""
    signals = {}

    raw, band, context = raise_probability(fields.get("series"), fields.get("roundDate"), as_of)
    signals["raiseProbability"] = _entry(raw, WEIGHTS["raiseProbability"], band=band, context=context)

    raw = mom_employee_growth(rates.get("headcountMomRate"))
    signals["momEmployeeGrowth"] = _entry(raw, WEIGHTS["momEmployeeGrowth"], momRate=rates.get("headcountMomRate"))

    raw = job_posting_velocity(rates.get("openRolesMomRate"), rates.get("currentOpenRoles"))
    signals["jobPostingVelocity"] = _entry(raw, WEIGHTS["jobPostingVelocity"], momRate=rates.get("openRolesMomRate"))

    raw, n = tier1_investor_count(fields.get("tier1Firms"))
    signals["tier1InvestorCount"] = _entry(raw, WEIGHTS["tier1InvestorCount"], count=n)

    for key, weight in WEIGHTS.items():
        if key not in signals:
            # Not yet wired -- vendor/data gap, see module docstring. Never a
            # silent 0: computed=False is what tells the hub to render "not
            # measured" rather than a cold reading.
            signals[key] = _entry(None, weight)

    points_available = sum(s["weight"] for s in signals.values() if s["computed"])
    contribution_total = sum(s["contribution"] for s in signals.values() if s["computed"])
    not_computed = sorted(k for k, s in signals.items() if not s["computed"])

    return {
        "signals": signals,
        "score": round(contribution_total, 1) if points_available else None,
        "normalizedScore": round(contribution_total / points_available * 100, 1) if points_available else None,
        "pointsAvailable": points_available,
        "notComputed": not_computed,
        "computedAt": (as_of or date.today()).isoformat(),
    }
