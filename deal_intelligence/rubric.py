"""The scoring rubric.

Five equally-weighted dimensions, each scored 1-4 against the anchors in
prompts/rubric.md. weighted_score() returns the weighted average in that same
1-4 scale (the math is scale-agnostic; see config.FIT_THRESHOLD). Everything
downstream reads from here, so this is the only place the rubric is defined.
"""
import os

_PROMPTS = os.path.join(os.path.dirname(__file__), "prompts")


def rubric_text() -> str:
    """The full human-readable rubric, injected into the agent prompts."""
    path = os.path.join(_PROMPTS, "rubric.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Weights must sum to 100. Scores per dimension are 1-4 (see prompts/rubric.md).
PARAMS = [
    {"key": "lead_round_dynamics", "weight": 20, "label": "Lead / Round Dynamics"},
    {"key": "ai_score",            "weight": 20, "label": "AI Score"},
    {"key": "fundamentals",        "weight": 20, "label": "Fundamentals"},
    {"key": "return_potential",    "weight": 20, "label": "Return Potential"},
    {"key": "terms",               "weight": 20, "label": "Terms"},
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
