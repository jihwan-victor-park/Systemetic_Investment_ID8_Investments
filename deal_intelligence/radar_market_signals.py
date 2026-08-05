"""Perplexity-backed research for the Heat Score Signal Framework's rows
that have no free/direct-API source (Oscar, 2026-07-30/2026-08-05: "I have
the perplexity API... do the [research] to get the rest of it"). One
bounded, cheap Perplexity call per company (model="sonar",
search_context_size="low" -- this needs a handful of public facts, not
deep research) answers four questions that feed SIX of
radar_market_heat.py's rows:

  - News Volume (`newsVolume`)
  - Step-Up (`stepUp`, approximate -- see radar_market_heat.py's own
    step_up() docstring on why it can only be a rough up/flat/down read,
    never the sheet's precise 2.0x+/1.5-2.0x/etc bands)
  - Monthly Website Visits Growth (`websiteVisitsGrowth`, only when a
    public source actually reports a traffic trend -- rare, and this says
    so honestly rather than guessing)
  - ONE "public momentum" read that backs THREE rows identically
    (`crunchbaseGrowthScore`/`crunchbaseHeatScore`/`crunchbaseSurgeScore`
    -- see radar_market_heat.py's own crunchbase_proxy() docstring on why
    those 3 rows share one read rather than three independent
    measurements: their real numbers only exist inside a paid, logged-in
    Crunchbase Pro session, and displaying a Perplexity-derived guess
    under a competitor's own branded metric name would misrepresent it as
    their real number)

Same "unknown is a legitimate, expected answer" convention as
stage1_fit.py's own rubric -- a private company with no public coverage of
its traffic/valuation history is the NORMAL case, not a research failure,
and the model is told explicitly not to guess when evidence doesn't exist.
Same identity-discipline requirement as stage1_fit.py carries (the real
Atoms/Atoms incident, 2026-07-30) -- name + domain + description are all
given as identity anchors, with the same same-name-different-company
warning.
"""
from . import config
from .research import perplexity, _extract_json

MODEL = "sonar"
SEARCH_CONTEXT_SIZE = "low"

_SYSTEM = (
    "You are a careful research analyst. You answer ONLY with a single JSON "
    "object, no prose before or after. Every field must be grounded in a "
    "real, citable public source -- if you cannot find public evidence for "
    "a field, answer \"unknown\" for it. Guessing or estimating without "
    "evidence is a worse answer than \"unknown\" and will be treated as a "
    "fabrication, not a helpful answer."
)

_PROMPT_TEMPLATE = """Research the company below using public web sources only.

Company name: {name}
Company domain: {domain}
Known business description: {description}

IMPORTANT -- company identity: multiple unrelated companies can share the
same or a similar name. Before using ANY source, confirm it is actually
about the company at the domain above (matching the business description),
not a different, unrelated company that happens to share a name. If a
source is ambiguous or about a different company, ignore it entirely.

Answer these four questions about THIS company, using ONLY what you can
find public evidence for. "unknown" is a normal, expected, and CORRECT
answer for a private company with no public coverage on a given topic --
do not guess or extrapolate just to avoid saying "unknown".

1. News volume: over the last ~90 days, is there "high" (multiple articles/
   press mentions), "steady" (occasional/baseline coverage), "low" (little
   to no coverage), or "unknown" (can't determine) volume of press coverage?
2. Public momentum: based on public signals (funding rumors, notable hires,
   product launches, partnerships, expansion news, analyst commentary), is
   there "strong", "moderate", "weak", or "unknown" evidence of rising
   public/market momentum for this company right now?
3. Valuation step-up: if this company's most recent funding round's
   valuation AND the round before that are BOTH publicly disclosed, is the
   most recent one "up", "flat", or "down" vs. the prior one? If either
   valuation isn't publicly disclosed, answer "unknown".
4. Website traffic trend: if a public source (news article, a Semrush/
   SimilarWeb public report, etc.) explicitly reports this company's
   website traffic trend, is it "rising", "flat", or "declining"? If no
   such public report exists, answer "unknown".

Respond with ONLY this JSON shape:
{{"newsVolume": "high|steady|low|unknown", "newsEvidence": "one sentence + a citation URL, or empty if unknown",
  "publicMomentum": "strong|moderate|weak|unknown", "momentumEvidence": "one sentence + a citation URL, or empty if unknown",
  "valuationStepUp": "up|flat|down|unknown", "valuationEvidence": "one sentence + a citation URL, or empty if unknown",
  "websiteTrafficTrend": "rising|flat|declining|unknown", "trafficEvidence": "one sentence + a citation URL, or empty if unknown"}}
"""

_VALID = {
    "newsVolume": {"high", "steady", "low"},
    "publicMomentum": {"strong", "moderate", "weak"},
    "valuationStepUp": {"up", "flat", "down"},
    "websiteTrafficTrend": {"rising", "flat", "declining"},
}
_EVIDENCE_KEY = {
    "newsVolume": "newsEvidence", "publicMomentum": "momentumEvidence",
    "valuationStepUp": "valuationEvidence", "websiteTrafficTrend": "trafficEvidence",
}


def research(name, domain, description):
    """One Perplexity call. Returns a plain dict:
    {newsVolume, publicMomentum, valuationStepUp, websiteTrafficTrend}
    (each a valid categorical string or None -- "unknown" from the model
    is normalized to None here, the same missing-not-zero convention every
    other Radar signal already uses) plus each field's *Evidence string and
    a `citations` list.

    Returns None on any failure (no API key, network error, unparseable
    response) -- caller treats that exactly like every field reading
    "unknown", never as a zero."""
    if not config.PERPLEXITY_API_KEY:
        return None
    prompt = _PROMPT_TEMPLATE.format(
        name=name or "unknown", domain=domain or "unknown",
        description=description or "not on file",
    )
    try:
        content, citations = perplexity(
            prompt, model=MODEL, system=_SYSTEM, temperature=0,
            search_context_size=SEARCH_CONTEXT_SIZE, max_tokens=600,
        )
    except Exception:
        return None
    data = _extract_json(content) if content else None
    if not isinstance(data, dict):
        return None

    out = {"citations": citations}
    for field, valid_values in _VALID.items():
        value = data.get(field)
        out[field] = value if value in valid_values else None
        out[_EVIDENCE_KEY[field]] = data.get(_EVIDENCE_KEY[field]) or None
    return out
