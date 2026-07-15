"""Stage 1: preliminary fit. Cheap, runs on every qualified deal.

One research-and-score call per deal against the rubric. Produces a weighted
1-4 fit score and a gate flag. No memo here.
"""
import asyncio
import os
import re

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


_ROUND_RE = re.compile(r"\b(pre-seed|seed|series\s+[a-h])\b", re.IGNORECASE)


def _normalize_round(round_: str) -> str:
    return re.sub(r"\s+", " ", round_).strip().lower()


def _rounds_mentioned(text: str) -> set:
    return {_normalize_round(m) for m in _ROUND_RE.findall(text)}


def _round_mismatch_warning(deal: DealInput, params: list, rationale: str) -> str:
    """Mechanical cross-check, independent of the model's own self-report:
    scan every finding/evidence string plus the rationale for round mentions
    ("Series D", "Seed", etc.) and compare against deal.round, the round we
    actually asked it to research. This exists because a reasoning-model
    prompt instruction ("verify the fact is about this company") is a nudge,
    not a guarantee -- Nous Research's Series B screen still came back
    describing a Series D led by a different, better-covered company's real
    investors (Kleiner Perkins/Saronic's actual round), which is exactly the
    kind of confident cross-company substitution a text instruction alone
    doesn't reliably stop. A stated round that contradicts the one we asked
    about is a cheap, high-signal tripwire for "this research may be about
    the wrong company" that doesn't depend on the model noticing its own error.
    Returns a warning string (empty if no mismatch, deal.round wasn't given,
    or deal.round doesn't parse into one of the recognized tokens below --
    e.g. "Growth" or "Series B-2" -- in which case there's nothing reliable
    to compare against, so the check stays silent rather than risk a false
    positive on a legitimate screen)."""
    if not deal.round:
        return ""
    wanted_matches = _ROUND_RE.findall(deal.round)
    if not wanted_matches:
        return ""
    wanted = _normalize_round(wanted_matches[0])
    text = rationale + "\n" + "\n".join(
        f"{p.evidence}\n" + "\n".join(s.finding for s in p.subcategories) for p in params
    )
    found = _rounds_mentioned(text)
    stray = found - {wanted}
    if stray and wanted not in found:
        return (f"Research findings mention {', '.join(sorted(stray))} but this deal's "
                f"round is {deal.round} -- the research may be about the wrong company "
                f"(cross-company fact conflation). Verify manually before trusting this screen.")
    return ""


# Matches "<Company>'s Series C", "<Company>' round", "<Company>'s funding", etc:
# a capitalized name (1-4 words) immediately possessive-modifying round/funding
# language. Restricting to this specific construction (rather than any
# capitalized name anywhere) is what keeps it from flagging ordinary investor
# mentions like "led by Kleiner Perkins" -- those aren't phrased as the
# investor owning a round, so they don't match.
_COMPANY_SUBJECT_RE = re.compile(
    r"\b([A-Z][\w&.-]*(?:\s[A-Z][\w&.-]*){0,3})[’']s?\s+"
    r"(?=(?:Series\s+[A-Za-z0-9]+|round|funding|valuation|raise)\b)"
)
_GENERIC_NAME_WORDS = {
    "inc", "llc", "corp", "corporation", "co", "company", "the",
    "technologies", "technology", "labs", "lab", "ai", "research",
    "group", "holdings", "capital", "ventures", "partners",
}


def _significant_tokens(name: str) -> set:
    words = re.findall(r"[a-z0-9]+", name.lower())
    return {w for w in words if w not in _GENERIC_NAME_WORDS} or set(words)


def _foreign_company_warning(deal: DealInput, params: list, rationale: str) -> str:
    """Second, more direct mechanical cross-check alongside _round_mismatch_warning:
    that one only fires when the found round contradicts deal.round, so it goes
    silent when no round was given at all -- which is exactly how Nous Research's
    screen got past it a second time, reporting "ElevenLabs' Series C" verbatim
    with no round context to contradict. This scans for the model naming a
    *different* company as the literal subject of the round/funding language
    (see _COMPANY_SUBJECT_RE) and flags it when that name shares no
    significant word with the company we actually asked about."""
    text = rationale + "\n" + "\n".join(
        f"{p.evidence}\n" + "\n".join(s.finding for s in p.subcategories) for p in params
    )
    deal_tokens = _significant_tokens(deal.name)
    foreign = set()
    for m in _COMPANY_SUBJECT_RE.finditer(text):
        candidate = m.group(1).strip()
        cand_tokens = _significant_tokens(candidate)
        if cand_tokens and not (cand_tokens & deal_tokens):
            foreign.add(candidate)
    if foreign:
        return (f"Research findings name {', '.join(sorted(foreign))} as the subject of a "
                f"round/funding claim, not {deal.name} -- the research may be about the wrong "
                f"company (cross-company fact conflation). Verify manually before trusting this screen.")
    return ""


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
    reasoning = research.extract_think(raw)
    parsed = research.extract_json(raw)
    parsed = parsed if isinstance(parsed, dict) else {}
    param_scores = {}
    params = []
    dims_by_key = {p["key"]: p for p in rubric.PARAMS}
    weight = round(100.0 / len(rubric.PARAMS), 2) if rubric.PARAMS else 0.0
    for item in parsed.get("params", []):
        key = item.get("key")
        dim = dims_by_key.get(key)
        if dim is None:
            continue
        # The model reports each subcategory by its fixed, verbatim label (not
        # an invented machine key -- more robust against a text model's drift
        # than asking it to remember snake_case keys). Resolve label -> the
        # fixed subcategory key/label here; a label that doesn't match any of
        # this dimension's standardized titles is dropped rather than guessed
        # at, same defensive posture as the dimension-key lookup above.
        sub_by_label = {s["label"]: s for s in dim["subcategories"]}
        subs = []
        sub_scores = []
        for s in (item.get("subcategories") or []):
            if not isinstance(s, dict):
                continue
            sub_def = sub_by_label.get(str(s.get("label", "")).strip())
            if sub_def is None:
                continue
            sc = float(s.get("score", 0) or 0)
            sub_scores.append(sc)
            subs.append(SubFinding(key=sub_def["key"], label=sub_def["label"],
                                    score=sc, finding=str(s.get("finding", ""))))
        dim_score = rubric.dimension_score(sub_scores)
        param_scores[key] = dim_score
        params.append(ParamScore(key=key, score=dim_score, weight=weight,
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
    rationale = parsed.get("rationale", "")
    research_flag = (_round_mismatch_warning(deal, params, rationale)
                      or _foreign_company_warning(deal, params, rationale))
    if research_flag:
        # Fail closed, same as the "no usable rubric params" guard above: a
        # screen that may be researching the wrong company must never be
        # mistaken downstream (Attio, hub, email) for a real screening
        # decision, regardless of what score it happened to compute.
        tier, gate = "error", False
    else:
        tier, gate = _tier(fit_score, hard_auto_pass, watch_list)
    return DealFit(
        record_id=deal.record_id, name=deal.name, fit_score=fit_score, raw_score=raw_avg, params=params,
        rationale=rationale, confidence=parsed.get("confidence", "medium"),
        gate=gate, quality_tier=tier, citations=citations,
        hard_auto_pass=hard_auto_pass, hard_auto_pass_reason=hard_auto_pass_reason,
        reasoning=reasoning, research_flag=research_flag,
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
