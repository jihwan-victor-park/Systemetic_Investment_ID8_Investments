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

Two sonar calls per company, in order (Oscar's design):
  1. STAGE RESOLUTION (resolve_current_stage / prompts/portfolio_stage.md) --
     a dedicated first pass whose only job is nailing the company's TRUE
     current round. This exists because stage-as-one-field-in-the-big-call was
     unreliable on fast-moving private companies (it called Base Power, a live
     Series C ID8 holding, "Series A"), and getting it wrong wrongly benches a
     company as too_early. The verified round then drives too_early (in code)
     and the timing base rate.
  2. FIT SCORING (score_company / prompts/portfolio_fit.md) -- the four-
     dimension holistic score (AI/thesis, team, fundamentals, stage/backing)
     plus the 3-month raise-probability band, given the confirmed stage from
     pass 1 as ground truth rather than re-researching it.

Companies ID8 already holds are excluded at selection time (data/id8_holdings.json)
-- they're current portfolio, not prospects to track for future access.

Mirrors stage1_fit.py's structure (build prompt -> perplexity_async -> parse
JSON -> typed result -> bounded-concurrency run()) so it reads the same as the
rest of the package. The CLI at the bottom is the local entry point Oscar runs
against the seed JSON -- see its --help / the module-level README note.
"""
import argparse
import asyncio
import json
import os
import re
from datetime import date

from . import config, research, rubric_portfolio, portfolio_timing
from .schemas import PortfolioFit, DimensionScore
from .stage1_fit import _significant_tokens, _COMPANY_SUBJECT_RE, _COMPANY_VERB_RE, _truthy

_PROMPT = os.path.join(os.path.dirname(__file__), "prompts", "portfolio_fit.md")
_STAGE_PROMPT = os.path.join(os.path.dirname(__file__), "prompts", "portfolio_stage.md")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SEED_PATH = os.path.join(_REPO_ROOT, "hub-next", "scripts", "data", "partner-vcs-seed.json")
_DEFAULT_OUT = os.path.join(_REPO_ROOT, "portfolio_fit_results.json")
_HOLDINGS_PATH = os.path.join(os.path.dirname(__file__), "data", "id8_holdings.json")


# ── ID8 holdings exclusion ────────────────────────────────────────────────────

def _normalize_name(name):
    """Lowercase + strip everything non-alphanumeric so 'Scale AI', 'Scale AI,
    Inc.' and 'scaleai' all collapse to the same key. Also drops a trailing
    parenthetical ('X (Social/Platform Software)' -> 'x') the seed data uses to
    disambiguate generic names."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name or "")
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _load_id8_holdings():
    try:
        with open(_HOLDINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {_normalize_name(n) for n in data.get("holdings", [])}
    except (OSError, json.JSONDecodeError):
        return set()


_ID8_HOLDINGS = _load_id8_holdings()


# ── Stage label handling ──────────────────────────────────────────────────────

def _onfile_round(company):
    """The ORIGINAL PitchBook round label. write_back overwrites `latestRound`
    in place with the researched round, preserving the original in
    `latestRoundOnFile` -- so once that's set, IT is the true on-file value.
    Reading through this keeps re-scoring idempotent (the stage pass always
    verifies against the original PitchBook label, never a value we already
    replaced)."""
    return (company.get("latestRoundOnFile") or company.get("latestRound") or "").strip()


# How specific a round label is, so write_back never DOWNGRADES a precise
# on-file series (e.g. "Series K") to a vaguer researched answer ("Growth/
# Late-stage"). Higher = more specific.
def _round_specificity(label):
    s = (label or "").strip().lower()
    if not s:
        return 0
    if re.match(r"(pre-?seed|seed|series\s+[a-z])", s):
        return 3  # a clean/near-clean series letter (incl. "Seed Round (Nth)")
    if "growth" in s or "late-stage" in s or "late stage" in s:
        return 2  # named late-stage but no letter
    return 1      # generic PitchBook bucket: "Later Stage VC", "Early Stage VC", "PE Growth", ...


def is_id8_holding(company_name):
    return _normalize_name(company_name) in _ID8_HOLDINGS


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
        ("Latest round", _fmt(_onfile_round(company))),
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


def _build_prompt(company, base_rate_context, confirmed_stage, vc_name=None):
    with open(_PROMPT, "r", encoding="utf-8") as f:
        template = f.read()
    param_keys = ", ".join(p["key"] for p in rubric_portfolio.PARAMS)
    return template.format(
        rubric=rubric_portfolio.rubric_text(),
        company=_company_context(company, vc_name=vc_name),
        params=param_keys,
        base_rate_context=base_rate_context,
        confirmed_stage=confirmed_stage,
    )


# ── Pass 1: dedicated stage resolution ────────────────────────────────────────

class StageResult:
    """Small holder for the stage-resolution pass output."""
    __slots__ = ("stage", "date", "lead_investor", "evidence", "confidence")

    def __init__(self, stage="", date="", lead_investor="", evidence="", confidence=""):
        self.stage, self.date, self.lead_investor = stage, date, lead_investor
        self.evidence, self.confidence = evidence, confidence


async def resolve_current_stage(company, vc_name=None):
    """Pass 1: one focused sonar call whose ONLY job is the company's true
    current round (prompts/portfolio_stage.md). Deeper search context than the
    fit call. Returns a StageResult; falls back to the on-file label on any
    parse failure so pass 2 always has *something*, rather than crashing the
    whole company on a flaky stage lookup."""
    with open(_STAGE_PROMPT, "r", encoding="utf-8") as f:
        template = f.read()
    prompt = template.format(
        company=_company_context(company, vc_name=vc_name),
        pitchbook_label=_onfile_round(company) or "(none on file)",
        pitchbook_date=company.get("latestRoundDate") or "unknown",
    )
    raw, _ = await research.perplexity_async(
        prompt, model=config.PORTFOLIO_FIT_MODEL, temperature=0,
        timeout=config.PORTFOLIO_FIT_TIMEOUT_SECONDS,
        search_context_size=config.PORTFOLIO_STAGE_SEARCH_CONTEXT_SIZE,
        max_tokens=config.PORTFOLIO_FIT_MAX_TOKENS,
    )
    parsed = research.extract_json(raw)
    if not isinstance(parsed, dict):
        return StageResult(stage=company.get("latestRound") or "", evidence="stage pass unparseable; fell back to on-file label", confidence="low")
    return StageResult(
        stage=(parsed.get("current_stage") or "").strip(),
        date=(parsed.get("current_round_date") or "").strip(),
        lead_investor=(parsed.get("lead_investor") or "").strip(),
        evidence=(parsed.get("evidence") or "").strip(),
        confidence=(parsed.get("confidence") or "").strip(),
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

async def score_company(company, vc_name=None, as_of=None, stage=None):
    """Score one portfolio company. Never raises for a normal bad/thin result
    (that's a real low score); raises only when the model returned nothing
    usable, so run()'s guard can tell 'scoring broke' from 'scored and weak'.

    Runs the dedicated stage-resolution pass first (unless a StageResult is
    passed in via `stage`, e.g. for testing), then the fit pass with that
    confirmed round as ground truth."""
    if stage is None:
        stage = await resolve_current_stage(company, vc_name=vc_name)

    # Effective stage: the pass-1 research when it produced a real answer;
    # otherwise fall back to the on-file label rather than discarding it. Pass 1
    # returns "unknown" for obscure companies it can't verify (e.g. Hadrian),
    # and the on-file PitchBook label -- even a generic bucket -- is better than
    # nothing there.
    pitchbook_label = _onfile_round(company)
    resolved = (stage.stage or "").strip()
    stage_is_real = bool(resolved) and resolved.lower() != "unknown"
    effective_stage = resolved if stage_is_real else pitchbook_label
    stage_from_onfile = not stage_is_real and bool(pitchbook_label)

    # Timing baseline uses the effective round/date (base_rate falls back to
    # on-file internally when a field is blank) -- the whole point of pass 1.
    br = portfolio_timing.base_rate(company, as_of=as_of,
                                    stage_override=effective_stage, date_override=stage.date)
    confirmed_stage = effective_stage or "unknown"
    prompt = _build_prompt(company, br.context, confirmed_stage, vc_name=vc_name)

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
    hard_auto_pass_reason = parsed.get("hard_auto_pass_reason", "") or ""
    rationale = parsed.get("rationale", "") or ""
    raise_evidence = parsed.get("raise_probability_evidence", "") or ""

    # AI hard-pass, enforced in code (Oscar's policy call): the rubric defines
    # an ai_thesis_fit score of 1 as "no meaningful AI component -- hard auto-
    # pass", but the model applied that inconsistently (SpaceX/Ramp flip-
    # flopped between a 1 that dropped and a 2 that didn't across runs). Making
    # it deterministic here removes that wobble: AI dimension == 1 always drops,
    # no matter what the model set hard_auto_pass to.
    if dim_scores.get("ai_thesis_fit") == 1 and not hard_auto_pass:
        hard_auto_pass = True
        hard_auto_pass_reason = ("AI dimension scored 1 (no meaningful AI component) -- "
                                 "rubric hard auto-pass, enforced in code")

    # too_early (below Series B) is a threshold applied IN CODE over the
    # EFFECTIVE stage (pass-1 research when real, else the on-file label) --
    # never the fit model's read. When even the effective stage doesn't
    # classify, default to NOT too_early: a false bench hides a real holding,
    # so better to let the fit score speak.
    effective_cls = portfolio_timing.is_series_b_plus(effective_stage)
    if effective_cls is not None:
        too_early = effective_cls is False
        stage_basis = f"stage {effective_stage!r}" + (" (from on-file label)" if stage_from_onfile else " (researched)")
    else:
        too_early = False
        stage_basis = "stage indeterminate -- not benched"

    # Surface for QA when pass 1's researched stage contradicts the on-file
    # label (a stale-data signal worth a human glance).
    researched = portfolio_timing.is_series_b_plus(resolved) if stage_is_real else None
    onfile = portfolio_timing.is_series_b_plus(pitchbook_label)
    stage_note = ""
    if researched is not None and onfile is not None and researched != onfile:
        stage_note = (f"researched stage {stage.stage!r} disagrees with on-file "
                      f"{pitchbook_label!r} -- on-file data may be stale")
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
        hard_auto_pass_reason=hard_auto_pass_reason,
        too_early=too_early,
        current_stage=effective_stage or "unknown",
        current_round_date=(stage.date if stage_is_real else ""),
        stage_source=("on-file" if stage_from_onfile else "researched" if stage_is_real else "none"),
        current_stage_evidence=" | ".join(f for f in (
            ("(pass 1 unknown; using on-file label)" if stage_from_onfile else stage.evidence),
            f"date: {stage.date}" if stage.date else "",
            f"lead: {stage.lead_investor}" if stage.lead_investor else "",
            f"confidence: {stage.confidence}" if stage.confidence else "",
        ) if f),
        pitchbook_latest_round=pitchbook_label,
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
                )

    return await asyncio.gather(*[guarded(c, vc) for c, vc in companies])


# ── Company selection ─────────────────────────────────────────────────────────

def _load_seed(seed_path):
    with open(seed_path, encoding="utf-8") as f:
        return json.load(f)


def select_companies(data, limit=100, vc_name=None, order="round-robin"):
    """Pick up to `limit` companies that passed the prefilter (prefilterPass
    is True) AND are not already ID8 holdings (data/id8_holdings.json -- we
    don't scan companies we already own as if they were prospects). With --vc,
    only that fund.

    order controls how the limit is spread when no single --vc is given:
      "round-robin" -- one company from each fund in turn (a representative
        sample across many portfolios; good for QA).
      "sequential"  -- whole funds in file order, one fully before the next
        (so you get complete per-VC portfolios up to the limit).
    Funds over 500 companies never appear either way: they're deferred by the
    prefilter (no prefilterPass=True), so nothing from them is ever selected.
    Deterministic (file order, no randomness); returns [(company_dict, vc_name)]."""
    per_vc = []
    skipped_holdings = 0
    for vc in data:
        if vc_name and vc["name"].strip().lower() != vc_name.strip().lower():
            continue
        passing = []
        for c in vc.get("portfolio", []):
            if c.get("prefilterPass") is not True:
                continue
            if is_id8_holding(c.get("company", "")):
                skipped_holdings += 1
                continue
            passing.append(c)
        if passing:
            per_vc.append((vc["name"], passing))
    if skipped_holdings:
        print(f"(excluded {skipped_holdings} companies ID8 already holds -- see data/id8_holdings.json)")

    if vc_name and not per_vc:
        available = ", ".join(sorted(v["name"] for v in data))
        raise SystemExit(f"No VC named {vc_name!r} with prefilter-passing companies.\nAvailable: {available}")

    selected = []
    if vc_name:
        for c in per_vc[0][1][:limit]:
            selected.append((c, per_vc[0][0]))
        return selected

    if order == "sequential":
        # whole funds in file order, one fully before the next
        for name, cs in per_vc:
            for c in cs:
                selected.append((c, name))
                if len(selected) >= limit:
                    return selected
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


# ── Write results back into the seed JSON (for the hub) ───────────────────────

def write_back(results, seed_path=_SEED_PATH):
    """Merge fit results onto the matching portfolio entries in
    partner-vcs-seed.json (matched by vc_source + normalized company name), so
    backfill-partner-vcs.mjs pushes them to Firestore and the hub can render
    them. Only successful scores are written (decision_tier != 'error').
    camelCase field names for the JS side. Returns (written, unmatched)."""
    with open(seed_path, encoding="utf-8") as f:
        data = json.load(f)

    idx = {}
    for vc in data:
        for c in vc.get("portfolio", []):
            idx[(vc["name"], _normalize_name(c.get("company", "")))] = c

    scored_at = date.today().isoformat()
    written, unmatched, rounds_updated = 0, [], 0
    for r in results:
        if r.decision_tier == "error":
            continue
        c = idx.get((r.vc_source, _normalize_name(r.company)))
        if c is None:
            unmatched.append((r.vc_source, r.company))
            continue
        c["fitScore"] = r.fit_score
        c["fitTier"] = r.decision_tier
        c["fitCurrentStage"] = r.current_stage
        c["fitRaiseProbability"] = r.raise_probability_band
        c["fitTooEarly"] = r.too_early
        c["fitHardPass"] = r.hard_auto_pass
        c["fitRationale"] = r.rationale
        c["fitScoredAt"] = scored_at
        # When pass 1 actually researched a current round, update the displayed
        # latestRound/latestRoundDate with it -- the stale/generic PitchBook
        # bucket ("Later Stage VC (4th Round)") gets replaced by the true series
        # we found. But NEVER downgrade: if the on-file label is already more
        # specific than the researched one (a clean "Series K" vs a vague
        # "Growth/Late-stage"), keep the on-file. Preserve the original once for
        # provenance; fallback ("on-file") cases leave latestRound as-is.
        onfile = _onfile_round(c)
        if (r.stage_source == "researched" and r.current_stage
                and _round_specificity(r.current_stage) >= _round_specificity(onfile)):
            c.setdefault("latestRoundOnFile", c.get("latestRound", ""))
            c["latestRound"] = r.current_stage
            if r.current_round_date:
                c["latestRoundDate"] = r.current_round_date
            rounds_updated += 1
        written += 1
    write_back.rounds_updated = rounds_updated

    with open(seed_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return written, unmatched


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
    ap.add_argument("--sequential", action="store_true",
                    help="fill whole funds in VC order (one fully before the next) instead of "
                         "round-robin sampling across funds")
    ap.add_argument("--write-back", action="store_true",
                    help="after scoring, merge the fit results (fitScore/fitTier/fitCurrentStage/"
                         "fitRaiseProbability/...) back onto partner-vcs-seed.json so the hub can "
                         "show them and backfill-partner-vcs.mjs can push them to Firestore")
    ap.add_argument("--dry-run", action="store_true",
                    help="select companies and build prompts but make NO API calls -- prints the "
                         "selection + a token/cost estimate so you can preview spend first")
    args = ap.parse_args()

    data = _load_seed(args.seed)
    companies = select_companies(data, limit=args.limit, vc_name=args.vc,
                                 order="sequential" if args.sequential else "round-robin")
    if not companies:
        raise SystemExit("No prefilter-passing companies selected -- run portfolio_prefilter --all --persist first.")

    print(f"Selected {len(companies)} companies"
          + (f" from {args.vc}" if args.vc else f" across {len({v for _, v in companies})} funds"))

    if args.dry_run:
        # Rough token estimate: prompt words / 0.75 ~= tokens. There are now
        # TWO sonar calls/company (stage resolution + fit), so per-request fees
        # count twice; estimate off the fit prompt (the larger of the two).
        br0 = portfolio_timing.base_rate(companies[0][0])
        sample_prompt = _build_prompt(companies[0][0], br0.context,
                                      companies[0][0].get("latestRound") or "unknown",
                                      vc_name=companies[0][1])
        in_tok = int(len(sample_prompt.split()) / 0.75)
        tok_cost = (in_tok + 300) / 1_000_000 * 1.0
        print(f"\nDRY RUN -- no API calls made.")
        print(f"  ~{in_tok} input tokens/fit-call (+~300 output), plus a smaller stage-resolution call")
        print(f"  ~2 sonar calls/company (stage + fit); token cost ~${tok_cost:.4f} + 2x per-request fee (~$0.005-0.014 each)")
        print(f"  estimated total for {len(companies)}: ~${(tok_cost + 0.018) * len(companies):.2f} "
              f"(${(tok_cost + 0.010) * len(companies):.2f}-${(tok_cost + 0.028) * len(companies):.2f} range)")
        print("\nFirst 5 selected:")
        for c, vc in companies[:5]:
            print(f"  {c.get('company'):<32} [{vc}]  on-file round={c.get('latestRound') or '?'}")
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

    if args.write_back:
        written, unmatched = write_back(results, seed_path=args.seed)
        print(f"\nWrote fit results onto {written} companies in {os.path.basename(args.seed)}.")
        print(f"  ({getattr(write_back, 'rounds_updated', 0)} had latestRound updated to the researched current round)")
        if unmatched:
            print(f"  ({len(unmatched)} results could not be matched back and were skipped)")
        print("Next: push to Firestore -- (cd hub-next && node scripts/backfill-partner-vcs.mjs) "
              "with FIRESTORE_EMULATOR_HOST (local) or GCP_PROJECT_ID (prod) set.")


if __name__ == "__main__":
    main()
