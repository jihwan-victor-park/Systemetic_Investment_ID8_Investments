"""Stage 1: preliminary fit. Cheap, runs on every qualified deal.

One research-and-score call per deal against the rubric. Produces a weighted
0-100 fit score and a gate flag. No memo here.
"""
import asyncio
import os

from . import config, rubric, research
from .schemas import DealInput, DealFit, ParamScore

_PROMPT = os.path.join(os.path.dirname(__file__), "prompts", "stage1_fit.md")


def _deal_context(deal: DealInput) -> str:
    bits = [f"Name: {deal.name}"]
    if deal.domain:
        bits.append(f"Website: {deal.domain}")
    if deal.round:
        bits.append(f"Round: {deal.round}")
    if deal.hq:
        bits.append(f"HQ: {deal.hq}")
    if deal.lead_investors:
        bits.append(f"Lead investors: {deal.lead_investors}")
    return "\n".join(bits)


def _build_prompt(deal: DealInput) -> str:
    with open(_PROMPT, "r", encoding="utf-8") as f:
        template = f.read()
    param_keys = ", ".join(p["key"] for p in rubric.PARAMS)
    return template.format(rubric=rubric.rubric_text(), deal=_deal_context(deal), params=param_keys)


async def score_deal(deal: DealInput) -> DealFit:
    # temperature 0: scoring should be as repeatable as possible so a boundary
    # deal does not flip across the gate between runs (web-search variance remains).
    raw, _citations = await research.perplexity_async(
        _build_prompt(deal), model=config.STAGE1_RESEARCH_MODEL, temperature=0)
    parsed = research.extract_json(raw) or {}
    param_scores = {}
    params = []
    weight_by_key = {p["key"]: p["weight"] for p in rubric.PARAMS}
    for item in parsed.get("params", []):
        key = item.get("key")
        if key not in weight_by_key:
            continue
        sc = float(item.get("score", 0) or 0)
        param_scores[key] = sc
        params.append(ParamScore(key=key, score=sc, weight=weight_by_key[key], evidence=item.get("evidence", "")))
    fit_score = rubric.weighted_score(param_scores)
    if fit_score >= config.VERY_HIGH_QUALITY_THRESHOLD:
        tier = "very_high"
    elif fit_score >= config.FIT_THRESHOLD:
        tier = "high"
    elif fit_score >= config.BORDERLINE_THRESHOLD:
        tier = "borderline"
    else:
        tier = "below_threshold"
    return DealFit(
        record_id=deal.record_id, name=deal.name, fit_score=fit_score, params=params,
        rationale=parsed.get("rationale", ""), confidence=parsed.get("confidence", "medium"),
        gate=fit_score >= config.FIT_THRESHOLD, quality_tier=tier,
    )


async def run(deals: list) -> list:
    """Score all deals with bounded concurrency. Failures become low-confidence zeros."""
    sem = asyncio.Semaphore(config.STAGE1_PARALLEL)

    async def guarded(d):
        async with sem:
            try:
                return await score_deal(d)
            except Exception as e:  # keep the batch alive
                return DealFit(record_id=d.record_id, name=d.name, fit_score=0.0,
                               rationale=f"scoring failed: {e}", confidence="low", gate=False)

    return await asyncio.gather(*[guarded(d) for d in deals])
