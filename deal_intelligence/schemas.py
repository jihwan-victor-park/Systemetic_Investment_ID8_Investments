"""Typed shapes passed between stages. Plain dataclasses, JSON-serializable."""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class DealInput:
    record_id: str
    name: str
    domain: Optional[str] = None
    round: Optional[str] = None
    lead_investors: Optional[str] = None
    hq: Optional[str] = None
    raw: dict = field(default_factory=dict)   # full Attio values, for reference


@dataclass
class SubFinding:
    """One fixed subcategory's real score + grounded finding -- the
    point-level tier of the three-tier rationale (point -> dimension ->
    deal). key/label are standardized across every deal (see rubric.PARAMS);
    every dimension, Terms included, has at least one subcategory now."""
    key: str            # fixed rubric subcategory key, e.g. "new_vs_reup" -- resolved
                        # from the model's verbatim label via rubric.py, not model-supplied
    label: str          # fixed rubric subcategory title, e.g. "New vs re-up"
    score: float        # 1-4 for this subcategory, per its own fixed anchor rubric
    finding: str        # 1 grounded sentence: a specific fact + source, or "none found"


@dataclass
class ParamScore:
    key: str            # rubric parameter (dimension) key
    score: float        # 1-4 for this dimension -- the mean of its subcategories' scores,
                        # computed in stage1_fit.py, not read directly from the model
    weight: float       # weight from the rubric (equal across all six dimensions)
    evidence: str       # dimension-level rationale -- the synthesis of subcategories below,
                        # not a restatement of any single one
    subcategories: list = field(default_factory=list)  # list[SubFinding], point-level tier


@dataclass
class DealFit:
    """Stage 1 output: a preliminary, rubric-weighted fit score."""
    record_id: str
    name: str
    fit_score: float                       # weighted average, 1-4 scale
    params: list = field(default_factory=list)   # list[ParamScore]
    rationale: str = ""
    confidence: str = "medium"             # high | medium | low -- Diligence Confidence: how much of the
                                            # score rests on verified vs. public-only/estimated data, not a
                                            # restatement of fit_score (see prompts/rubric.md)
    gate: bool = False                     # passed the threshold -> deep research
    quality_tier: str = "pass"             # strong_go | go_ic | more_diligence | pass | watch_list
    citations: list = field(default_factory=list)  # source URLs Perplexity grounded on; [1]->index 0
    raw_score: float = 0.0                 # unweighted mean of all six dimension scores, Terms included,
                                            # 1-4 scale -- identical to fit_score at this rubric version
                                            # since all six dims sit at equal weight; kept as its
                                            # own field so a future reweighting doesn't need a schema change
    hard_auto_pass: bool = False           # a confirmed (not data-missing) disqualifying condition fired;
                                            # forces quality_tier to "pass" and gate to False regardless of fit_score
    hard_auto_pass_reason: str = ""        # which condition triggered it; empty when hard_auto_pass is False

    def to_dict(self):
        d = asdict(self)
        return d


@dataclass
class DealMemo:
    """Stage 2 output: deep research, only for deals that clear the gate."""
    record_id: str
    name: str
    final_score: Optional[float] = None
    sections: dict = field(default_factory=dict)   # section title -> markdown body
    sources: list = field(default_factory=list)
    markdown_path: Optional[str] = None

    def to_dict(self):
        return asdict(self)
