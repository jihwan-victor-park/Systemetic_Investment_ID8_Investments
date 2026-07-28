"""The Portfolio Fit rubric (v1, July 2026) -- mirrors rubric.py's pattern
(PARAMS as single source of truth, spliced into prompts/portfolio_fit_rubric.md
at its `<!-- ANCHORS: <key> -->` markers) but for the lighter-than-Stage-1 pass
over partner VC portfolio companies. See prompts/portfolio_fit_rubric.md for
the full "why this isn't Stage 1 with fewer dimensions" reasoning.

Two structural differences from rubric.py, both deliberate:

1. No subcategories. Each dimension here is scored with ONE holistic 1-4 call
   plus one evidence sentence, not itemized into 2-10 fixed subcategories the
   way Stage 1's PARAMS are. That's the actual "lighter" lever -- keeping the
   per-company research/output small enough to run at ~1,000-2,000-company
   scale inside a $10-20 budget, not merely fewer dimensions.
2. Geography is NOT one of these dimensions and carries no hard-auto-pass
   logic here. hqLocation is already structured PitchBook data on every
   portfolio row -- excluding on it belongs in the deterministic Phase 1
   filter (plain code, run before any company reaches this prompt), not in a
   paid research call re-deriving a fact already sitting in a database field.
   Likewise, businessStatus (Acquired/IPO/Out of Business) is a deterministic
   exclusion upstream, not scored here.

Not built yet, out of scope for this file: the Phase 1 deterministic filter
itself, the Phase 0 enrichment script, and the Phase 2 pipeline endpoint that
would actually call this rubric against portfolio rows. This file and
portfolio_fit.md are the prompting/scoring-logic piece only.
"""
import os
import re

_PROMPTS = os.path.join(os.path.dirname(__file__), "prompts")

# Each dimension: key, label, weight, and its holistic 1-4 anchor table.
# Unlike rubric.py's PARAMS, there is no "subcategories" list -- the anchor
# table below IS the dimension's scoring rubric.
PARAMS = [
    {
        "key": "ai_thesis_fit",
        "label": "AI / Thesis Fit",
        "anchors": {
            1: "No meaningful AI component -- a thin wrapper calling a third-party foundation-model API with no differentiation. Hard auto-pass.",
            2: "Some AI usage but not clearly structural to the moat -- plausible AI framing without evidenced depth (no stated fine-tuning, proprietary dataset, or defensible pipeline).",
            3: "AI is a genuine, evidenced part of the product's value -- real fine-tuning, a proprietary dataset, or meaningful engineering investment, though not necessarily hard to replicate.",
            4: "AI is the core, defensible moat -- proprietary architecture or a demonstrated data flywheel that is genuinely hard to replicate with a foundation-model update.",
        },
    },
    {
        "key": "founder_team_quality",
        "label": "Founder / Team Quality",
        "anchors": {
            1: "Verified negative history (litigation, fraud allegations, regulatory action, confirmed toxic-culture signals). Hard auto-pass.",
            2: "Background genuinely unverifiable after a real search effort, or the team has some operating experience but no scaled outcome and no deep domain authority.",
            3: "Credible team -- meaningful domain authority or an elite pedigree, reasonable functional coverage, no red flags found.",
            4: "Strong, verified pedigree -- serial founder(s) with a prior exit or a company scaled to $100M+ ARR, deep domain authority, clean functional coverage.",
        },
    },
    {
        "key": "fundamentals_scale_ceiling",
        "label": "Fundamentals & Scale Ceiling",
        "anchors": {
            1: "Confirmed weak fundamentals for stage (real, disclosed sub-scale revenue/growth), or a business that structurally cannot become a venture-scale outcome even in a strong case.",
            2: "Fundamentals undisclosed and no usable triangulation exists -- a plausible but unverified scale ceiling.",
            3: "Fundamentals (confirmed or credibly [ESTIMATED] via triangulation) support a large outcome -- real revenue/growth signal, or a convincing market-size-plus-moat case for a $1B+ ceiling.",
            4: "Strong confirmed fundamentals and a clearly evidenced path to a $1B+ outcome -- durable moat, large TAM, real traction.",
        },
    },
    {
        "key": "stage_backing_quality",
        "label": "Stage & Backing Quality",
        "anchors": {
            1: "Sub-Series-A with no institutional backing of note, or backed exclusively by unknown/non-institutional investors.",
            2: "Backing quality unclear or unverifiable, or only lower-tier/angel investors confirmed on the cap table.",
            3: "At least one Tier 1 (or Tier 1+) firm confirmed on the cap table, at a stage approaching or within mandate (Series A moving toward B, or Series B+).",
            4: "Multiple Tier 1/Tier 1+ firms confirmed on the cap table at Series B+ -- strong pedigree squarely in mandate.",
        },
    },
]

# Decision tiers -- see config.py for the numeric thresholds these compare
# against. Kept here (not inlined in stage-scoring code) so a future
# reweighting or tier addition has one place to change.
DECISION_TIERS = ["track_priority", "track", "monitor", "drop", "too_early"]


def _anchors_markdown(dim: dict) -> str:
    """One dimension's holistic anchor table -- the block that replaces its
    `<!-- ANCHORS: <key> -->` marker in prompts/portfolio_fit_rubric.md."""
    lines = ["| Score | Anchor |", "| --- | --- |"]
    for score in (1, 2, 3, 4):
        lines.append(f"| {score} | {dim['anchors'][score]} |")
    return "\n".join(lines)


def rubric_text() -> str:
    """The full human-readable rubric, injected into portfolio_fit.md.
    portfolio_fit_rubric.md carries the hand-written narrative (why this
    isn't Stage 1, hard-pass/soft-pass list, decision tiers, raise-probability
    band design); each dimension's anchor table is generated from PARAMS
    above and spliced in at its `<!-- ANCHORS: <key> -->` marker."""
    path = os.path.join(_PROMPTS, "portfolio_fit_rubric.md")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    def repl(m):
        key = m.group(1)
        dim = next((p for p in PARAMS if p["key"] == key), None)
        if dim is None:
            raise ValueError(f"prompts/portfolio_fit_rubric.md references unknown PARAMS key {key!r}")
        return _anchors_markdown(dim)

    return re.sub(r"<!-- ANCHORS: (\w+) -->", repl, text)


def validate():
    if not PARAMS:
        raise ValueError("PARAMS is empty")
    for p in PARAMS:
        if set(p.get("anchors", {}).keys()) != {1, 2, 3, 4}:
            raise ValueError(f"dimension {p['key']!r} must have anchors for exactly scores 1-4")
    return True


def weighted_score(dimension_scores: dict) -> float:
    """dimension_scores: {key: 1-4 holistic score}. All four dimensions sit
    at equal weight (25% each), so this is mathematically a plain mean --
    kept as its own function, same reasoning as rubric.weighted_score, so a
    future reweighting doesn't need a schema change."""
    keys = [p["key"] for p in PARAMS]
    scores = [dimension_scores.get(k, 0) or 0 for k in keys]
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def decision_tier(score: float, hard_auto_pass: bool, too_early: bool,
                   track_priority_threshold: float, track_threshold: float,
                   monitor_threshold: float) -> str:
    """Mirrors stage1_fit.py's tier logic: hard_auto_pass always forces
    'drop' regardless of the numeric score. too_early is reported alongside
    a real computed score, not instead of one -- the caller decides whether
    to surface the tier or the score-based band first in the UI."""
    if hard_auto_pass:
        return "drop"
    if too_early:
        return "too_early"
    if score >= track_priority_threshold:
        return "track_priority"
    if score >= track_threshold:
        return "track"
    if score >= monitor_threshold:
        return "monitor"
    return "drop"


# Raise-probability bands (see prompts/portfolio_fit_rubric.md's "Probability
# of next round" section). Boundaries as percentages of estimated 3-month
# raise likelihood; the LLM reports the band name directly, this list exists
# so calling code can validate/order the model's output.
RAISE_PROBABILITY_BANDS = ["low", "medium", "high", "imminent"]
