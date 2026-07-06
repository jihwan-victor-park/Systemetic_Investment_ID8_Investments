"""The scoring rubric (v2.1, April 2026).

Six dimensions, unevenly weighted (see PARAMS), each scored 1-4 against the
anchors in prompts/rubric.md. weighted_score() returns the weighted average in
that same 1-4 scale (the math is scale-agnostic; see config.FIT_THRESHOLD).
raw_score() returns the plain (unweighted) mean, shown alongside the weighted
score so the effect of the weighting -- particularly AI Score and Terms
sitting below parity with the other four -- is visible, not hidden. Everything
downstream reads from here, so this is the only place the rubric is defined.

Hard-auto-pass vs. soft-pass logic (e.g. undisclosed revenue capping
Fundamentals at 2 rather than 1) lives entirely in the prompt text
(prompts/rubric.md, prompts/stage1_fit.md), not here -- the model reports
hard_auto_pass explicitly rather than code inferring it from raw scores, so a
single mis-scored dimension can't silently auto-kill an otherwise strong deal.
"""
import os

_PROMPTS = os.path.join(os.path.dirname(__file__), "prompts")


def rubric_text() -> str:
    """The full human-readable rubric, injected into the agent prompts."""
    path = os.path.join(_PROMPTS, "rubric.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Weights must sum to 100. Scores per dimension are 1-4 (see prompts/rubric.md).
# Lead/Round Dynamics, Founder/Team Quality, Fundamentals, and Return Potential
# sit at parity (20% each) as the four core evaluative dimensions; AI Score
# (15%) and Terms (5%) are weighted down -- AI-ness is a mandate gate more than
# a spectrum, and Terms is explicitly a gate item, not a core driver.
PARAMS = [
    {"key": "lead_round_dynamics",  "weight": 20, "label": "Lead / Round Dynamics"},
    {"key": "founder_team_quality", "weight": 20, "label": "Founder / Team Quality"},
    {"key": "fundamentals",         "weight": 20, "label": "Fundamentals"},
    {"key": "return_potential",     "weight": 20, "label": "Return Potential"},
    {"key": "ai_score",             "weight": 15, "label": "AI Score"},
    {"key": "terms",                "weight": 5,  "label": "Terms"},
]


def validate():
    total = sum(p["weight"] for p in PARAMS)
    if total != 100:
        raise ValueError(f"Rubric weights must sum to 100, got {total}")
    return True


def weighted_score(param_scores: dict) -> float:
    """param_scores: {key: 1-4}. Returns the weighted average, same 1-4 scale."""
    validate()
    by_key = {p["key"]: p["weight"] for p in PARAMS}
    total = 0.0
    for key, weight in by_key.items():
        total += (param_scores.get(key, 0) or 0) * weight / 100.0
    return round(total, 1)


def raw_score(param_scores: dict) -> float:
    """param_scores: {key: 1-4}. Unweighted mean across all six dimensions,
    same 1-4 scale. A dimension missing from param_scores counts as 0, same
    convention as weighted_score."""
    scores = [param_scores.get(p["key"], 0) or 0 for p in PARAMS]
    return round(sum(scores) / len(scores), 1) if scores else 0.0
