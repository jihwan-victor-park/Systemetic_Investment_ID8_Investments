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
    round_date: Optional[str] = None   # the round's close date, off Attio's 'deal_date' slug --
                                        # RADAR_PLAN.md's capital-clock math (runway/cash-out
                                        # estimation) needs this; nothing else did before it existed
    description: Optional[str] = None  # PitchBook's company description, off Attio's 'description'
                                        # text slug -- Radar's relevance-exclusion list (RADAR_PLAN.md
                                        # §1.6) matches keywords against this, not just radarCategory
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
    reasoning: str = ""                    # the model's <think> chain-of-thought for this scoring call, if the
                                            # model produced one -- kept for QA (catching conflated/wrong-company
                                            # facts before trusting a score), never scored or parsed itself
    research_flag: str = ""                # set by a mechanical (non-LLM) integrity check -- e.g. the findings
                                            # describe a different round than the one we asked about, a sign of
                                            # cross-company fact conflation -- empty when no check fired

    def to_dict(self):
        d = asdict(self)
        return d


@dataclass
class DimensionScore:
    """One Portfolio Fit dimension's holistic score -- no subcategories,
    unlike ParamScore above (see rubric_portfolio.py for why)."""
    key: str            # rubric_portfolio.PARAMS dimension key
    score: float        # 1-4 holistic score for this dimension
    weight: float       # 0.25 for all four dimensions at v1
    evidence: str       # <= 25 words: the holistic verdict, grounded in a specific fact


@dataclass
class PortfolioFit:
    """Portfolio Fit output (v1): the lighter-than-Stage-1 monitoring score
    for a partner VC's portfolio company with no live round. See
    prompts/portfolio_fit_rubric.md for the full design and rubric_portfolio.py
    for the scoring logic this schema is populated from."""
    company: str
    company_pbid: Optional[str] = None
    fit_score: float = 0.0                 # weighted average across the four dimensions, 1-4 scale
    dimensions: list = field(default_factory=list)   # list[DimensionScore]
    rationale: str = ""
    confidence: str = "medium"             # high | medium | low, same meaning as DealFit.confidence
    decision_tier: str = "drop"            # track_priority | track | monitor | drop | too_early
    hard_auto_pass: bool = False
    hard_auto_pass_reason: str = ""
    too_early: bool = False                # stage override -- real fit_score kept regardless. FINAL value:
                                            # recomputed in portfolio_fit.py from current_stage (below), not
                                            # taken raw from the model -- see that module for the precedence
    current_stage: str = ""                # the EFFECTIVE current round: the researched value when pass 1 found
                                            # one, else the on-file PitchBook label (never discarded)
    current_round_date: str = ""           # the researched round's date (YYYY-MM/-DD), when pass 1 found one
    stage_source: str = ""                 # "researched" (pass 1 found a real round) | "on-file" (pass 1 came
                                            # back unknown, fell back to the PitchBook label) -- write_back only
                                            # overwrites latestRound when this is "researched"
    current_stage_evidence: str = ""       # <= 20 words: the round + date + source, or why unknown
    pitchbook_latest_round: str = ""       # the on-file label the research was asked to confirm/override, kept
                                            # alongside current_stage so QA can see where the two disagree (stale data)
    raise_probability_band: str = ""       # low | medium | high | imminent
    raise_probability_evidence: str = ""   # <= 25 words: what moved the band off the deterministic baseline
    base_rate_context: str = ""            # the deterministic base-rate string this call was given as input
    base_rate_band: str = ""               # low | medium | high -- the deterministic timing band before the
                                            # model's qualitative overlay; kept alongside raise_probability_band
                                            # so QA can see how far the model moved off the baseline
    months_since_last_round: Optional[float] = None  # deterministic input to the base rate, for auditing
    vc_source: str = ""                    # which partner VC's portfolio this company was scored from
    citations: list = field(default_factory=list)   # source URLs Perplexity grounded on
    research_flag: str = ""                # mechanical (non-LLM) integrity check -- set when the model's own
                                            # text names a *different* company as the subject of a funding claim
                                            # (cross-company conflation, same risk stage1_fit guards); "" when clean

    def to_dict(self):
        return asdict(self)


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
