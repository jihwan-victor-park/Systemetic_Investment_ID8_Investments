"""Phase 1 deterministic pre-filter for the Portfolio Fit pipeline (see
rubric_portfolio.py's module docstring -- this is the piece it explicitly
scopes out: "the Phase 1 deterministic filter itself... run before any
company reaches this prompt"). Plain code, no LLM calls, no cost -- this
exists so the paid Perplexity pass (portfolio_fit.md, ~$0.01-0.05/company on
`sonar`) only ever runs against companies that could plausibly matter, not
the bulk of a 1,000-9,000+ row portfolio that's obviously out of mandate.

Three checks, each independently gate-able and each returning a reason
string when it excludes a company (never a silent drop -- same
"hard_auto_pass_reason" transparency convention as stage1_fit.py/
rubric_portfolio.py):

  1. Geography -- NA/Europe only, per the fund thesis's stated screen
     (see project_fund_thesis memory: "headquartered in North America or
     Europe only"). hqLocation is a free-text "City, State"/"City, Country"
     string, not a region code -- see _classify_region().
  2. Business status -- excludes confirmed-dead companies (Out of
     Business). Does NOT currently catch Acquired/IPO -- see the
     KNOWN GAP note below.
  3. AI/tech relevance -- a high-recall, keyword/vertical-based filter.
     This is NOT the AI hard-gate itself (that's portfolio_fit's own
     hard_auto_pass, decided by the model after real research) -- it only
     needs to cut the obviously-irrelevant bulk (restaurants, apparel,
     mining, etc.) cheaply. When ambiguous, it passes the company through
     rather than guessing wrong and starving the LLM stage of a real AI
     company. See _ai_relevant()'s docstring for the exact reasoning.

KNOWN GAP -- Acquired/IPO exclusion is not implemented: PitchBook splits a
company's status into two separate fields -- "Business Status" (Generating
Revenue, Profitable, Startup, Out of Business, clinical-trial phases -- what
`businessStatus` on a portfolio entry actually stores today) and a separate
"Ownership Status" (Acquired/Merged, Publicly Held, In IPO Registration --
NOT currently captured anywhere in partner-vcs-seed.json's portfolio schema).
prompts/portfolio_fit.md documents the intended exclusion as "businessStatus
(not Acquired/IPO/Out of Business)", but that can only ever fire for
Out-of-Business today, because the other two values live in a field nobody
enriches yet. Fix is to add `ownershipStatus` to the Phase 0 enrichment pass
(pitchbook_get_profile's "Ownership Status" field) and check it here -- flagged,
not silently faked.

Stage (Series B+) is deliberately NOT a Phase 1 exclusion. portfolio_fit.md
already handles sub-Series-B companies via `too_early: true` -- scored for
real, benched rather than dropped, so a strong early-stage company isn't
thrown away. Duplicating that as a hard filter here would contradict an
already-made design decision.

Usage:
    python -m deal_intelligence.portfolio_prefilter --vc "1789 Capital"
    python -m deal_intelligence.portfolio_prefilter --vc "1789 Capital" --json
"""
import argparse
import json
import os
import re
import sys

SEED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "hub-next", "scripts", "data", "partner-vcs-seed.json"
)

# ── Geography ────────────────────────────────────────────────────────────────

US_STATE_ABBREVS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

NA_COUNTRIES = {"united states", "usa", "u.s.", "u.s.a.", "canada", "mexico"}

# Real PitchBook country strings seen on hqLocation across this dataset's
# enriched companies, plus the rest of the EU/EEA + UK (the fund thesis's
# "Europe" is used in the LP-deck sense -- broad Western/Northern Europe, not
# a strict EU-membership test). Extend as new countries actually show up.
EUROPE_COUNTRIES = {
    "united kingdom", "uk", "ireland", "france", "germany", "spain", "italy",
    "netherlands", "belgium", "switzerland", "austria", "sweden", "norway",
    "denmark", "finland", "portugal", "poland", "czech republic", "greece",
    "luxembourg", "iceland", "estonia", "latvia", "lithuania", "hungary",
    "romania", "bulgaria", "croatia", "slovenia", "slovakia",
}


def _classify_region(hq_location):
    """hqLocation is free text ("San Francisco, CA" / "Toronto, Canada" /
    "London, United Kingdom") -- not a region code. Returns "NA", "Europe",
    "other", or None (couldn't parse / no comma -- treated as unknown, not
    excluded; see PortfolioPrefilterResult).
    """
    if not hq_location or "," not in hq_location:
        return None
    tail = hq_location.rsplit(",", 1)[-1].strip()
    tail_lc = tail.lower()
    if tail.upper() in US_STATE_ABBREVS:
        return "NA"
    if tail_lc in NA_COUNTRIES:
        return "NA"
    if tail_lc in EUROPE_COUNTRIES:
        return "Europe"
    return "other"


# ── No enrichment data at all ───────────────────────────────────────────────

# ~65% of rows across the full partner-VC universe (6,813 of 10,536 as of
# this writing) have never been touched by any enrichment pass -- no
# hqLocation, businessStatus, description, category, or vertical. Oscar's
# call: treat a company Perplexity/PitchBook couldn't find anything on as
# more likely dead/stale than as "real company, just unlucky" -- skip it
# rather than let it silently ride through tier 4 of _ai_relevant() the way
# it used to. This is a deliberate reversal of this module's original
# "when in doubt, pass it through" default, scoped to the single case where
# there is NOTHING to go on at all (every other ambiguous case below still
# passes through as before).
_ENRICHMENT_FIELDS = ("hqLocation", "businessStatus", "description", "category", "vertical")


def _has_any_enrichment(company):
    return any((company.get(f) or "").strip() for f in _ENRICHMENT_FIELDS)


# ── Business status ─────────────────────────────────────────────────────────

# Only "Out of Business" is reliably excludable today -- see KNOWN GAP above
# for why Acquired/IPO can't be checked yet.
EXCLUDED_BUSINESS_STATUSES = {"out of business"}


# ── AI / tech relevance ──────────────────────────────────────────────────────

# PitchBook's own vertical tags that directly indicate AI relevance --
# multi-tag field, so this is a substring/set-membership check against the
# comma-split vertical list, not an exact match on the whole field.
AI_VERTICAL_TAGS = {
    "artificial intelligence & machine learning",
    "generative ai",
    "llm agents",
    "artificial general intelligence (agi) research",
    "robotic foundation models",
}

# Free-text fallback when vertical is missing/inconclusive -- checked against
# category + industry + description. Deliberately high-recall (a false
# positive here just costs one cheap `sonar` call that the model will
# hard_auto_pass anyway; a false negative silently throws away a real AI
# company before it's ever seen). Do not tighten this list to be "precise" --
# that's portfolio_fit's own paid research pass's job, not this one's.
AI_KEYWORDS = [
    "artificial intelligence", r"\bai\b", "machine learning", r"\bml\b",
    "neural network", r"\bllm\b", "large language model", "foundation model",
    "generative", "computer vision", r"\bnlp\b", "natural language processing",
    "deep learning", "autonomous", "predictive model", "algorithm-driven",
    "agentic",
]
_AI_KEYWORD_RE = re.compile("|".join(AI_KEYWORDS), re.IGNORECASE)

_embeddings_warned = False


def _warn_embeddings_unavailable(exc):
    """Prints once per process, not once per company -- a portfolio pass
    touches thousands of rows, and an outage/missing-key reason doesn't
    change row to row."""
    global _embeddings_warned
    if _embeddings_warned:
        return
    _embeddings_warned = True
    # stderr, not stdout -- --json/--all pipes stdout as machine-readable
    # output (see refresh_portfolio_prefilter.sh), and this would otherwise
    # land ahead of the JSON and break every consumer's parser.
    print(f"[portfolio_prefilter] embeddings tier unavailable, falling back to category-only: {exc}", file=sys.stderr)


# Industry/category values observed in this dataset that are definitively
# non-tech -- a company landing here with NO AI vertical/keyword hit anywhere
# has no realistic path through portfolio_fit's AI hard-gate. Conservative by
# design: only sectors with zero plausible tech/AI overlap. Extend as new
# categories show up; when in doubt, leave a category OUT of this set (pass
# it through) rather than risk excluding a real company.
NON_TECH_CATEGORIES = {
    "restaurants, hotels and leisure", "consumer non-durables",
    "metals, minerals and mining", "other materials", "consumer durables",
    "apparel and accessories (b2c)", "food products", "beverages",
}


def _ai_relevant(vertical, category, industry, description, use_embeddings=True):
    """Returns (relevant: bool, reason: str). Four tiers, in order, each only
    reached if the cheaper one before it was inconclusive:

    1. vertical has an explicit AI tag -> relevant, high confidence, free.
    2. keyword hit in category/industry/description -> relevant, free.
    3. Embeddings similarity (see ai_relevance_embeddings.py) -- catches the
       cases keywords/category structurally can't: two companies with
       near-identical PitchBook taxonomy and description phrasing but
       fundamentally different substance (e.g. "subscription publishing
       platform" vs "streaming platform" -- one a real tech company, one
       pure media, neither containing a literal AI keyword). Skipped
       entirely if OPENAI_API_KEY isn't set (or use_embeddings=False) --
       falls through to tier 4 unchanged, so this filter keeps working with
       no API key at all, just with less discriminating power on exactly
       this class of ambiguous case.
    4. category is a confirmed non-tech sector with no signal from any tier
       above -> not relevant. Otherwise -> relevant (pass through). Missing
       data everywhere (the ~9,000 rows not yet enriched) lands here and
       passes -- correct, we simply don't know anything about it yet.
    """
    vertical_tags = {v.strip().lower() for v in (vertical or "").split(",") if v.strip()}
    if vertical_tags & AI_VERTICAL_TAGS:
        hit = next(iter(vertical_tags & AI_VERTICAL_TAGS))
        return True, f"vertical tag: {hit}"

    text = " ".join(filter(None, [category, industry, description]))
    keyword_hit = _AI_KEYWORD_RE.search(text)
    if keyword_hit:
        return True, f"keyword match: {keyword_hit.group(0)!r}"

    if use_embeddings and description:
        try:
            from . import ai_relevance_embeddings as aie
            score, label = aie.ai_relevance_score(description)
            if score > 0.02:
                return True, label
            if score < -0.02:
                return False, label
            # else: ambiguous -- fall through to tier 4 below, same as if
            # embeddings were never consulted at all.
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: key
            # missing, quota exhausted, rate limited, network down, numpy/
            # openai not installed, anything. This tier is best-effort --
            # never crash a filter pass over a multi-thousand-company
            # portfolio for it; skip and warn once (not per-company) so a
            # real outage doesn't silently masquerade as "no company had AI
            # signal" (every row just quietly falling to tier 4 instead).
            _warn_embeddings_unavailable(exc)

    cat_lc = (category or "").strip().lower()
    if cat_lc in NON_TECH_CATEGORIES and not keyword_hit:
        return False, f"non-tech category ({category}), no AI signal anywhere"

    return True, "insufficient data to exclude -- passed through"


# ── Combined filter ──────────────────────────────────────────────────────────

def evaluate(company, use_embeddings=True):
    """company: one portfolio-array dict (company, category, industry,
    description, vertical, hqLocation, businessStatus, ...).
    Returns {"pass": bool, "reasons": [...]} -- reasons is always populated
    (why it passed, or why/which check excluded it), never a bare boolean.
    """
    reasons = []

    if not _has_any_enrichment(company):
        return {"pass": False, "reasons": ["no enrichment data on file (no hqLocation/businessStatus/"
                                            "description/category/vertical) -- skipped, likely stale or dead"]}

    status = (company.get("businessStatus") or "").strip().lower()
    if status in EXCLUDED_BUSINESS_STATUSES:
        return {"pass": False, "reasons": [f"businessStatus excluded: {company.get('businessStatus')}"]}

    region = _classify_region(company.get("hqLocation"))
    if region == "other":
        return {"pass": False, "reasons": [f"hqLocation outside NA/Europe: {company.get('hqLocation')}"]}
    reasons.append(f"geography: {region or 'unknown (passed through)'}")

    ai_ok, ai_reason = _ai_relevant(
        company.get("vertical"), company.get("category"),
        company.get("industry"), company.get("description"),
        use_embeddings=use_embeddings,
    )
    if not ai_ok:
        return {"pass": False, "reasons": reasons + [ai_reason]}
    reasons.append(ai_reason)

    return {"pass": True, "reasons": reasons}


def filter_companies(companies, use_embeddings=True):
    """Splits a portfolio list into (passed, excluded), each item annotated
    with its evaluate() result under the "_prefilter" key."""
    passed, excluded = [], []
    for c in companies:
        result = evaluate(c, use_embeddings=use_embeddings)
        annotated = {**c, "_prefilter": result}
        (passed if result["pass"] else excluded).append(annotated)
    return passed, excluded


# Funds this size or larger are accelerator/syndicate-style portfolios
# (Antler, Capital Factory, Gaingels, ...) that dwarf everything else in the
# dataset -- 4 funds alone account for 6,758 of 10,536 companies (64%) as of
# this writing. Deliberately deferred, not excluded: `run_all()` leaves every
# company in an oversized fund completely untouched (no prefilterPass field
# at all) rather than writing a verdict for them, so "not yet evaluated"
# stays visibly distinct from "evaluated and rejected" -- revisit once the
# rest of the universe is under control.
DEFAULT_MAX_FUND_SIZE = 500


def run_all(seed_path=SEED_PATH, max_fund_size=DEFAULT_MAX_FUND_SIZE, use_embeddings=True, persist=False):
    """Runs evaluate() over every company in every VC fund at or under
    max_fund_size, stamping "prefilterPass"/"prefilterReason" directly onto
    each company dict in place -- the label Oscar asked for so a later
    full-scale (paid) analysis pass can filter on `prefilterPass is True`
    without recomputing anything. Stage/Series-B+ is deliberately NOT
    considered here (see module docstring) -- this is geography +
    business-status + no-enrichment-data + AI-relevance only.

    Returns a summary dict; writes seed_path back to disk iff persist=True
    (dry-run by default -- this mutates a real, committed data file).
    """
    with open(seed_path, encoding="utf-8") as f:
        data = json.load(f)

    deferred_funds, evaluated_funds = [], []
    total_pass = total_excluded = total_deferred = 0
    exclude_reasons = {}

    for vc in data:
        portfolio = vc.get("portfolio", [])
        if len(portfolio) > max_fund_size:
            deferred_funds.append((vc["name"], len(portfolio)))
            total_deferred += len(portfolio)
            continue
        evaluated_funds.append((vc["name"], len(portfolio)))
        for company in portfolio:
            result = evaluate(company, use_embeddings=use_embeddings)
            company["prefilterPass"] = result["pass"]
            company["prefilterReason"] = " · ".join(result["reasons"])
            if result["pass"]:
                total_pass += 1
            else:
                total_excluded += 1
                # reasons[-1] is always the one that actually decided the
                # exclusion -- reasons[0] can instead be an earlier
                # informational note (e.g. "geography: NA") logged before an
                # AI-relevance check further down the chain is what actually
                # excluded the company.
                key = result["reasons"][-1].split(":")[0].split("(")[0].strip()
                exclude_reasons[key] = exclude_reasons.get(key, 0) + 1

    if persist:
        with open(seed_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return {
        "funds_evaluated": len(evaluated_funds),
        "funds_deferred": deferred_funds,
        "companies_deferred": total_deferred,
        "companies_evaluated": total_pass + total_excluded,
        "companies_pass": total_pass,
        "companies_excluded": total_excluded,
        "exclude_reasons": exclude_reasons,
        "persisted": persist,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def _load_vc_portfolio(vc_name):
    with open(SEED_PATH, encoding="utf-8") as f:
        data = json.load(f)
    for vc in data:
        if vc["name"].strip().lower() == vc_name.strip().lower():
            return vc["name"], vc.get("portfolio", [])
    available = ", ".join(sorted(v["name"] for v in data))
    raise SystemExit(f"No VC named {vc_name!r} in {SEED_PATH}.\nAvailable: {available}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vc", help='partner VC name, e.g. "1789 Capital" (omit when using --all)')
    ap.add_argument("--all", action="store_true",
                    help="run every fund at/under --max-fund-size and stamp prefilterPass/prefilterReason "
                         "onto partner-vcs-seed.json (see run_all())")
    ap.add_argument("--max-fund-size", type=int, default=DEFAULT_MAX_FUND_SIZE,
                    help=f"funds with more portfolio companies than this are deferred, not evaluated "
                         f"(default {DEFAULT_MAX_FUND_SIZE})")
    ap.add_argument("--persist", action="store_true",
                    help="--all only: write the stamped labels back to partner-vcs-seed.json "
                         "(default is a dry run that only prints the summary)")
    ap.add_argument("--json", action="store_true", help="print full JSON instead of a summary table")
    ap.add_argument("--show-excluded", action="store_true", help="also print excluded companies + reasons")
    ap.add_argument("--no-embeddings", action="store_true",
                     help="skip the embeddings tier even if OPENAI_API_KEY is set (free/offline run)")
    args = ap.parse_args()

    if args.all:
        summary = run_all(max_fund_size=args.max_fund_size, use_embeddings=not args.no_embeddings, persist=args.persist)
        if args.json:
            print(json.dumps(summary, indent=2))
            return
        print(f"Funds evaluated (<= {args.max_fund_size} companies): {summary['funds_evaluated']}")
        print(f"Funds deferred (> {args.max_fund_size} companies): {len(summary['funds_deferred'])}"
              f" ({summary['companies_deferred']} companies)")
        for name, n in sorted(summary["funds_deferred"], key=lambda x: -x[1]):
            print(f"  DEFERRED  {name:<30} {n} companies")
        print()
        print(f"Companies evaluated: {summary['companies_evaluated']}")
        print(f"  PASS:     {summary['companies_pass']}")
        print(f"  EXCLUDE:  {summary['companies_excluded']}")
        for reason, n in sorted(summary["exclude_reasons"].items(), key=lambda x: -x[1]):
            print(f"    {n:5d}  {reason}")
        print()
        print("Persisted to disk." if summary["persisted"] else "Dry run -- rerun with --persist to write labels to disk.")
        return

    if not args.vc:
        ap.error("--vc is required unless --all is given")

    name, portfolio = _load_vc_portfolio(args.vc)
    passed, excluded = filter_companies(portfolio, use_embeddings=not args.no_embeddings)

    if args.json:
        print(json.dumps({"vc": name, "passed": passed, "excluded": excluded}, indent=2))
        return

    print(f"{name}: {len(portfolio)} companies -> {len(passed)} pass, {len(excluded)} excluded\n")
    for c in passed:
        print(f"  PASS     {c['company']:<40} {' · '.join(c['_prefilter']['reasons'])}")
    if args.show_excluded:
        print()
        for c in excluded:
            print(f"  EXCLUDE  {c['company']:<40} {' · '.join(c['_prefilter']['reasons'])}")


if __name__ == "__main__":
    main()
