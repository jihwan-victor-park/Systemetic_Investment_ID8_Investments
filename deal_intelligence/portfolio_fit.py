"""Stage 0: Portfolio Fit scoring. The lighter-than-Stage-1 monitoring pass
over a partner VC's portfolio companies -- the piece rubric_portfolio.py's
docstring scoped out as "the Phase 2 pipeline endpoint that would actually
call this rubric against portfolio rows... Not built yet."

Where this sits in the pipeline (Oscar's framing):
  Stage 0 (this file) -- monitor partner VC portfolios so we know which
    companies to TRACK now and revisit for access once they reach Series B+.
    One cheap `sonar` research-and-score call per company, run against the
    Portfolio Fit rubric (rubric_portfolio.py / prompts/portfolio_fit.md),
    only over companies that cleared the deterministic prefilter
    (portfolio_prefilter.py, prefilterPass=True).
  Stage 1 -- the existing live-deal fit pass (stage1_fit.py / Research Chat).
  Stage 2 -- deal screening (not built; out of scope here).

Two things happen in the single scored call, per the rubric:
  1. the four-dimension holistic fit score (AI/thesis, team, fundamentals,
     stage/backing), and
  2. the 3-month raise-probability band -- seeded by portfolio_timing.py's
     deterministic base rate (computed in code from last-financing recency vs
     stage cadence) and nudged by the model's qualitative overlay.

Mirrors stage1_fit.py's structure (build prompt -> perplexity_async -> parse
JSON -> typed result -> bounded-concurrency run()) so it reads the same as the
rest of the package. The CLI at the bottom is the local entry point Oscar runs
against the seed JSON -- see its --help / the module-level README note.
"""
import argparse
import asyncio
import json
import os
from datetime import date

from . import config, research, rubric_portfolio, portfolio_timing
from .schemas import PortfolioFit, DimensionScore
from .stage1_fit import _significant_tokens, _COMPANY_SUBJECT_RE, _COMPANY_VERB_RE, _truthy

_PROMPT = os.path.join(os.path.dirname(__file__), "prompts", "portfolio_fit.md")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SEED_PATH = os.path.join(_REPO_ROOT, "hub-next", "scripts", "data", "partner-vcs-seed.json")
_DEFAULT_OUT = os.path.join(_REPO_ROOT, "portfolio_fit_results.json")


# ── Prompt assembly ──────────────────────────────────────────────────────────

def _fmt(value):
    """A field value the model should treat as present, or None to skip the
    line entirely -- blank strings and PitchBook's empty-string sentinels both
    become 'skip' so we never feed the model an empty 'Revenue: ' line it
    might read as a real zero."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _company_context(company, vc_name=None):
    """The 'Company' block -- PitchBook ground truth for this one company, the
    facts the prompt tells the model to treat as authoritative (and as a
    tripwire: research that contradicts them signals it drifted onto a
    different, better-covered company). Only non-empty fields are emitted."""
    fin = company.get("financials") or {}
    lines = [
        ("Name", _fmt(company.get("company"))),
        ("Industry", _fmt(company.get("industry"))),
        ("Category", _fmt(company.get("category"))),
        ("PitchBook verticals", _fmt(company.get("vertical"))),
        ("Description", _fmt(company.get("description"))),
        ("HQ", _fmt(company.get("hqLocation"))),
        ("Year founded", _fmt(company.get("yearFounded"))),
        ("Business status", _fmt(company.get("businessStatus"))),
        ("Latest round", _fmt(company.get("latestRound"))),
        ("Latest round date", _fmt(company.get("latestRoundDate"))),
        ("Employees (PitchBook)", _fmt(fin.get("employees"))),
        ("Revenue $000s (PitchBook)", _fmt(fin.get("revenueUsdThousands"))),
        ("Post-money valuation $mm (PitchBook)", _fmt(fin.get("postValuationUsdMillions"))),
    ]
    if vc_name:
        # The partner VC is a known backer on this company's cap table -- real,
        # structured signal for the Stage & Backing dimension, so name it.
        lines.append(("Known investor (this portfolio)", vc_name))
    return "\n".join(f"{k}: {v}" for k, v in lines if v is not None)


def _build_prompt(company, base_rate_context, vc_name=None):
    with open(_PROMPT, "r", encoding="utf-8") as f:
        template = f.read()
    param_keys = ", ".join(p["key"] for p in rubric_portfolio.PARAMS)
    return template.format(
        rubric=rubric_portfolio.rubric_text(),
        company=_company_context(company, vc_name=vc_name),
        params=param_keys,
        base_rate_context=base_rate_context,
    )


# ── Mechanical integrity check ───────────────────────────────────────────────

def _conflation_flag(company_name, dimensions, rationale, raise_evidence):
    """Lightweight version of stage1_fit's cross-company checks: scan the
    model's own output for a *different* company named as the subject of a
    funding/round claim. portfolio_fit.md warns the model about this exact
    failure (listicles/roundups that bundle several companies), but a prompt
    instruction is a nudge, not a guarantee -- this is the mechanical backstop.
    Returns a warning string (empty when clean)."""
    text = "\n".join([rationale or "", raise_evidence or ""]
                     + [d.evidence for d in dimensions])
    target_tokens = _significant_tokens(company_name)
    foreign = set()
    for pattern in (_COMPANY_SUBJECT_RE, _COMPANY_VERB_RE):
        for m in pattern.finditer(text):
            candidate = m.group(1).strip()
            cand_tokens = _significant_tokens(candidate)
            if cand_tokens and not (cand_tokens & target_tokens):
                foreign.add(candidate)
    if foreign:
        return (f"Output names {', '.join(sorted(foreign))} as the subject of a funding claim, "
                f"not {company_name} -- possible cross-company conflation, verify before trusting.")
    return ""


# ── Scoring ──────────────────────────────────────────────────────────────────

async def score_company(company, vc_name=None, as_of=None):
    """Score one portfolio company. Never raises for a normal bad/thin result
    (that's a real low score); raises only when the model returned nothing
    usable, so run()'s guard can tell 'scoring broke' from 'scored and weak'."""
    br = portfolio_timing.base_rate(company, as_of=as_of)
    prompt = _build_prompt(company, br.context, vc_name=vc_name)

    # sonar is not a reasoning model, so no reasoning_effort here -- only
    # search_context_size applies. temperature 0 for score repeatability.
    raw, citations = await research.perplexity_async(
        prompt, model=config.PORTFOLIO_FIT_MODEL, temperature=0,
        timeout=config.PORTFOLIO_FIT_TIMEOUT_SECONDS,
        search_context_size=config.PORTFOLIO_FIT_SEARCH_CONTEXT_SIZE,
        max_tokens=config.PORTFOLIO_FIT_MAX_TOKENS,
    )
    parsed = research.extract_json(raw)
    parsed = parsed if isinstance(parsed, dict) else {}

    dims_by_key = {p["key"]: p for p in rubric_portfolio.PARAMS}
    weight = round(1.0 / len(rubric_portfolio.PARAMS), 2) if rubric_portfolio.PARAMS else 0.0
    dimensions = []
    dim_scores = {}
    for item in parsed.get("dimensions", []):
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if key not in dims_by_key:
            continue
        score = float(item.get("score", 0) or 0)
        dim_scores[key] = score
        dimensions.append(DimensionScore(key=key, score=score, weight=weight,
                                          evidence=str(item.get("evidence", ""))))
    if not dimensions:
        raise ValueError(
            f"no usable dimensions in Portfolio Fit response for {company.get('company')!r} "
            f"(len={len(raw)}, first 300): {raw[:300]!r} (last 300): {raw[-300:]!r}"
        )

    fit_score = rubric_portfolio.weighted_score(dim_scores)
    hard_auto_pass = _truthy(parsed.get("hard_auto_pass", False))
    too_early = _truthy(parsed.get("too_early", False))
    rationale = parsed.get("rationale", "") or ""
    raise_evidence = parsed.get("raise_probability_evidence", "") or ""

    # Deterministic stage backstop: the model's too_early (below-Series-B)
    # judgment is unreliable on PitchBook's generic bucket labels -- it tagged
    # xAI ('Later Stage VC') and Hadrian ('Series C') too_early. Stage is
    # structured data, so a clearly Series-B+ company can never be too_early,
    # regardless of what the model said. One-directional on purpose (see
    # portfolio_timing.is_series_b_plus): only overrides a wrong True, never
    # forces one, since the model may know a newer round than the snapshot.
    stage_note = ""
    if too_early and portfolio_timing.is_series_b_plus(company.get("latestRound")) is True:
        too_early = False
        stage_note = (f"model tagged too_early but latestRound "
                      f"({company.get('latestRound')!r}) is Series B+ -- override applied")
    tier = rubric_portfolio.decision_tier(
        fit_score, hard_auto_pass, too_early,
        config.PORTFOLIO_TRACK_PRIORITY_THRESHOLD,
        config.PORTFOLIO_TRACK_THRESHOLD,
        config.PORTFOLIO_MONITOR_THRESHOLD,
    )
    flag = _conflation_flag(company.get("company", ""), dimensions, rationale, raise_evidence)
    flag = " · ".join(f for f in (flag, stage_note) if f)

    return PortfolioFit(
        company=company.get("company", ""),
        company_pbid=company.get("companyPbid"),
        fit_score=fit_score,
        dimensions=dimensions,
        rationale=rationale,
        confidence=parsed.get("confidence", "medium"),
        decision_tier=tier,
        hard_auto_pass=hard_auto_pass,
        hard_auto_pass_reason=parsed.get("hard_auto_pass_reason", "") or "",
        too_early=too_early,
        raise_probability_band=parsed.get("raise_probability_band", "") or "",
        raise_probability_evidence=raise_evidence,
        base_rate_context=br.context,
        base_rate_band=br.band,
        months_since_last_round=br.months_since,
        vc_source=vc_name or "",
        citations=citations,
        research_flag=flag,
    )


async def run(companies, parallel=None, as_of=None):
    """Score companies with bounded concurrency. companies: list of
    (company_dict, vc_name) tuples. A failed call yields a PortfolioFit with
    decision_tier='error' (never a real tier) so a broken run can't be mistaken
    for a genuine screening verdict, same posture as stage1_fit.run()."""
    sem = asyncio.Semaphore(parallel or config.PORTFOLIO_FIT_PARALLEL)

    async def guarded(company, vc_name):
        async with sem:
            try:
                return await score_company(company, vc_name=vc_name, as_of=as_of)
            except Exception as e:  # keep the batch alive
                return PortfolioFit(
                    company=company.get("company", ""),
                    company_pbid=company.get("companyPbid"),
                    rationale=f"scoring failed: {e}", confidence="low",
                    decision_tier="error", vc_source=vc_name or "",
                    base_rate_context=portfolio_timing.base_rate(company, as_of=as_of).context,
                )

    return await asyncio.gather(*[guarded(c, vc) for c, vc in companies])


# ── Company selection ─────────────────────────────────────────────────────────

def _load_seed(seed_path):
    with open(seed_path, encoding="utf-8") as f:
        return json.load(f)


def select_companies(data, limit=100, vc_name=None):
    """Pick up to `limit` companies that passed the prefilter (prefilterPass
    is True). With --vc, only that fund. Otherwise round-robins across every
    evaluated fund so a 100-company test spans many portfolios instead of
    exhausting one alphabetical fund -- more representative for QA. Deterministic
    (file order, no randomness), returns [(company_dict, vc_name), ...]."""
    per_vc = []
    for vc in data:
        if vc_name and vc["name"].strip().lower() != vc_name.strip().lower():
            continue
        passing = [c for c in vc.get("portfolio", []) if c.get("prefilterPass") is True]
        if passing:
            per_vc.append((vc["name"], passing))

    if vc_name and not per_vc:
        available = ", ".join(sorted(v["name"] for v in data))
        raise SystemExit(f"No VC named {vc_name!r} with prefilter-passing companies.\nAvailable: {available}")

    selected = []
    if vc_name:
        for c in per_vc[0][1][:limit]:
            selected.append((c, per_vc[0][0]))
        return selected

    # round-robin across funds
    idx = 0
    while len(selected) < limit and any(idx < len(cs) for _, cs in per_vc):
        for name, cs in per_vc:
            if idx < len(cs):
                selected.append((cs[idx], name))
                if len(selected) >= limit:
                    break
        idx += 1
    return selected


# ── CLI ──────────────────────────────────────────────────────────────────────

def _print_summary(results):
    from collections import Counter
    tiers = Counter(r.decision_tier for r in results)
    bands = Counter(r.raise_probability_band or "(none)" for r in results)
    base_bands = Counter(r.base_rate_band or "(none)" for r in results)
    scored = [r for r in results if r.decision_tier != "error"]
    errors = len(results) - len(scored)
    flagged = [r for r in results if r.research_flag]
    avg = round(sum(r.fit_score for r in scored) / len(scored), 2) if scored else 0.0

    print(f"\nScored {len(scored)}/{len(results)} companies ({errors} errors)")
    print(f"Average fit score: {avg} / 4")
    print("\nDecision tiers:")
    for tier in ["track_priority", "track", "monitor", "drop", "too_early", "error"]:
        if tiers.get(tier):
            print(f"  {tiers[tier]:4d}  {tier}")
    print("\nRaise-probability band (model, after overlay):")
    for band in ["imminent", "high", "medium", "low", "(none)"]:
        if bands.get(band):
            print(f"  {bands[band]:4d}  {band}")
    print("\nDeterministic base-rate band (timing only, before overlay):")
    for band in ["high", "medium", "low", "(none)"]:
        if base_bands.get(band):
            print(f"  {base_bands[band]:4d}  {band}")
    if flagged:
        print(f"\n⚠ {len(flagged)} flagged for manual review (conflation and/or stage override):")
        for r in flagged[:10]:
            print(f"    {r.company}: {r.research_flag}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=100, help="max companies to score (default 100)")
    ap.add_argument("--vc", help="only score this partner VC's portfolio (default: round-robin across all)")
    ap.add_argument("--out", default=_DEFAULT_OUT,
                    help="where to write the JSON results (default: repo-root portfolio_fit_results.json)")
    ap.add_argument("--parallel", type=int, help=f"concurrent calls (default {config.PORTFOLIO_FIT_PARALLEL})")
    ap.add_argument("--seed", default=_SEED_PATH, help="path to partner-vcs-seed.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="select companies and build prompts but make NO API calls -- prints the "
                         "selection + a token/cost estimate so you can preview spend first")
    args = ap.parse_args()

    data = _load_seed(args.seed)
    companies = select_companies(data, limit=args.limit, vc_name=args.vc)
    if not companies:
        raise SystemExit("No prefilter-passing companies selected -- run portfolio_prefilter --all --persist first.")

    print(f"Selected {len(companies)} companies"
          + (f" from {args.vc}" if args.vc else f" across {len({v for _, v in companies})} funds"))

    if args.dry_run:
        # Rough token estimate: prompt words / 0.75 ~= tokens; output ~300 tok.
        sample_prompt = _build_prompt(companies[0][0],
                                      portfolio_timing.base_rate(companies[0][0]).context,
                                      vc_name=companies[0][1])
        in_tok = int(len(sample_prompt.split()) / 0.75)
        # Sonar: $1/M in + $1/M out (+ per-request fee, dominant). Token cost only here.
        tok_cost = (in_tok + 300) / 1_000_000 * 1.0
        print(f"\nDRY RUN -- no API calls made.")
        print(f"  ~{in_tok} input tokens/company (+~300 output)")
        print(f"  token cost ~${tok_cost:.4f}/company + Perplexity's per-request fee (~$0.005-0.014)")
        print(f"  estimated total for {len(companies)}: ~${(tok_cost + 0.009) * len(companies):.2f} "
              f"(${(tok_cost + 0.005) * len(companies):.2f}-${(tok_cost + 0.014) * len(companies):.2f} range)")
        print("\nFirst 5 selected:")
        for c, vc in companies[:5]:
            br = portfolio_timing.base_rate(c)
            print(f"  {c.get('company'):<32} [{vc}]  round={c.get('latestRound') or '?'}  base_rate={br.band}")
        return

    results = asyncio.run(run(companies, parallel=args.parallel))

    out_path = os.path.abspath(args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "scored_at": date.today().isoformat(),
            "count": len(results),
            "results": [r.to_dict() for r in results],
        }, f, indent=2, ensure_ascii=False)

    _print_summary(results)
    print(f"\nFull results written to: {out_path}")


if __name__ == "__main__":
    main()
