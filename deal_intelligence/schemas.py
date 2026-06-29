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
    confidence: str = "medium"             # high | medium | low
    gate: bool = False                     # passed the threshold -> deep research
    quality_tier: str = "below_threshold"  # very_high | high | below_threshold
    citations: list = field(default_factory=list)  # source URLs Perplexity grounded on; [1]->index 0

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
