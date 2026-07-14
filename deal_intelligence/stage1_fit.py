"""Stage 1: preliminary fit. Cheap, runs on every qualified deal.

One research-and-score call per deal against the rubric. Produces a weighted
1-4 fit score and a gate flag. No memo here.
"""
import asyncio
import os

from . import config, rubric, research
from .schemas import DealInput, DealFit, ParamScore, SubFinding

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


def _truthy(v) -> bool:
    """Defensive bool coercion -- Perplexity is a text model producing JSON, not
    a strict function-calling API, so hard_auto_pass/watch_list occasionally
    come back as "true"/"yes" strings rather than real JSON booleans."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    return str(v).strip().lower() in ("true", "yes", "y", "1")


def _tier(fit_score: float, hard_auto_pass: bool, watch_list: bool) -> tuple:
    """Returns (quality_tier, gate). hard_auto_pass and watch_list are mutually-
    overriding flags from the model, not derived from fit_score -- a single
    dimension mis-scored to 1 should never silently auto-kill a deal on its own;
    only an explicit, reasoned hard_auto_pass does. hard_auto_pass wins over
    watch_list: a deal that's disqualified outright (no AI, bad terms, etc.) is
    a Pass, not a "come back at Series B" Watch List, regardless of stage."""
    if hard_auto_pass:
        return "pass", False
    if watch_list:
        return "watch_list", False
    if fit_score >= config.STRONG_GO_THRESHOLD:
        return "strong_go", True
    if fit_score >= config.FIT_THRESHOLD:
        return "go_ic", True
    if fit_score >= config.MORE_DILIGENCE_THRESHOLD:
        return "more_diligence", False
    return "pass", False


async def score_deal(deal: DealInput) -> DealFit:
    # temperature 0: scoring should be as repeatable as possible so a boundary
    # deal does not flip across the gate between runs (web-search variance remains).
    # reasoning_effort/search_context_size at "high" + a long timeout: Stage 1
    # now runs the deepest Perplexity model at max depth on every deal, not the
    # cheap fast pass v2.1 used -- this can take several minutes per deal.
    raw, citations = await research.perplexity_async(
        _build_prompt(deal), model=config.STAGE1_RESEARCH_MODEL, temperature=0,
        timeout=config.STAGE1_TIMEOUT_SECONDS,
        reasoning_effort=config.STAGE1_REASONING_EFFORT,
        search_context_size=config.STAGE1_SEARCH_CONTEXT_SIZE,
        max_tokens=config.STAGE1_MAX_TOKENS)
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
        subs = [
            SubFinding(label=str(s.get("label", "")), finding=str(s.get("finding", "")))
            for s in (item.get("subcategories") or []) if isinstance(s, dict)
        ]
        params.append(ParamScore(key=key, score=sc, weight=weight_by_key[key],
                                  evidence=item.get("evidence", ""), subcategories=subs))
    if not params:
        # Either Perplexity's response didn't parse as JSON at all, or it parsed
        # but had no "params" array we could read -- either way we got no real
        # rubric scores. Raising here (instead of scoring an empty dict) is what
        # lets run()'s guard below tell "scoring broke" apart from "we scored it
        # and it's genuinely weak": a real score can never hit fit_score 0.0,
        # since the rubric floor is 1 per dimension.
        # length + tail (not just head): the three-tier rationale asks for
        # 40+ findings in one JSON blob, so the #1 suspect when parsing fails
        # despite well-formed-looking content is max_tokens truncation
        # mid-object -- the tail shows that at a glance, the head alone can't.
        raise ValueError(
            f"no usable rubric params in Perplexity response for {deal.name!r} "
            f"(len={len(raw)}, first 300 chars): {raw[:300]!r} "
            f"(last 300 chars): {raw[-300:]!r}"
        )
    fit_score = rubric.weighted_score(param_scores)
    raw_avg = rubric.raw_score(param_scores)
    hard_auto_pass = _truthy(parsed.get("hard_auto_pass", False))
    hard_auto_pass_reason = parsed.get("hard_auto_pass_reason", "") or ""
    watch_list = _truthy(parsed.get("watch_list", False))
    tier, gate = _tier(fit_score, hard_auto_pass, watch_list)
    return DealFit(
        record_id=deal.record_id, name=deal.name, fit_score=fit_score, raw_score=raw_avg, params=params,
        rationale=parsed.get("rationale", ""), confidence=parsed.get("confidence", "medium"),
        gate=gate, quality_tier=tier, citations=citations,
        hard_auto_pass=hard_auto_pass, hard_auto_pass_reason=hard_auto_pass_reason,
    )


async def run(deals: list) -> list:
    """Score all deals with bounded concurrency. Failures get quality_tier="error"
    (never the default "pass") so a broken scoring run can't be mistaken for a
    real screening decision downstream (Attio, hub pages, email)."""
    sem = asyncio.Semaphore(config.STAGE1_PARALLEL)

    async def guarded(d):
        async with sem:
            try:
                return await score_deal(d)
            except Exception as e:  # keep the batch alive
                return DealFit(record_id=d.record_id, name=d.name, fit_score=0.0,
                               rationale=f"scoring failed: {e}", confidence="low", gate=False,
                               quality_tier="error")

    return await asyncio.gather(*[guarded(d) for d in deals])
