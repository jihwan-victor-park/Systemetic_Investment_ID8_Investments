"""Radar's capital clock (RADAR_PLAN.md Part III "Capital clock", Part IV
§4.1 baseline hazard). Companies raise when cash gets short -- this predicts
roughly when, from round size, round date, and current headcount.

Same pure-function idiom as rubric.py/radar_mandate.py: plain data in, plain
data out, no I/O. `compute()` returns the RAW (pre-seasonality) dates --
radar_schedule.py owns shifting predictedWindowOpen/contactByDate out of the
seasonal dead zones (RADAR_PLAN.md §6.3); radar_state.py is what calls both
in sequence and reconciles them (see that module's docstring for the exact
order, since alertAtDate has to be derived from the SHIFTED contactByDate,
not this module's raw one).

v1 uses flat current-headcount as the burn rate, not a trajectory -- there's
no headcount time series yet (that's Phase 4's job). This is a known,
stated approximation, not a bug: see the implementation plan's risk #4.
"""
from datetime import date, timedelta

# Seeded from RADAR_PLAN.md Part III's placeholder cost-per-head table.
# "Sign off on real portfolio numbers" is Part XII open decision #7 --
# treated as not-yet-blocking per that section's own wording ("or supply
# real portfolio numbers (better)"), so this ships as the working default.
# AI-heavy/hardware/deeptech ("high") intensity is deliberately the same
# cost class regardless of region in this v1 -- Part III's table gives NA
# and Europe both a "300-400k+" range for AI-heavy and doesn't split
# hardware/deeptech by region at all, so collapsing high-intensity to one
# number avoids inventing a Europe-specific figure the source table doesn't
# actually give.
COST_PER_HEAD = {
    ("NA", "high"): 350_000,
    ("NA", "medium"): 240_000,
    ("NA", "low"): 240_000,
    ("Europe", "high"): 350_000,
    ("Europe", "medium"): 155_000,
    ("Europe", "low"): 155_000,
}
DEFAULT_COST_PER_HEAD = 240_000  # unknown region -- falls back to the NA/medium figure

# The flat current-headcount burn rate (no revenue offset, no trajectory --
# see this module's own docstring) is a reasonable approximation for a
# normal-sized round, but breaks completely for an outsized round relative
# to current headcount: a $1.7B round against a 690-person org "computes" a
# 10-year runway and a predicted raise window in 2035 -- not wrong per the
# formula, just outside the range this crude a burn model has any business
# making a date prediction over. Oscar, 2026-07-29 ("the dates ... are so
# stupid"). Capping runway (not just the derived dates) keeps
# estCashOutDate/predictedWindowOpen/runwayMonths internally consistent
# rather than having runwayMonths say one thing and the dates say another.
# The cap is stated on the face of `assumptions` when it fires, same
# "carries its assumptions on the face of the card" principle
# RADAR_SIGNAL_ENGINE.md §3 argues for -- never a silently-adjusted number.
MAX_RUNWAY_MONTHS = 36

# Second, tighter cap for `capital_intensity == "high"` (AI-heavy/compute/
# hardware/deeptech/defense, classify_capital_intensity() below) -- Oscar,
# 2026-07-29: "ai startups are raising rounds so fast and so close to each
# other." Real research, not assumption (2026-07-29):
#   - The MEDIAN company's timeline has actually gotten LONGER, not shorter
#     -- seed-to-Series-A stretched to ~20mo, trending toward 28mo
#     (eqvista.com/ai-startup-fundraising-trends). MAX_RUNWAY_MONTHS=36
#     stays the right cap for medium/low intensity companies; the fix here
#     is deliberately narrow, not a blanket "AI is faster now" change.
#   - The companies that genuinely DO raise back-to-back are a specific,
#     identifiable tier: Anthropic (3 rounds/9mo), Cyera ($3B->$12B across
#     4 steps/18mo), Cursor ($100M->$2B ARR in 13mo) -- all compute-heavy,
#     all raising to FUND GROWTH, not because nominal cash is running low
#     (qubit.capital/blog/ai-startup-fundraising-trends,
#     fastaijobs.com/career-hacks/biggest-ai-funding-rounds-2026).
#   - Notably this fast tier's growth is REVENUE-driven, not headcount-
#     driven -- AI-native companies now run 2-5x higher ARR-per-employee
#     than traditional startups because AI automates work that used to
#     need hiring (runway.com/blog/burn-multiple-benchmarks-for-2026). That
#     means the existing hiring-based signal kernels (radar_hazard.py's F2
#     family) are structurally weak for exactly this tier -- a company
#     burning through compute toward $2B ARR can show flat headcount the
#     whole way. Capital intensity (already classified below, from
#     radarCategory/description keywords) is the input this pipeline
#     already has that actually tracks with the fast-raising tier; a
#     revenue-growth signal would be the more direct fix but there's no
#     reliable revenue field feeding this pipeline yet (Stage 1 screens do
#     estimate it, per-deal, in free text -- not wired in here).
MAX_RUNWAY_MONTHS_HIGH_INTENSITY = 18

# ── Cadence model (2026-07-29) ────────────────────────────────────────────
# The runway model above answers "when does cash get short." It cannot
# answer "when does a company raise on strength," which the 2026 research is
# unambiguous is how the fast tier operates -- Anthropic (3 rounds/9mo),
# Cyera ($3B->$12B over 4 steps/18mo), Cursor ($100M->$2B ARR/13mo) all
# raised with plenty of nominal runway left, because the raise funds growth
# rather than avoiding death. A runway-only model structurally predicts those
# companies LATE, which is the expensive direction to be wrong in.
#
# So: compute BOTH, take whichever opens first (see compute()). A company
# raising offensively doesn't wait for the cash-out clock; a company with no
# growth signal falls back to the runway clock unchanged.
#
# Baselines are research-grounded, not invented:
#   - Median seed->Series A is ~20 months and LENGTHENING toward 28
#     (eqvista.com/ai-startup-fundraising-trends) -- so the no-growth-signal
#     default must be ~20mo+, NOT the compressed number the "AI raises fast"
#     narrative would suggest. Applying the fast tier's cadence to everyone
#     is the mistake this table exists to avoid.
#   - The hypergrowth tier's observed spacing is ~4-9 months between rounds
#     (the three examples above). 8mo is the conservative end of that.
#   - "strong" sits between: real evidenced growth above the rubric's own
#     $25M ARR / 70% YoY bar, but not the compressed cycle.
# `growth_tier` comes from radar_timing_signals.extract_growth_tier(), which
# reads the Stage 1 findings TEXT rather than the fit rubric's score (see
# that module for why the score is the wrong input).
CADENCE_MONTHS_BY_GROWTH = {
    "hypergrowth": 8,
    "strong": 14,
    None: 22,  # mid-point of the observed 20->28mo median drift
}

# A process starts before it closes -- the window opens roughly a quarter
# before the expected next round date. Same 3-month convention the runway
# model already uses between predictedWindowOpen and contactByDate.
CADENCE_PROCESS_LEAD_MONTHS = 3


def cadence_window_open(round_date, growth_tier):
    """When the NEXT raise window plausibly opens, from round cadence alone
    -- independent of burn. `round_date`: the last round's close date.
    Returns a date, or None without a round_date to anchor to."""
    if not round_date:
        return None
    cadence = CADENCE_MONTHS_BY_GROWTH.get(growth_tier, CADENCE_MONTHS_BY_GROWTH[None])
    return _add_months(round_date, cadence - CADENCE_PROCESS_LEAD_MONTHS)

# Sector-keyword proxy only -- v1 has no reliable revenue/burn-efficiency
# data to test the plan's real "efficient SaaS, near-breakeven, revenue-
# funded" definition of "low" against. See the plan's risk #3: the scan-
# interval x1.4 modifier (radar_schedule.py) is what actually does the
# practical work "low intensity" is supposed to do here.
_INTENSITY_KEYWORDS = {
    "high": (
        "hardware", "deep tech", "deeptech", "defense", "defence",
        "semiconductor", "satellite", "aerospace", "robotics",
        "foundation model", "frontier model", "model training",
        "chip", "silicon",
    ),
    "low": (
        "saas", "software platform", "workflow software", "vertical software",
    ),
}


def classify_capital_intensity(radar_category, description):
    """"high" / "medium" (default) / "low", from a keyword match against
    radarCategory + description -- "high" checked first since a company can
    plausibly match both lists (e.g. "AI hardware"), and high-intensity is
    the costlier, more time-sensitive class to under-classify."""
    text = f"{radar_category or ''} {description or ''}".lower()
    if any(kw in text for kw in _INTENSITY_KEYWORDS["high"]):
        return "high"
    if any(kw in text for kw in _INTENSITY_KEYWORDS["low"]):
        return "low"
    return "medium"


def cost_per_head(region, capital_intensity, overrides=None):
    """`overrides`: an optional {"NA_high": 400000, ...} map -- Oscar,
    2026-07-29, in response to being told COST_PER_HEAD is an unvalidated
    placeholder: "build solutions for these." The real fix is real
    portfolio numbers, which no amount of code can manufacture; what code
    CAN do is make plugging them in not require a redeploy. Read from
    radarConfig/current.costPerHeadOverrides (same hub-editable doc
    watchFloor/hotThreshold already live in) via radar_state._get_
    cost_per_head_overrides() -- checked first, hardcoded COST_PER_HEAD
    stays the fallback for any (region, intensity) pair not overridden."""
    if overrides:
        key = f"{region}_{capital_intensity}"
        if key in overrides:
            return overrides[key]
    return COST_PER_HEAD.get((region, capital_intensity), DEFAULT_COST_PER_HEAD)


def _add_months(d, months):
    """Exact calendar-month shift (not a 30-day approximation) -- clamps the
    day when the target month is shorter (e.g. 31 Jan - 1 month -> 31 Dec is
    fine, but 31 Mar - 1 month -> last day of Feb, not an invalid date)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year, month):
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def compute(fields, headcount, as_of=None, growth_tier=None, cost_per_head_overrides=None):
    """fields: {roundSize, roundDate (ISO string or date), region ('NA'/
    'Europe'/'other'/None), radarCategory, description}. headcount: int or
    None (no Apollo data yet, or a lookup that failed). as_of: date,
    defaults to today (pass explicitly in tests for determinism).

    `growth_tier`: "hypergrowth" | "strong" | None, from
    radar_timing_signals.extract_growth_tier() -- drives the cadence model
    (see CADENCE_MONTHS_BY_GROWTH). None is the correct, common default and
    means "no growth evidence found," NOT "no growth": the cadence estimate
    then falls back to the research-backed ~22mo median and will normally
    lose to the runway estimate anyway.

    `cost_per_head_overrides`: see cost_per_head()'s own docstring -- real
    portfolio numbers, when available, without a redeploy.

    Returns the radar.clock dict (RADAR_PLAN.md Part VIII shape), with
    predictedWindowOpen/contactByDate/alertAtDate as RAW dates -- caller
    (radar_state.py) applies seasonality shifting before storing."""
    today = as_of or date.today()
    round_size = fields.get("roundSize")
    round_date_raw = fields.get("roundDate")
    round_date = _parse_date(round_date_raw)
    region = fields.get("region")
    capital_intensity = classify_capital_intensity(fields.get("radarCategory"), fields.get("description"))
    cph = cost_per_head(region, capital_intensity, cost_per_head_overrides)

    months_since_round = None
    if round_date:
        months_since_round = round((today - round_date).days / 30.44, 1)

    if not headcount or not round_size or not round_date:
        # Can't estimate burn/cash-out without all three -- return what we
        # do know rather than raising. This is the expected, common state
        # for a company that hasn't had an Apollo headcount lookup yet.
        #
        # The cadence model needs ONLY round_date, though, so a company with
        # no headcount is no longer a total blank: it still gets a real
        # window estimate off cadence alone (2026-07-29). This is a strict
        # improvement over the old behavior, which returned None and left
        # the hub showing "—" for anything Apollo hadn't resolved.
        missing = [n for n, v in (("headcount", headcount), ("roundSize", round_size), ("roundDate", round_date)) if not v]
        cadence_open = cadence_window_open(round_date, growth_tier)
        cadence_contact = _add_months(cadence_open, -3) if cadence_open else None
        return {
            "roundSize": round_size, "roundDate": round_date_raw,
            "headcount": headcount, "headcountCheckedAt": fields.get("headcountCheckedAt"),
            "costPerHead": cph, "capitalIntensity": capital_intensity,
            "estMonthlyBurn": None, "monthsSinceRound": months_since_round,
            "estCashOutDate": None, "runwayMonths": None,
            "predictedWindowOpen": cadence_open.isoformat() if cadence_open else None,
            "contactByDate": cadence_contact.isoformat() if cadence_contact else None,
            "alertAtDate": (cadence_contact - timedelta(weeks=6)).isoformat() if cadence_contact else None,
            "growthTier": growth_tier,
            "windowBasis": "cadence" if cadence_open else None,
            "assumptions": (
                f"incomplete -- missing {', '.join(missing)}, no burn estimate possible; "
                f"window from round cadence alone ({CADENCE_MONTHS_BY_GROWTH.get(growth_tier, CADENCE_MONTHS_BY_GROWTH[None])}mo "
                f"typical for growth tier {growth_tier or 'unknown'})"
                if cadence_open else
                f"incomplete -- missing {', '.join(missing)}, no burn estimate possible yet"
            ),
        }

    est_monthly_burn = round(headcount * cph / 12)
    capital_consumed = est_monthly_burn * months_since_round
    capital_remaining = max(round_size - capital_consumed, 0)
    runway_months_raw = round(capital_remaining / est_monthly_burn, 1) if est_monthly_burn else None
    runway_cap = MAX_RUNWAY_MONTHS_HIGH_INTENSITY if capital_intensity == "high" else MAX_RUNWAY_MONTHS
    runway_capped = runway_months_raw is not None and runway_months_raw > runway_cap
    runway_months = min(runway_months_raw, runway_cap) if runway_months_raw is not None else None
    est_cash_out_date = _add_months(today, round(runway_months)) if runway_months is not None else None
    runway_window_open = _add_months(est_cash_out_date, -12) if est_cash_out_date else None

    # Blend the two mechanisms: whichever window opens FIRST wins. A
    # hypergrowth company raising on strength (cadence) doesn't wait for its
    # cash-out clock (runway); a quiet company with no growth signal keeps
    # the runway answer unchanged, since its cadence estimate will be the
    # later of the two. `window_basis` records which one actually drove the
    # answer so the hub can show it rather than presenting a blended number
    # with no stated provenance.
    cadence_open = cadence_window_open(round_date, growth_tier)
    if runway_window_open and cadence_open:
        predicted_window_open = min(runway_window_open, cadence_open)
        window_basis = "cadence" if cadence_open < runway_window_open else "runway"
    else:
        predicted_window_open = runway_window_open or cadence_open
        window_basis = "runway" if runway_window_open else ("cadence" if cadence_open else None)

    contact_by_date = _add_months(predicted_window_open, -3) if predicted_window_open else None
    alert_at_date = contact_by_date - timedelta(weeks=6) if contact_by_date else None

    intensity_label = {"high": "high", "medium": "medium", "low": "low"}[capital_intensity]
    assumptions = (
        f"{region or 'unknown region'} {intensity_label}-intensity class @ ${cph:,}/head/yr; "
        f"gross burn (no revenue-offset data); flat current-headcount rate (no history yet); "
        f"headcount from Apollo{' ' + fields['headcountCheckedAt'] if fields.get('headcountCheckedAt') else ''}"
        + (f"; runway capped at {runway_cap}mo for date math (raw estimate {runway_months_raw:.0f}mo -- "
           + ("high capital-intensity companies raise on a much tighter cycle than nominal cash position "
              "suggests, see capital_clock.py's MAX_RUNWAY_MONTHS_HIGH_INTENSITY" if capital_intensity == "high"
              else "flat headcount-burn is unreliable this far out, round size is large relative to current headcount")
           + ")"
           if runway_capped else "")
        + (f"; window from {window_basis} model"
           + (f" (growth tier {growth_tier}, ~{CADENCE_MONTHS_BY_GROWTH[growth_tier]}mo typical round spacing -- "
              f"raising on strength ahead of the cash-out clock)" if window_basis == "cadence" else "")
           if window_basis else "")
    )

    return {
        "roundSize": round_size, "roundDate": round_date_raw,
        "headcount": headcount, "headcountCheckedAt": fields.get("headcountCheckedAt"),
        "costPerHead": cph, "capitalIntensity": capital_intensity,
        "estMonthlyBurn": est_monthly_burn, "monthsSinceRound": months_since_round,
        "estCashOutDate": est_cash_out_date.isoformat(), "runwayMonths": runway_months,
        "predictedWindowOpen": predicted_window_open.isoformat(),
        "contactByDate": contact_by_date.isoformat(),
        "alertAtDate": alert_at_date.isoformat(),
        # Which mechanism actually drove the window (§3's "every runway
        # figure carries its assumptions on the face of the card") -- a date
        # whose basis is hidden is not useful, and "runway" vs "cadence"
        # means genuinely different things about the company.
        "windowBasis": window_basis,
        "growthTier": growth_tier,
        "runwayWindowOpen": runway_window_open.isoformat() if runway_window_open else None,
        "cadenceWindowOpen": cadence_open.isoformat() if cadence_open else None,
        "assumptions": assumptions,
    }


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
