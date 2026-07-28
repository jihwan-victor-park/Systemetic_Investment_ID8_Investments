"""Radar's scan scheduling (RADAR_PLAN.md Part VI). Computes `nextScanAt` --
when a Radar company should next be looked at -- from the fixed opening
sequence (Scan 1 @ T+4mo, Scan 2 @ T+6mo from round close), then an adaptive
interval based on how many months remain until the predicted raise window
opens, then seasonality (never land a scan in a dead zone; the two mandatory
calendar sweeps act as a ceiling on how late `nextScanAt` can drift).

v1 only implements the DETERMINISTIC slice of §6.2's modifier table --
capital-intensity (x0.7/x1.4) and the "any preparation signal -> 6wk floor"
rule. The momentum/quiet/distress modifiers are explicitly excluded: they
need real signal history from Phase 3/4 sensors, which don't exist yet in
this build. `preparation_signal_active` is accepted as a parameter for
forward compatibility but every v1 caller passes False (nothing yet sets
it to True).

Same pure-function idiom as rubric.py/radar_mandate.py/capital_clock.py: no
I/O, unit-testable with zero mocking.
"""
from datetime import date, timedelta

# §6.3's two dead zones, as (month, day) start/end pairs, plus where a
# shifted date lands on each side. Landing points deliberately coincide with
# the mandatory sweep dates below (Sept 5 / Jan 12) where the plan's own
# wording lines up ("push a late-December scan to the second week of
# January" = the Jan sweep date exactly) -- one fewer magic date to keep in
# sync.
_AUG_ZONE = {"start": (7, 25), "end": (8, 31), "later": (9, 5), "earlier": (7, 15)}
_YEAR_END_ZONE = {"start": (12, 15), "end": (1, 6), "later": (1, 12), "earlier": (12, 5)}

MANDATORY_SWEEPS = ((9, 5), (1, 12))  # ~5 Sep, ~12 Jan -- every company, regardless of nextScanAt


def shift_out_of_dead_zone(d, direction):
    """direction='later' for predicted dates (RADAR_PLAN.md §6.3 rule a) or
    'earlier' for contact deadlines / scan dates (rule b) -- never the
    other way. Returns `d` unchanged if it isn't in a dead zone."""
    month, day = d.month, d.day
    if (month, day) >= _AUG_ZONE["start"] and (month, day) <= _AUG_ZONE["end"]:
        target_month, target_day = _AUG_ZONE["later" if direction == "later" else "earlier"]
        return date(d.year, target_month, target_day)
    if (month, day) >= _YEAR_END_ZONE["start"]:
        if direction == "later":
            return date(d.year + 1, *_YEAR_END_ZONE["later"])
        return date(d.year, *_YEAR_END_ZONE["earlier"])
    if (month, day) <= _YEAR_END_ZONE["end"]:
        if direction == "later":
            return date(d.year, *_YEAR_END_ZONE["later"])
        return date(d.year - 1, *_YEAR_END_ZONE["earlier"])
    return d


def next_mandatory_sweep(today):
    """The next ~5 Sep or ~12 Jan on or after `today`."""
    candidates = []
    for month, day in MANDATORY_SWEEPS:
        d = date(today.year, month, day)
        if d < today:
            d = date(today.year + 1, month, day)
        candidates.append(d)
    return min(candidates)


def _add_months(d, months):
    """Exact calendar-month shift, clamped for short target months -- same
    logic as capital_clock._add_months, duplicated rather than imported:
    this module stays self-contained pure logic with no cross-module
    coupling, same convention radar_mandate.py's classify_region uses."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, (date(year, month + 1, 1) - timedelta(days=1)).day if month != 12 else 31)
    return date(year, month, day)


def opening_sequence_scan(round_date, scan_count):
    """Scan 1 @ T+4mo (scan_count == 0), Scan 2 @ T+6mo (scan_count == 1).
    Returns None once both have fired (scan_count >= 2) -- caller falls
    through to the adaptive interval -- or if there's no round_date at all
    to anchor the sequence to."""
    if not round_date or scan_count >= 2:
        return None
    months = 4 if scan_count == 0 else 6
    return _add_months(round_date, months)


def base_interval_weeks(months_until_window):
    """RADAR_PLAN.md §6.2's base interval table. `None` (unknown window,
    e.g. no headcount yet for the capital clock) defaults to the widest
    (safest, cheapest) interval rather than guessing tight."""
    if months_until_window is None or months_until_window > 12:
        return 16  # > 12 months -> 4 months
    if months_until_window >= 8:
        return 12  # 8-12 months -> 3 months
    if months_until_window >= 5:
        return 8  # 5-8 months -> 8 weeks
    if months_until_window >= 3:
        return 6  # 3-5 months -> 6 weeks, the critical zone
    return 4  # < 3 months -> 4 weeks


def apply_modifiers(weeks, capital_intensity, preparation_signal_active=False):
    """x0.7 high-intensity / x1.4 low-intensity, then the "any preparation
    signal active" 6-week cap (§6.2's "floor of 6 weeks" -- worded as a
    floor in the plan but meaning the interval should not run WIDER than 6
    weeks once a finance role or similar has appeared, i.e. it keeps
    re-checks "reasonably tight"; implemented here as `min(weeks, 6)` to
    match that stated intent). Always in v1: `preparation_signal_active` is
    False at every real call site -- no sensor exists yet to ever set it
    True -- so this branch is currently dead in production but kept
    implemented and tested for when Phase 3/4 sensors land.

    Bounds: minimum 4 weeks, maximum 4 months (16 weeks), per §6.2."""
    if capital_intensity == "high":
        weeks = weeks * 0.7
    elif capital_intensity == "low":
        weeks = weeks * 1.4
    if preparation_signal_active:
        weeks = min(weeks, 6)
    weeks = max(4, min(weeks, 16))
    return round(weeks)


def next_scan_at(last_scan_at, round_date, scan_count, months_until_window,
                  capital_intensity, today=None, preparation_signal_active=False):
    """Returns (date, reason). Folds the two mandatory sweep dates in as a
    CEILING (min(adaptive_date, next_sweep)) rather than Part X's literal
    "every company, unconditionally, on that date" -- same practical
    outcome at Radar's current population size, simpler than a second
    unconditional code path in the scan runner. See the implementation
    plan's risk #5."""
    today = today or date.today()

    opening = opening_sequence_scan(round_date, scan_count)
    if opening is not None:
        candidate = opening
        reason = f"opening sequence -- scan {scan_count + 1} of 2, T+{4 if scan_count == 0 else 6} months from round close"
    else:
        weeks = apply_modifiers(base_interval_weeks(months_until_window), capital_intensity, preparation_signal_active)
        base_date = last_scan_at or today
        candidate = base_date + timedelta(weeks=weeks)
        window_desc = f"window ~{months_until_window:.1f}mo out" if months_until_window is not None else "window unknown"
        intensity_desc = {"high": " x0.7 high capital intensity", "low": " x1.4 low capital intensity", "medium": ""}[capital_intensity]
        reason = f"{weeks} weeks -- {window_desc}{intensity_desc}"

    sweep = next_mandatory_sweep(today)
    if sweep < candidate:
        candidate = sweep
        reason = f"mandatory sweep ({sweep.isoformat()})"

    shifted = shift_out_of_dead_zone(candidate, "later")
    if shifted != candidate:
        reason += f", shifted off {candidate.isoformat()} to avoid a dead zone"
        candidate = shifted

    return candidate, reason
