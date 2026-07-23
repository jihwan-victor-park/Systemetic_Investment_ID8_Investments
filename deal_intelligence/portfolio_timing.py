"""Deterministic 'probability of next raise' base rate for the Stage 0
Portfolio Fit pass -- the timing metric, computed in plain code with no LLM
call, exactly like portfolio_prefilter.py's checks.

prompts/portfolio_fit_rubric.md's "Probability of next round" section splits
that estimate into two layers: (1) this deterministic base rate, supplied to
the model inline, and (2) a qualitative overlay the model nudges it with from
its one paid research pass. This module is layer 1 only -- it never calls out
to anything, so the timing signal is reproducible and auditable on its own,
independent of whatever the model does with it.

The model:
  months since the company's last recorded financing (`latestRoundDate`),
  compared against the stage-typical cadence for its `latestRound`:
    - pre-Series-C rounds reprice roughly every 18-24 months
    - Series C / D+ rounds roughly every 24-30 months
  (both windows straight from the rubric). A company past its window carries a
  higher 3-month raise base rate; one that just closed carries a low one.

Output is a `TimingBaseRate`: the band (low/medium/high/imminent, same scale
as the model's own raise_probability_band so the overlay is an apples-to-
apples nudge), plus a human-readable `context` string that is what actually
gets injected into the prompt -- it spells out the months-elapsed and the
window so the model understands the baseline it's adjusting, rather than being
handed a bare label.

Deliberately conservative at the top end: the deterministic layer never
returns `imminent`. Reaching >60% 3-month probability requires a real
qualitative catalyst (a "in talks to raise" report, a CFO hire) -- that's the
model's overlay to add, not something months-elapsed alone can establish. The
worst-case "wildly overdue" case tops out at `high` and says so, since being
long past cadence is just as often a distress signal as an imminent-raise one.
"""
from dataclasses import dataclass
from datetime import date
import re


# Cadence windows (months between rounds), straight from the rubric. Keyed by
# the coarse stage bucket _classify_stage() returns.
CADENCE_MONTHS = {
    "pre_c": (18, 24),
    "c_plus": (24, 30),
}

# Default window when the round string doesn't classify -- use the (wider,
# more conservative) pre-C window rather than guessing late-stage, since an
# unrecognized/blank round is more often an early/odd one than a Series F.
_DEFAULT_BUCKET = "pre_c"


def _classify_stage(latest_round):
    """Maps a PitchBook `latestRound` string to "pre_c" | "c_plus" | None.

    Real values in this dataset (see portfolio_prefilter survey) look like
    'Series A', 'Series B1', 'Series C', 'Series D'..'Series H', 'Seed Round
    (2nd Round)', 'Early Stage VC (3rd Round)', 'Later Stage VC (8th Round)',
    'Buyout/LBO (1st Round)'. Returns None only when there's genuinely nothing
    to classify (blank/unparseable), so the caller can say "stage unknown"
    rather than silently bucketing it.
    """
    if not latest_round:
        return None
    r = latest_round.strip().lower()

    # Series letter -- C or later is c_plus, A/B (and any A1/B2 style) is pre_c.
    m = re.search(r"series\s+([a-h])", r)
    if m:
        return "c_plus" if m.group(1) >= "c" else "pre_c"

    if "seed" in r or "angel" in r or "pre-seed" in r:
        return "pre_c"
    if "early stage vc" in r:
        return "pre_c"
    if "later stage vc" in r:
        return "c_plus"
    # Buyout/LBO, growth/PE, etc. -- past the venture cadence entirely; treat
    # like a late round for cadence purposes.
    if any(k in r for k in ("buyout", "lbo", "growth", "pe ", "private equity", "mezzanine")):
        return "c_plus"
    return None


@dataclass
class TimingBaseRate:
    band: str            # low | medium | high  (never imminent -- see module docstring)
    months_since: float | None   # months since latestRoundDate, None if no date on file
    stage_bucket: str | None     # "pre_c" | "c_plus" | None
    context: str         # the human-readable string injected into the prompt


def _months_between(earlier, later):
    """Whole-ish months between two dates, as a float (keeps the fractional
    part so a company 5.5 months out isn't rounded to a different band edge)."""
    return (later.year - earlier.year) * 12 + (later.month - earlier.month) + (later.day - earlier.day) / 30.0


def _parse_date(s):
    """latestRoundDate is ISO 'YYYY-MM-DD' in this dataset. Returns a date or
    None (never raises) -- a malformed/partial date is treated as no date."""
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(s).strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def base_rate(company, as_of=None):
    """company: one portfolio dict (needs `latestRound`, `latestRoundDate`).
    as_of: reference date for "months since" -- defaults to today (this runs
    locally against the seed JSON, so real wall-clock today is correct); made
    injectable so tests are deterministic.

    Returns a TimingBaseRate. Falls back to a band of 'medium' with an explicit
    "no financing date on file" context when latestRoundDate is missing (~5%
    of passing rows) -- the model then leans entirely on its qualitative
    overlay rather than a fabricated baseline.
    """
    as_of = as_of or date.today()
    latest_round = company.get("latestRound") or ""
    bucket = _classify_stage(latest_round)
    round_label = latest_round or "unknown round"

    round_date = _parse_date(company.get("latestRoundDate"))
    if round_date is None:
        return TimingBaseRate(
            band="medium",
            months_since=None,
            stage_bucket=bucket,
            context=(f"No last-financing date on file (last round: {round_label}). "
                     f"No deterministic timing baseline computable -- set the band from "
                     f"qualitative signal alone, defaulting to medium if none exists."),
        )

    months = round(_months_between(round_date, as_of), 1)
    lo, hi = CADENCE_MONTHS.get(bucket or _DEFAULT_BUCKET)
    bucket_desc = {"pre_c": "pre-Series-C", "c_plus": "Series C/D+"}.get(bucket, "unclassified stage (assuming pre-Series-C cadence)")

    # Piecewise on where months-elapsed sits relative to this stage's [lo, hi]
    # cadence window. Edges chosen so "just closed" is clearly low and "past
    # the window" is clearly high, with the typical window itself as medium.
    if months < 0:
        # latestRoundDate in the future vs as_of -- a data error, not a real
        # state. Treat as just-closed rather than trusting the negative.
        band, why = "low", "last financing date is in the future (data error) -- treated as just closed"
    elif months < lo * 0.5:
        band, why = "low", f"only {months:.0f}mo since last round, well inside the {lo}-{hi}mo {bucket_desc} cadence"
    elif months < lo:
        band, why = "low", f"{months:.0f}mo since last round, still short of the {lo}-{hi}mo {bucket_desc} cadence"
    elif months < hi:
        band, why = "medium", f"{months:.0f}mo since last round, inside the typical {lo}-{hi}mo {bucket_desc} cadence"
    elif months < hi * 1.4:
        band, why = "high", f"{months:.0f}mo since last round, past the {lo}-{hi}mo {bucket_desc} cadence -- due"
    else:
        band, why = "high", (f"{months:.0f}mo since last round, well past the {lo}-{hi}mo {bucket_desc} cadence "
                             f"-- overdue (could equally signal difficulty raising)")

    context = (f"Deterministic base rate: {band}. {why.capitalize()}. "
               f"This is a starting point from timing alone -- adjust up or down for qualitative signal.")
    return TimingBaseRate(band=band, months_since=months, stage_bucket=bucket, context=context)
