"""Radar's hazard model (RADAR_SIGNAL_ENGINE.md §4 "The prediction model:
hazard, not score"). Replaces a flat additive score with peak-effect-delay
kernels -- a signal is worth more months after it fires than the week it
appears, and the model naturally forgets a company that's gone quiet,
because an inactive signal simply isn't in the product at all.

Same pure-function idiom as rubric.py/radar_mandate.py/capital_clock.py/
radar_schedule.py: plain data in, plain data out, no I/O, no Firestore.
radar_state.py is the only caller and owns resolving each signal's
months-since-event from its own stored dates before calling compute() here.

Every prior in SIGNAL_KERNELS and baseline_hazard() is hand-set from
RADAR_SIGNAL_ENGINE.md §4.1/§3 and stated as such in the doc itself --
"wrong in detail," to be replaced by fitted coefficients once §9's
calibration loop has enough closed rounds to work with. Stating them
explicitly here is what makes them correctable.
"""
import math

# Mirrors RADAR_SIGNAL_ENGINE.md §4.1's table -- peak month, peak multiplier,
# rise/fade shape. Only signals this pass can actually detect are wired
# (finance-role/corp-dev postings via radar_jobs.py, headcount growth/decline
# via radar_signal_series.py); the rest of the doc's table (press rumor,
# board member added, founder cadence, etc.) stays undefined here until
# their sensors exist -- a legible, extendable table, not a guess disguised
# as a smaller one.
#
# `fade_month` is this module's own addition (the doc names a shape in
# words -- "sharp, fades by 6mo" -- this is that shape as a number).
# `concurrent: True` signals (headcount growth/decline) are re-evaluated
# fresh every scan rather than aged from a stored event date -- the caller
# always passes monthsSinceEvent=0 for these, which is what "holds flat
# while true, drops out the scan it stops being true" means in practice;
# `fade_month` on those two rows is unused (kept for schema consistency).
SIGNAL_KERNELS = {
    # ── F2: organizational preparation (hiring composition) ──────────────
    # Sensed by radar_jobs.py + headcount series. NOTE (2026-07-29 research):
    # this family structurally UNDER-detects AI-native companies, which hit
    # 2-5x higher ARR-per-employee because AI replaces the hiring that used
    # to signal scaling -- see radar_timing_signals.py's research grounding.
    # F3 below is the higher-value family for ID8's AI mandate.
    "senior_finance_role":  {"peak_month": 4, "fade_month": 12, "peak_mult": 2.5, "family": "F2"},
    "corp_dev_role":        {"peak_month": 2, "fade_month": 6,  "peak_mult": 2.2, "family": "F2"},
    "headcount_growth_40":  {"peak_month": 0, "fade_month": 0,  "peak_mult": 1.6, "family": "F2", "concurrent": True},
    "senior_gtm_burst":     {"peak_month": 3, "fade_month": 9,  "peak_mult": 1.4, "family": "F2"},
    "recruiter_hiring":     {"peak_month": 3, "fade_month": 9,  "peak_mult": 1.3, "family": "F2"},

    # ── F3: growth momentum (2026-07-29) ─────────────────────────────────
    # Extracted from Stage 1 screen findings by radar_timing_signals.py, NOT
    # from the fit rubric's revenue_growth SCORE -- that score reads 2 ("no
    # disclosed figure") for undisclosed hypergrowth, which would invert the
    # signal on exactly the companies this family exists to catch. See that
    # module's docstring for the Paper/25x-ARR proof case.
    #
    # Multipliers sit between F2's hiring signals and F4's process leakage:
    # a 25x ARR ramp is stronger evidence of an imminent raise than a CFO
    # hire (the research tier raising back-to-back does so on growth, not
    # preparation) but weaker than a visibly-running process. Slow fade
    # (12mo) because growth momentum persists in a way an event does not.
    "hypergrowth_revenue":   {"peak_month": 2, "fade_month": 12, "peak_mult": 3.0, "family": "F3"},
    "strong_revenue_growth": {"peak_month": 2, "fade_month": 12, "peak_mult": 1.8, "family": "F3"},

    # ── F4: process leakage ──────────────────────────────────────────────
    # The raise is already visible/in motion. §2's table puts this family at
    # "very high" precision, 0-3mo lead. Peaks immediately and fades fast --
    # a "term sheets in hand" read is worthless nine months later. Set below
    # the doc's x6.0 for a hard press leak ("in talks to raise"): this is
    # inferred from our own research pass, which is good evidence but not the
    # same as a reporter confirming a live process.
    "process_visible":      {"peak_month": 0, "fade_month": 4,  "peak_mult": 4.0, "family": "F4"},

    # ── F1-adjacent: insider conviction ──────────────────────────────────
    # Existing Tier-1 investors confirmed following on -- parties with an
    # information advantage committing more capital. Flat-ish while true,
    # same shape as the doc's "existing lead closed a new fund" row.
    "insiders_following":   {"peak_month": 0, "fade_month": 12, "peak_mult": 1.5, "family": "F1"},

    # ── Negative / distress ──────────────────────────────────────────────
    # §2.2's distress discriminator, as an explicit branch (never an
    # emergent weighting). `defensive_raise` is the subtle one: a company
    # raising defensively probably IS raising, but it is not an opportunity
    # -- the doc is explicit that distress should LOWER escalation, so this
    # both damps the multiplier and sets distressFlag for the caller.
    "headcount_decline_10": {"peak_month": 0, "fade_month": 0,  "peak_mult": 0.4, "family": "negative", "concurrent": True},
    "layoffs":              {"peak_month": 0, "fade_month": 6,  "peak_mult": 0.6, "family": "negative"},
    "defensive_raise":      {"peak_month": 0, "fade_month": 9,  "peak_mult": 0.7, "family": "negative"},
}

# Families whose presence means "this company is in trouble", not "this
# company is about to raise on strength" -- surfaced as `distressFlag` so
# the hub and the partner brief can refuse to escalate them as
# opportunities regardless of what the composite multiplier says (§2.2:
# "Flag, never escalate as an opportunity").
DISTRESS_KERNELS = ("headcount_decline_10", "layoffs", "defensive_raise")

COMPOSITE_CAP = 8.0  # §4.2 "composite cap"


def baseline_hazard(months_until_window):
    """h₀: baseline annualized hazard from the capital clock (§3), the only
    always-present term. Bucketed off `months_until_window` -- the same
    quantity radar_state.py already derives from capital_clock.py's
    predictedWindowOpen and passes to radar_schedule.next_scan_at() -- so
    this reuses that computation rather than re-deriving runway itself, and
    the bucket edges intentionally match radar_schedule.base_interval_weeks'
    own breakpoints (>12 / 8-12 / 5-8 / 3-5 critical zone / <3) so the two
    modules never disagree about what "far out" vs "critical zone" means.

    `None` (no clock estimate yet -- no headcount lookup has succeeded) uses
    §1's stated base rate for an unscored company (~5-8% in 90 days, i.e.
    ~20-30% annualized) rather than 0, since absence of a clock reading is
    not evidence the company is far from raising."""
    if months_until_window is None:
        return 0.20
    if months_until_window > 12:
        return 0.15
    if months_until_window >= 8:
        return 0.35
    if months_until_window >= 5:
        return 0.55
    if months_until_window >= 3:
        return 0.85
    if months_until_window >= 0:
        return 1.10
    return 1.30  # past the predicted window -- elevated baseline; distress
    # signals pull this back down via a sub-1.0 composite multiplier, not by
    # capping h0 itself (see §2.2's distress discriminator).


def signal_multiplier(kernel, months_since_event):
    """One signal's multiplier at its current age. Triangular: rises
    linearly from 1.0 (no effect) at t=0 to `peak_mult` at `peak_month`,
    holds nothing extra, then fades linearly back to 1.0 by `fade_month`.
    `peak_month == 0` (an immediate-effect signal, or a concurrent signal
    always called with monthsSinceEvent=0) returns peak_mult outright at
    t=0 rather than a degenerate 0/0 rise.

    `months_since_event=None` (never detected) or negative (shouldn't
    happen, defends anyway) returns 1.0 -- no effect, matching "inactive
    signals aren't in the product at all"."""
    if months_since_event is None or months_since_event < 0:
        return 1.0
    peak_month, peak_mult = kernel["peak_month"], kernel["peak_mult"]
    if months_since_event <= peak_month:
        if peak_month == 0:
            return peak_mult
        return 1.0 + (peak_mult - 1.0) * (months_since_event / peak_month)
    fade_month = kernel["fade_month"]
    if months_since_event >= fade_month:
        return 1.0
    span = fade_month - peak_month
    progress = (months_since_event - peak_month) / span
    return peak_mult - (peak_mult - 1.0) * progress


def combine_multipliers(multipliers):
    """Product of every active signal's resolved multiplier, capped at
    COMPOSITE_CAP (§4.2). No entry for an inactive signal -- there is no
    "1.0 baseline" placeholder to include; this is `Πᵢ` over active i only,
    same as the doc's own formula in §4."""
    product = 1.0
    for m in multipliers:
        product *= m
    return min(product, COMPOSITE_CAP)


def hazard_p90(h0_annualized, composite_multiplier):
    """P(raise within 90 days) = 1 − exp(−h0 × composite × 0.25) -- §4's
    formula, 0.25 = 90/360 of a year."""
    return 1 - math.exp(-h0_annualized * composite_multiplier * 0.25)


def hazard_p180(h0_annualized, composite_multiplier):
    """Same shape as hazard_p90, 0.5 = 180/360 of a year -- §8's action
    trigger is P180, not P90 (contact-by lead time needs the longer
    horizon; P90 stays the urgency read)."""
    return 1 - math.exp(-h0_annualized * composite_multiplier * 0.5)


def heat_points(p180):
    """P180 rescaled to a 0-100 number (Oscar, 2026-07-29) -- roughly "P180
    as a percent," which is what makes a threshold like "hot at 80+"
    legible at a glance. This is display sugar; the model's real unit is
    probability."""
    return round(p180 * 100, 1)


def two_family_guardrail(active_families):
    """§4.2 rule 1: 'hot' requires active signals from ≥2 distinct families.
    Four job postings is one signal (family F2) -- this pass only wires F2
    sensors, so this deliberately returns False until F1/F3/F4/F5 also
    contribute active (non-baseline) signals. Surfaced as `twoFamilyPass` on
    the written hazard doc as confidence-relevant data, not (this pass) used
    to hard-block heatPoints/hot display -- see radar_state.py's docstring
    on why."""
    return len(set(active_families)) >= 2


def confidence_level(active_families, newest_signal_age_months):
    """§4.3: confidence is reported separately from probability -- a 30%
    from one stale sensor means less than a 30% from multiple fresh,
    independent families. Simplified to what's computable this pass (only
    F2 sensor coverage exists, so "sensor coverage of this company" isn't
    yet a separate axis from family count)."""
    n = len(set(active_families))
    if n == 0:
        return "low"
    if n >= 2:
        return "high"
    if newest_signal_age_months is not None and newest_signal_age_months <= 6:
        return "medium"
    return "low"


def compute(h0_annualized, active_signals):
    """The pipeline radar_state.py actually calls -- one function, same
    convention as capital_clock.compute()/radar_mandate.screen(), rather
    than five sub-functions wired by hand at every call site.

    active_signals: [{"key": <a SIGNAL_KERNELS key>, "monthsSinceEvent":
    float|None}, ...] -- radar_state.py resolves each signal's age from its
    own stored first-seen date before calling this (or passes
    monthsSinceEvent=0 for a `concurrent` kernel, re-evaluated fresh every
    scan rather than aged). Only signals currently active belong in this
    list at all.

    Returns {p90, p180, heatPoints, compositeMultiplier, familiesActive,
    twoFamilyPass, confidence} -- the shape radar_state.py writes onto
    radar.hazard, plus computedAt stamped by the caller."""
    multipliers = []
    families = []
    ages = []
    distress = []
    for sig in active_signals:
        key = sig["key"]
        kernel = SIGNAL_KERNELS[key]
        age = sig.get("monthsSinceEvent")
        multipliers.append(signal_multiplier(kernel, age))
        families.append(kernel["family"])
        if key in DISTRESS_KERNELS:
            distress.append(key)
        if age is not None:
            ages.append(age)

    composite = combine_multipliers(multipliers)
    p90 = hazard_p90(h0_annualized, composite)
    p180 = hazard_p180(h0_annualized, composite)

    return {
        "p90": round(p90, 4),
        "p180": round(p180, 4),
        "heatPoints": heat_points(p180),
        "compositeMultiplier": round(composite, 3),
        "familiesActive": sorted(set(families)),
        "twoFamilyPass": two_family_guardrail(families),
        "confidence": confidence_level(families, min(ages) if ages else None),
        # §2.2: "overdue" is equally a sign of imminent raise and of dying,
        # and treating the second as the first is how a partner's attention
        # gets spent on a corpse. An explicit flag, never inferred from the
        # score alone.
        "distressFlag": bool(distress),
        "distressSignals": sorted(set(distress)),
    }
