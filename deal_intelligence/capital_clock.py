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


def cost_per_head(region, capital_intensity):
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


def compute(fields, headcount, as_of=None):
    """fields: {roundSize, roundDate (ISO string or date), region ('NA'/
    'Europe'/'other'/None), radarCategory, description}. headcount: int or
    None (no Apollo data yet, or a lookup that failed). as_of: date,
    defaults to today (pass explicitly in tests for determinism).

    Returns the radar.clock dict (RADAR_PLAN.md Part VIII shape), with
    predictedWindowOpen/contactByDate/alertAtDate as RAW dates -- caller
    (radar_state.py) applies seasonality shifting before storing."""
    today = as_of or date.today()
    round_size = fields.get("roundSize")
    round_date_raw = fields.get("roundDate")
    round_date = _parse_date(round_date_raw)
    region = fields.get("region")
    capital_intensity = classify_capital_intensity(fields.get("radarCategory"), fields.get("description"))
    cph = cost_per_head(region, capital_intensity)

    months_since_round = None
    if round_date:
        months_since_round = round((today - round_date).days / 30.44, 1)

    if not headcount or not round_size or not round_date:
        # Can't estimate burn/cash-out without all three -- return what we
        # do know rather than raising. This is the expected, common state
        # for a company that hasn't had an Apollo headcount lookup yet.
        missing = [n for n, v in (("headcount", headcount), ("roundSize", round_size), ("roundDate", round_date)) if not v]
        return {
            "roundSize": round_size, "roundDate": round_date_raw,
            "headcount": headcount, "headcountCheckedAt": fields.get("headcountCheckedAt"),
            "costPerHead": cph, "capitalIntensity": capital_intensity,
            "estMonthlyBurn": None, "monthsSinceRound": months_since_round,
            "estCashOutDate": None, "runwayMonths": None,
            "predictedWindowOpen": None, "contactByDate": None, "alertAtDate": None,
            "assumptions": f"incomplete -- missing {', '.join(missing)}, no burn estimate possible yet",
        }

    est_monthly_burn = round(headcount * cph / 12)
    capital_consumed = est_monthly_burn * months_since_round
    capital_remaining = max(round_size - capital_consumed, 0)
    runway_months_raw = round(capital_remaining / est_monthly_burn, 1) if est_monthly_burn else None
    runway_capped = runway_months_raw is not None and runway_months_raw > MAX_RUNWAY_MONTHS
    runway_months = min(runway_months_raw, MAX_RUNWAY_MONTHS) if runway_months_raw is not None else None
    est_cash_out_date = _add_months(today, round(runway_months)) if runway_months is not None else None
    predicted_window_open = _add_months(est_cash_out_date, -12) if est_cash_out_date else None
    contact_by_date = _add_months(predicted_window_open, -3) if predicted_window_open else None
    alert_at_date = contact_by_date - timedelta(weeks=6) if contact_by_date else None

    intensity_label = {"high": "high", "medium": "medium", "low": "low"}[capital_intensity]
    assumptions = (
        f"{region or 'unknown region'} {intensity_label}-intensity class @ ${cph:,}/head/yr; "
        f"gross burn (no revenue-offset data); flat current-headcount rate (no history yet); "
        f"headcount from Apollo{' ' + fields['headcountCheckedAt'] if fields.get('headcountCheckedAt') else ''}"
        + (f"; runway capped at {MAX_RUNWAY_MONTHS}mo for date math (raw estimate {runway_months_raw:.0f}mo -- "
           f"flat headcount-burn is unreliable this far out, round size is large relative to current headcount)"
           if runway_capped else "")
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
