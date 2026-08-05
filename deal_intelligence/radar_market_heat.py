"""Radar's market-heat score ("Heat Score Signal Framework", Oscar
2026-07-31 -- a 16-signal weighted scorecard he supplied as a spreadsheet
rubric, `Heat Score Signal Framework.xlsx`).

Oscar's explicit call (2026-08-05): this IS meant to become Radar's
primary/hegemonic heat score over time, superseding `radar.hazard.heatPoints`
(radar_hazard.py's kernel/probability model) and hub-next's older
`radarHeatScore.js` placeholder (timing+fit, 0-12 scale) as THE number a
partner looks at. **Not fully swapped over yet, this pass**: `radar_hazard.
heatPoints` still drives `DROP_STREAK_THRESHOLD`/`watch_floor` auto-drop and
(via `capital_clock`) scan-cadence scheduling, unchanged -- those
thresholds were tuned specifically against hazard's own exponential-hazard
distribution (see `radar_state.py`'s own DEFAULT_WATCH_FLOOR comment for
the production incident that taught that lesson), and `marketHeat.
normalizedScore` has a structurally different shape (no forced baseline
floor -- an unremarkable-but-fine company lands near 50, not near hazard's
~7-9.5) that needs its own real-company validation before it can safely
drive the same auto-drop/scheduling decisions. This module still never
writes to `radar.hazard`, and nothing reads `marketHeat` back into the
hazard model -- but `marketHeat` (with `timing_urgency_multiplier()` and
the round-announced ceiling below) IS now the score meant to be shown
first, everywhere it's surfaced, per that same 2026-08-05 decision.

Only computed for companies that already pass Radar's mandate screen
(radar_state.py calls this inside the mandate-pass branch only) -- same
population radar_mandate.screen() already gates everything else to.

v1 status (updated 2026-08-05): 15 of the rubric's 16 signals are wired.
`raiseProbability`, `momEmployeeGrowth`, `jobPostingVelocity`,
`tier1InvestorCount` are computed straight from already-resolved
pipeline data (no new fetch). `industryGrowth`/`googleTrendsSearchInterest`
come from Google Trends (`google_trends.py`, via `pytrends` -- free,
public, but unofficial and untested from this sandbox's network, see that
module's own docstring). `newsVolume`/`stepUp`/`websiteVisitsGrowth` and
the three Crunchbase-branded rows (`crunchbaseGrowthScore`/
`crunchbaseHeatScore`/`crunchbaseSurgeScore`, all fed by ONE shared
"public momentum" proxy read -- see `crunchbase_proxy()`'s own docstring
for why) come from one bounded Perplexity call per company
(`radar_market_signals.py`). `yoyRevenueGrowth` reuses
`radar_timing_signals.extract_growth_tier()`, already computed elsewhere
in this pipeline. Only `redditActivity` (5pts) has no wired source at all
-- no licensed vendor, no free API without new auth setup; it stays
`computed: False` indefinitely until one exists.

Every unwired signal reports `computed: False, raw: None` -- NEVER a
silent 0, which would read as "the market is cold on this company"
instead of "we haven't measured this yet." `score` is the sum of
contributions from whatever IS computed (so it grows as more signals come
online, never shrinks), then scaled by `timing_urgency_multiplier()` and
clamped to 100 (see that function's own docstring, and
`ROUND_ANNOUNCED_CEILING` below); `normalizedScore` rescales that same
(boosted, clamped) sum to the weight actually computed, for an
apples-to-apples read while `redditActivity` stays permanently unwired.

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


def _bucket_pct_change(pct):
    """Shared bucketing for the two Google-Trends-sourced rows
    (industryGrowth, googleTrendsSearchInterest) -- the rubric gives both
    the identical scale: >25%=10, 10-25%=7, flat +-10%=5, down >10%=0."""
    if pct is None:
        return None
    if pct > 25:
        return 10.0
    if pct >= 10:
        return 7.0
    if pct >= -10:
        return 5.0
    return 0.0


def industry_growth(trends_industry):
    """Signal 'industryGrowth'. `trends_industry`: google_trends.
    industry_growth()'s own return shape (`{"pctChange": float|None, ...}`),
    or None if it was never fetched -- Trends failed, or the company had no
    industry tags to check."""
    if not trends_industry:
        return None
    return _bucket_pct_change(trends_industry.get("pctChange"))


def google_trends_search_interest(trends_company):
    """Signal 'googleTrendsSearchInterest', same bucket scale as
    industryGrowth. `trends_company`: google_trends.company_search_interest()'s
    own return shape, or None."""
    if not trends_company:
        return None
    return _bucket_pct_change(trends_company.get("pctChange"))


def news_volume(value):
    """Signal 'newsVolume'. `value`: radar_market_signals.research()'s own
    `newsVolume` categorical read ("high"|"steady"|"low"), or None
    (unknown/not researched) -- None reads as missing, never as "low"."""
    return {"high": 10.0, "steady": 5.0, "low": 0.0}.get(value)


def step_up(value):
    """Signal 'stepUp'. APPROXIMATE -- the rubric's own bands need the
    actual step-up multiple (2.0x+/1.5-2.0x/etc), which a categorical
    up/flat/down research read can't distinguish. `up` scores 8, not 10,
    deliberately short of a maxed-out row -- "some step-up" is real
    evidence but weaker than a confirmed 2x+ multiple would be. `None`
    (most private companies never disclose two rounds' valuations
    publicly) is missing, never "flat"."""
    return {"up": 8.0, "flat": 4.0, "down": 1.0}.get(value)


def website_visits_growth(value):
    """Signal 'websiteVisitsGrowth'. APPROXIMATE, same reasoning as
    step_up() -- a categorical rising/flat/declining read can't claim the
    rubric's precise growth-rate bands, so `rising` scores 7, not 10.
    `None` (no public traffic report exists -- the common case) is
    missing, never "flat"."""
    return {"rising": 7.0, "flat": 4.0, "declining": 0.0}.get(value)


def crunchbase_proxy(public_momentum):
    """Signals 'crunchbaseGrowthScore'/'crunchbaseHeatScore'/
    'crunchbaseSurgeScore' -- ONE Perplexity-derived "public momentum" read
    (radar_market_signals.research()'s own `publicMomentum` field) feeds
    all three identically. Their real numbers only exist inside a paid,
    logged-in Crunchbase Pro session; a single search-grounded proxy can't
    honestly claim to distinguish 3 different proprietary indices, so it
    doesn't pretend to -- every caller of this function stamps a
    `proxyNote` on the entry (see compute()) so nobody downstream mistakes
    it for Crunchbase's own number. `None` (unknown/not researched) is
    missing, never a mid-scale guess."""
    return {"strong": 10.0, "moderate": 5.0, "weak": 0.0}.get(public_momentum)


def yoy_revenue_growth(growth_tier):
    """Signal 'yoyRevenueGrowth'. PROXY for the rubric's Sacra-sourced YoY
    figure -- radar_timing_signals.extract_growth_tier()'s "hypergrowth"
    (>=100% YoY or >=3x multiple or $50M+ ARR) maps to the rubric's own
    >100% YoY bucket (10); "strong" (>=$25M ARR or >=70% YoY) sits closest
    to its 75-100% bucket (7). `None` -- no growth language found in the
    screen -- is missing, not "0% growth": absence of a public number is
    the normal state for a private company, not evidence of decline."""
    if growth_tier == "hypergrowth":
        return 10.0
    if growth_tier == "strong":
        return 7.0
    return None


# Timing-urgency boost (Oscar, 2026-08-05): "shorter time [to the expected
# raise date] gets a higher heat score, but a fundamentally good score
# matters more" -- a bounded multiplicative BOOST applied to the rubric's
# own contribution total, not per-signal decay, and not the literal
# "expected date as denominator" division he described (which would blow
# up unboundedly as months_until_window -> 0, conflicting with his own
# "never over 100" requirement -- this is the intent translated into a
# bounded mechanism instead). Reuses the SAME months_until_window
# radar_hazard.baseline_hazard() buckets on and radar_schedule.next_scan_at()
# consumes -- passed in by the caller (radar_state.py), never re-derived
# here (this module stays a pure, no-I/O function, same convention as
# radar_hazard.compute()), so the three models never disagree about "how
# close."
MAX_URGENCY_BOOST = 1.15  # a starting number, not locked in -- retune once
# this has run against real companies. A +15% ceiling keeps a company
# that's only okay on fundamentals from ever reading as genuinely hot just
# because its window is near; it can only nudge a real number upward.

# Hard ceiling once an actual round has been detected as announced (not
# merely predicted) -- see radar_state._round_just_announced(). At that
# point the opportunity window has already closed; a high score would read
# as "still worth chasing" when it's actually "too late." Deliberately
# nonzero (not 0) so the number reads as "suppressed," not an error or a
# blank, and deliberately far below any plausible hot threshold.
ROUND_ANNOUNCED_CEILING = 10.0


def timing_urgency_multiplier(months_until_window):
    """1.0 (neutral) when there's no clock estimate at all (`None`) or the
    company is >=12 months out. Ramps linearly to MAX_URGENCY_BOOST as
    months_until_window falls from 12 to 0, then holds flat at
    MAX_URGENCY_BOOST once the predicted window has opened and passed (an
    overdue-but-not-yet-announced company stays maximally urgent -- same
    direction radar_hazard.baseline_hazard()'s own top bucket takes for a
    past-window company)."""
    if months_until_window is None or months_until_window >= 12:
        return 1.0
    if months_until_window <= 0:
        return MAX_URGENCY_BOOST
    return round(1.0 + (MAX_URGENCY_BOOST - 1.0) * (12 - months_until_window) / 12, 4)


def _entry(raw, weight, **extra):
    computed = raw is not None
    return {
        "computed": computed,
        "raw": raw,
        "weight": weight,
        "contribution": round(raw / 10 * weight, 3) if computed else None,
        **extra,
    }


def compute(fields, rates, as_of=None,
            market_research=None, trends=None, growth_tier=None,
            months_until_window=None, round_announced=False):
    """The pipeline radar_state.py calls, from inside the mandate-pass
    branch only.

    fields: {series, roundDate, tier1Firms}.
    rates: {headcountMomRate, openRolesMomRate, currentOpenRoles} --
    already-derived numbers, none of them raw series (see module
    docstring's "resolved inputs in" note).

    market_research: radar_market_signals.research()'s own return shape,
    or None -- not fetched, or the Perplexity call failed. Feeds
    newsVolume/stepUp/websiteVisitsGrowth and the shared crunchbase_proxy()
    read. trends: {"industry": google_trends.industry_growth()'s return
    shape|None, "company": google_trends.company_search_interest()'s
    return shape|None}, or None. growth_tier: radar_timing_signals.
    extract_growth_tier()'s own "hypergrowth"|"strong"|None. All four
    default to None/empty so a caller from before these params existed
    (including every pre-2026-08-05 test) gets IDENTICAL behavior to
    before -- those rows just read as missing, same as today.

    months_until_window: capital_clock's predicted-window-open minus
    today, in months (the SAME value radar_hazard.baseline_hazard() and
    radar_schedule.next_scan_at() already consume) -- feeds
    timing_urgency_multiplier(). `None` (default) keeps the multiplier a
    neutral 1.0, a no-op. round_announced: True once radar_state.
    _round_just_announced() detects a real round was recorded since the
    last scan -- caps score/normalizedScore at ROUND_ANNOUNCED_CEILING.
    Both default to values that reproduce today's exact output.

    Returns {signals: {key: {computed, raw, weight, contribution, ...}},
    score, normalizedScore, pointsAvailable, notComputed, computedAt,
    timingUrgencyMultiplier, monthsUntilWindow, roundAnnouncedFlag}."""
    signals = {}

    raw, band, context = raise_probability(fields.get("series"), fields.get("roundDate"), as_of)
    signals["raiseProbability"] = _entry(raw, WEIGHTS["raiseProbability"], band=band, context=context)

    raw = mom_employee_growth(rates.get("headcountMomRate"))
    signals["momEmployeeGrowth"] = _entry(raw, WEIGHTS["momEmployeeGrowth"], momRate=rates.get("headcountMomRate"))

    raw = job_posting_velocity(rates.get("openRolesMomRate"), rates.get("currentOpenRoles"))
    signals["jobPostingVelocity"] = _entry(raw, WEIGHTS["jobPostingVelocity"], momRate=rates.get("openRolesMomRate"))

    raw, n = tier1_investor_count(fields.get("tier1Firms"))
    signals["tier1InvestorCount"] = _entry(raw, WEIGHTS["tier1InvestorCount"], count=n)

    trends = trends or {}
    raw = industry_growth(trends.get("industry"))
    signals["industryGrowth"] = _entry(raw, WEIGHTS["industryGrowth"])

    raw = google_trends_search_interest(trends.get("company"))
    signals["googleTrendsSearchInterest"] = _entry(raw, WEIGHTS["googleTrendsSearchInterest"])

    market_research = market_research or {}
    raw = news_volume(market_research.get("newsVolume"))
    signals["newsVolume"] = _entry(raw, WEIGHTS["newsVolume"])

    raw = step_up(market_research.get("valuationStepUp"))
    signals["stepUp"] = _entry(raw, WEIGHTS["stepUp"])

    raw = website_visits_growth(market_research.get("websiteTrafficTrend"))
    signals["websiteVisitsGrowth"] = _entry(raw, WEIGHTS["websiteVisitsGrowth"])

    proxy_raw = crunchbase_proxy(market_research.get("publicMomentum"))
    for key in ("crunchbaseGrowthScore", "crunchbaseHeatScore", "crunchbaseSurgeScore"):
        signals[key] = _entry(
            proxy_raw, WEIGHTS[key],
            proxyNote="Perplexity public-momentum research -- not Crunchbase's own proprietary score",
        )

    raw = yoy_revenue_growth(growth_tier)
    signals["yoyRevenueGrowth"] = _entry(raw, WEIGHTS["yoyRevenueGrowth"])

    for key, weight in WEIGHTS.items():
        if key not in signals:
            # Not yet wired -- vendor/data gap, see module docstring. Never a
            # silent 0: computed=False is what tells the hub to render "not
            # measured" rather than a cold reading.
            signals[key] = _entry(None, weight)

    points_available = sum(s["weight"] for s in signals.values() if s["computed"])
    contribution_total = sum(s["contribution"] for s in signals.values() if s["computed"])
    not_computed = sorted(k for k, s in signals.items() if not s["computed"])

    urgency = timing_urgency_multiplier(months_until_window)
    round_announced = bool(round_announced)
    score = round(min(contribution_total * urgency, 100), 1) if points_available else None
    normalized_score = (
        round(min(contribution_total * urgency / points_available * 100, 100), 1)
        if points_available else None
    )
    if round_announced:
        # Hard override applied last, not a further multiplier -- "too
        # late" is a categorically different state from "less urgent," see
        # ROUND_ANNOUNCED_CEILING's own comment. The `signals` breakdown
        # above is left untouched so the evidence stays inspectable, same
        # convention as radar_hazard.py's distressFlag (a real, explicit
        # flag alongside a dampened-not-deleted number, never a silent
        # mutation).
        if score is not None:
            score = round(min(score, ROUND_ANNOUNCED_CEILING), 1)
        if normalized_score is not None:
            normalized_score = round(min(normalized_score, ROUND_ANNOUNCED_CEILING), 1)

    return {
        "signals": signals,
        "score": score,
        "normalizedScore": normalized_score,
        "pointsAvailable": points_available,
        "notComputed": not_computed,
        "computedAt": (as_of or date.today()).isoformat(),
        "timingUrgencyMultiplier": urgency,
        "monthsUntilWindow": months_until_window,
        "roundAnnouncedFlag": round_announced,
    }
