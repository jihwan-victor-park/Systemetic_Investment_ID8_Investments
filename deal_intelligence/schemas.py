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
class ParamScore:
    key: str            # rubric parameter key
    score: float        # 1-4 for this parameter, per the rubric's anchors
    weight: float       # weight from the rubric
    evidence: str       # 1-2 sentences with a source where possible


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
    raw_score: float = 0.0                 # unweighted mean of params, 1-4 scale -- shown alongside
                                            # fit_score so the AI Score/Terms weighting-down is visible
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
