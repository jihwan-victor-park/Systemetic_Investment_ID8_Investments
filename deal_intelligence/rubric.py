"""The scoring rubric (v3.1, July 2026).

Five scored dimensions at parity (see PARAMS), each scored 1-4 against the
anchors in prompts/rubric.md. weighted_score() returns the weighted average in
that same 1-4 scale (the math is scale-agnostic; see config.FIT_THRESHOLD).
raw_score() returns the plain (unweighted) mean over the same five scored
dimensions.  Everything downstream reads from here, so this is the only place
the rubric is defined.

Terms is gate_only: the model still produces a real 1-4 read for it
(hard_auto_pass detection needs it, and the one-pager keeps showing all six
rows for legibility), but it does not enter the weighted or raw average --
it is a pass/fail gate, not graded on a curve. AI Score, which was gate_only
in v3.0, is back to being a scored dimension at parity with the other four:
"No meaningful AI component" remains a hard-auto-pass trigger on its own low
anchor (exactly like a Score-1 lead on Lead / Round Dynamics), but whenever
AI *is* present, its depth (pure-play vs. feature-layer) is graded on the
same curve as everything else, not just pass/failed. See Section 2 of the
v3.1 implementation spec for the rationale.

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


# Weights must sum to 100 across the SCORED (non gate_only) dimensions.
# Lead/Round Dynamics, Founder/Team Quality, Fundamentals, Return Potential,
# and AI Score sit at exact parity (20% each) as the five core evaluative
# dimensions. Terms is gate_only: weight 0, excluded from weighted_score()
# and raw_score(), but still scored 1-4 by the model and still carried in
# ParamScore/the output JSON for hard_auto_pass detection and display.
PARAMS = [
    {"key": "lead_round_dynamics",  "weight": 20, "label": "Lead / Round Dynamics",  "gate_only": False},
    {"key": "founder_team_quality", "weight": 20, "label": "Founder / Team Quality", "gate_only": False},
    {"key": "fundamentals",         "weight": 20, "label": "Fundamentals",           "gate_only": False},
    {"key": "return_potential",     "weight": 20, "label": "Return Potential",       "gate_only": False},
    {"key": "ai_score",             "weight": 20, "label": "AI Score",               "gate_only": False},
    {"key": "terms",                "weight": 0,  "label": "Terms",                  "gate_only": True},
]


def validate():
    scored = [p for p in PARAMS if not p.get("gate_only")]
    total = sum(p["weight"] for p in scored)
    if total != 100:
        raise ValueError(f"Scored-dimension weights must sum to 100, got {total}")
    return True


def weighted_score(param_scores: dict) -> float:
    """param_scores: {key: 1-4}. Returns the weighted average over SCORED
    dimensions only, same 1-4 scale. The gate_only dimension (terms) never
    enters this average -- it is a pass/fail gate, not graded on a curve;
    its 1-4 read is still collected upstream for hard_auto_pass detection
    and the one-pager's six-row scoring table."""
    validate()
    scored = [p for p in PARAMS if not p.get("gate_only")]
    total = 0.0
    for p in scored:
        total += (param_scores.get(p["key"], 0) or 0) * p["weight"] / 100.0
    return round(total, 1)


def raw_score(param_scores: dict) -> float:
    """param_scores: {key: 1-4}. Unweighted mean over the same SCORED
    dimensions as weighted_score (the gate_only dimension is excluded here
    too). A dimension missing from param_scores counts as 0, same convention
    as weighted_score."""
    scored = [p for p in PARAMS if not p.get("gate_only")]
    scores = [param_scores.get(p["key"], 0) or 0 for p in scored]
    return round(sum(scores) / len(scores), 1) if scores else 0.0
