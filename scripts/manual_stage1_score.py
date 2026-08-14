"""Manually build a Stage 1 screen doc when the automated Perplexity pipeline
is down (see PERPLEXITY_API_KEY 401 incident, July 2026) -- for the hub only,
not Attio.

Feeds a hand/agent-produced research JSON, shaped exactly like the "Output"
contract in deal_intelligence/prompts/stage1_fit.md (the same JSON Perplexity
would have returned), through the *exact same* parsing/scoring code
stage1_fit.score_deal uses -- so dimension means, fit_score, raw_score,
quality_tier, and gate are computed identically to a real automated run, not
re-derived by hand. Then builds the same screen-doc dict shape
firestore_push.push_company_screen_firestore writes to
companies/{slug}/screens/{date}, so the output here can be loaded straight in.

Usage:
    python3 scripts/manual_stage1_score.py <input.json> > <output.json>

<input.json> shape:
{
  "deal": {"record_id": "", "name": "...", "domain": "...", "round": "...",
            "lead_investors": "...", "hq": "..."},
  "model_output": { ...exact stage1_fit.md Output JSON contract... },
  "citations": ["https://...", ...]
}
"""
import json
import sys
from datetime import date

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from deal_intelligence import rubric
from deal_intelligence.schemas import DealInput, DealFit, ParamScore, SubFinding
from deal_intelligence.stage1_fit import _truthy, _tier, _dimension_hard_gate
from deal_intelligence.fit_note import PARAM_LABELS, _badge_text, _linkify_md, company_id
from deal_intelligence.firestore_push import _SUB_ANCHORS


def parse_model_output(parsed: dict):
    """Identical logic to stage1_fit.score_deal's parsing -- just no Perplexity call."""
    param_scores = {}
    params = []
    dims_by_key = {p["key"]: p for p in rubric.PARAMS}
    weight = round(100.0 / len(rubric.PARAMS), 2)
    for item in parsed.get("params", []):
        dim = dims_by_key.get(item.get("key"))
        if dim is None:
            continue
        sub_by_label = {s["label"]: s for s in dim["subcategories"]}
        subs, sub_scores = [], []
        for s in (item.get("subcategories") or []):
            sub_def = sub_by_label.get(str(s.get("label", "")).strip())
            if sub_def is None:
                raise ValueError(f"subcategory label {s.get('label')!r} doesn't match rubric.py for dim {item.get('key')!r}")
            sc = float(s.get("score", 0) or 0)
            sub_scores.append(sc)
            subs.append(SubFinding(key=sub_def["key"], label=sub_def["label"], score=sc, finding=str(s.get("finding", ""))))
        dim_score = rubric.dimension_score(sub_scores)
        param_scores[item["key"]] = dim_score
        params.append(ParamScore(key=item["key"], score=dim_score, weight=weight,
                                  evidence=item.get("evidence", ""), subcategories=subs))
    if not params:
        raise ValueError("no usable rubric params in model_output")
    fit_score = rubric.weighted_score(param_scores)
    raw_avg = rubric.raw_score(param_scores)
    hard_auto_pass = _truthy(parsed.get("hard_auto_pass", False))
    hard_auto_pass_reason = parsed.get("hard_auto_pass_reason", "") or ""
    if not hard_auto_pass:
        gate_reason = _dimension_hard_gate(param_scores)
        if gate_reason:
            hard_auto_pass = True
            hard_auto_pass_reason = gate_reason
    watch_list = _truthy(parsed.get("watch_list", False))
    tier, gate = _tier(fit_score, hard_auto_pass, watch_list)
    return params, fit_score, raw_avg, hard_auto_pass, hard_auto_pass_reason, watch_list, tier, gate


def build_deal_fit(deal: DealInput, parsed: dict, citations: list) -> DealFit:
    params, fit_score, raw_avg, hard_auto_pass, reason, watch_list, tier, gate = parse_model_output(parsed)
    return DealFit(
        record_id=deal.record_id, name=deal.name, fit_score=fit_score, raw_score=raw_avg, params=params,
        rationale=parsed.get("rationale", ""), confidence=parsed.get("confidence", "medium"),
        gate=gate, quality_tier=tier, citations=citations,
        hard_auto_pass=hard_auto_pass, hard_auto_pass_reason=reason,
    )


def build_screen_doc(fit: DealFit, deal: DealInput) -> dict:
    """Same shape as firestore_push.push_company_screen_firestore's screen_doc
    (minus docxPath -- no GCS bucket access from here)."""
    cites = fit.citations
    return {
        "date": date.today().isoformat(),
        "roundStage": deal.round,
        "fitScore": fit.fit_score,
        "rawScore": fit.raw_score,
        "verdict": _badge_text(fit).lower(),
        "gate": fit.gate,
        "hardAutoPassNote": (
            f"Hard auto-pass: {_linkify_md(fit.hard_auto_pass_reason, cites)}"
            if (fit.hard_auto_pass and fit.hard_auto_pass_reason) else None
        ),
        "dimensions": [
            {
                "key": p.key,
                "name": PARAM_LABELS.get(p.key, p.key),
                "score": p.score,
                "evidence": _linkify_md(p.evidence.replace("|", "/").replace("\n", " "), cites),
                "subcategories": [
                    {
                        "key": s.key,
                        "name": s.label,
                        "score": s.score,
                        "finding": _linkify_md(s.finding.replace("|", "/").replace("\n", " "), cites),
                        "anchors": {str(k): v for k, v in _SUB_ANCHORS.get(s.key, {}).items()},
                    }
                    for s in p.subcategories
                ],
            }
            for p in fit.params
        ],
        "rationale": _linkify_md(fit.rationale, cites),
        "confidence": fit.confidence,
        "sources": [{"number": i, "url": url} for i, url in enumerate(cites, 1)],
    }


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        payload = json.load(f)

    deal = DealInput(**payload["deal"])
    fit = build_deal_fit(deal, payload["model_output"], payload.get("citations", []))
    screen = build_screen_doc(fit, deal)

    out = {
        "slug": company_id(deal),
        "company": {"name": deal.name, "website": deal.domain},
        "screen": screen,
        "_computed": {  # sanity-check summary, not part of the Firestore write
            "fit_score": fit.fit_score, "raw_score": fit.raw_score,
            "quality_tier": fit.quality_tier, "gate": fit.gate,
            "hard_auto_pass": fit.hard_auto_pass,
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
