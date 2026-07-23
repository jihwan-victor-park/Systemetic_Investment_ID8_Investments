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
        except RuntimeError:
            pass  # OPENAI_API_KEY not set -- silently skip this tier

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
    ap.add_argument("--vc", required=True, help='partner VC name, e.g. "1789 Capital"')
    ap.add_argument("--json", action="store_true", help="print full JSON instead of a summary table")
    ap.add_argument("--show-excluded", action="store_true", help="also print excluded companies + reasons")
    ap.add_argument("--no-embeddings", action="store_true",
                     help="skip the embeddings tier even if OPENAI_API_KEY is set (free/offline run)")
    args = ap.parse_args()

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
