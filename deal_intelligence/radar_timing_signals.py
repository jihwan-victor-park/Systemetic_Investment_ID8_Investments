"""Bridges Stage 1's FIT screen into Radar's TIMING model -- the missing
layer between the two (Oscar, 2026-07-29: "i need a reliable framework").

WHY THIS MODULE EXISTS -- the core insight, worth stating plainly because it
is the thing that makes Radar's heat score trustworthy or not:

    ID8's rubric (rubric.py) scores "is this a good investment."
    Radar asks "is this company about to raise."
    Those are different questions, and the rubric systematically
    UNDER-reports timing evidence.

The proof, from a real screen (Paper, 2026-07-29): its `revenue_growth`
subcategory scored **2** -- the rubric's own "no disclosed revenue, no usable
triangulation" anchor -- while the finding text on that very same
subcategory reads "ARR grew 25x post-Desktop launch." A 25x ARR ramp is
close to the strongest raise-timing signal a private company can emit, and
the fit rubric correctly scored it a 2, because for FIT purposes an
unverifiable number is weak evidence. Reading fit scores as timing signals
would therefore invert the signal on exactly the companies that matter
most: the hypergrowth AI tier that raises again within months.

So this module does two things the scores alone cannot:

1. **Reads the timing-bearing subcategories** (not the whole rubric). A few
   of the rubric's 34 subcategories are, in substance, timing signals
   already -- `timing_motivation`'s top anchor is literally "multiple
   credible term sheet options, company controlling the process," which is
   RADAR_SIGNAL_ENGINE.md §2's F4 "process leakage" family (0-3mo lead,
   "very high" precision) wearing a fit-rubric costume. Those get mapped to
   real hazard kernels.

2. **Extracts growth magnitude from the findings TEXT**, deterministically
   (regex, no LLM -- same convention radar_jobs.classify_postings uses for
   job titles). "ARR grew 25x", "$100M ARR", "6x YoY" are all machine-
   readable and all invisible to a score of 2.

Same pure-function idiom as the rest of the Radar modules: plain data in,
plain data out, no I/O, unit-testable with fabricated inputs.

RESEARCH GROUNDING (2026-07-29, real sources, not assumption):
  - The MEDIAN company's cadence has LENGTHENED -- seed-to-Series-A now
    ~20mo trending to 28mo (eqvista.com/ai-startup-fundraising-trends).
    So "AI raises fast" is not a blanket truth and must not be applied as
    one.
  - The genuinely fast tier is identifiable and revenue-driven: Anthropic
    (3 rounds/9mo), Cyera ($3B->$12B over 4 steps/18mo), Cursor ($100M->
    $2B ARR/13mo) (qubit.capital, fastaijobs.com).
  - That tier's growth shows up in REVENUE, not headcount -- AI-native
    companies run 2-5x higher ARR-per-employee because AI replaces the
    hiring that used to signal scaling (runway.com/blog/
    burn-multiple-benchmarks-for-2026). This is precisely why radar_jobs/
    headcount (family F2) structurally under-detects them, and why this
    module's growth extraction is the higher-value sensor for ID8's
    mandate.
"""
import re

# Subcategory keys whose fit score genuinely carries timing meaning, mapped
# to the hazard kernel they should fire (see radar_hazard.SIGNAL_KERNELS).
# Deliberately a SHORT list -- most of the rubric's 34 subcategories say
# nothing about when a round opens, and pretending otherwise is how a score
# turns into noise.
#
# `min_score` is the threshold at which the signal is considered active;
# `distress_at` (where set) fires the opposite-direction kernel when the
# subcategory bottoms out, per RADAR_SIGNAL_ENGINE.md §2.2's explicit
# requirement that distress be a real branch and not an emergent weighting.
TIMING_SUBCATEGORIES = {
    # "Clearly opportunistic -- positive inflection point, multiple credible
    # term sheet options, company controlling the process" (anchor 4) is F4
    # process leakage: the raise is already in motion and visible.
    "timing_motivation": {
        "kernel": "process_visible", "min_score": 4,
        # Anchor 1 is "Defensive raise -- runway extension, down-round
        # pressure, or limited alternatives visible" -- that LOWERS raise
        # quality and flags distress; never escalate it as opportunity.
        "distress_at": 1, "distress_kernel": "defensive_raise",
    },
    # "Existing Tier-1 investors from prior rounds are confirmed following
    # on alongside the new lead" (anchor 4) -- insiders with information
    # advantage committing more capital, F1-adjacent, constant while true.
    "institutional_momentum": {"kernel": "insiders_following", "min_score": 4},
}

# Growth-magnitude patterns, matched against the findings text of the
# fundamentals/return dimensions. Deterministic and high-recall by design:
# a false positive costs one over-weighted signal (bounded by the composite
# cap), a false negative silently misses the single most predictive fact
# about a hypergrowth company. Ordered most- to least-specific.
_MULTIPLE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*x\s*(?:ARR|revenue|growth|YoY|in\s|\b)", re.IGNORECASE)
_ARR_DOLLARS_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)\s*([MB])\b[^.]{0,30}?ARR", re.IGNORECASE)
_PERCENT_GROWTH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:YoY|year[-\s]over[-\s]year|annual\w*\s+growth|growth)", re.IGNORECASE)

# Growth tiers, calibrated to the research above rather than invented:
#   "hypergrowth" -- the Anthropic/Cyera/Cursor pattern (multi-x ARR inside
#       a year, or $50M+ ARR scale). These raise offensively, on strength,
#       months after the last round, regardless of nominal runway.
#   "strong"      -- real, evidenced growth above the rubric's own $25M/70%
#       bar, but not the compressed-cycle tier.
#   None          -- no extractable growth evidence. NOT "weak": absence of a
#       public number is the normal state for a private company
#       (RADAR_SIGNAL_ENGINE.md §4.3's "absence of signal is not evidence of
#       absence"), so this contributes no signal in either direction.
HYPERGROWTH_MULTIPLE = 3.0     # >=3x on an ARR/revenue basis
HYPERGROWTH_ARR_MILLIONS = 50  # >=$50M ARR, matching the rubric's own top Fundamentals anchor
STRONG_ARR_MILLIONS = 25       # >=$25M ARR, matching the rubric's own anchor-3 bar
STRONG_PERCENT = 70.0          # >=70% YoY, same
HYPERGROWTH_PERCENT = 100.0    # >=100% YoY, same


def _arr_millions(value, unit):
    return float(value) * (1000 if unit.upper() == "B" else 1)


def extract_growth_tier(texts):
    """Scans an iterable of finding/evidence strings for growth magnitude.
    Returns ("hypergrowth" | "strong" | None, [evidence strings that
    matched]) -- the evidence list is returned so the hub can show WHY a
    company reads hot, per RADAR_SIGNAL_ENGINE.md §1's insistence that the
    card carry its own reasoning rather than a bare number."""
    tier = None
    evidence = []

    def _promote(new_tier, text):
        nonlocal tier
        ranks = {None: 0, "strong": 1, "hypergrowth": 2}
        if ranks[new_tier] > ranks[tier]:
            tier = new_tier
        if text not in evidence:
            evidence.append(text)

    for text in texts:
        if not text:
            continue
        for match in _MULTIPLE_RE.finditer(text):
            if float(match.group(1)) >= HYPERGROWTH_MULTIPLE:
                _promote("hypergrowth", text)
        for match in _ARR_DOLLARS_RE.finditer(text):
            arr = _arr_millions(match.group(1), match.group(2))
            if arr >= HYPERGROWTH_ARR_MILLIONS:
                _promote("hypergrowth", text)
            elif arr >= STRONG_ARR_MILLIONS:
                _promote("strong", text)
        for match in _PERCENT_GROWTH_RE.finditer(text):
            pct = float(match.group(1))
            if pct >= HYPERGROWTH_PERCENT:
                _promote("hypergrowth", text)
            elif pct >= STRONG_PERCENT:
                _promote("strong", text)

    return tier, evidence


def _iter_subcategories(screen):
    """Yields (dimension_key, subcategory_key, score, finding) over a
    screens/{date} doc's `dimensions` array (firestore_push.py's shape).
    Tolerates missing/legacy fields rather than raising -- an older screen
    predating rubric v4 simply yields less."""
    for dim in (screen or {}).get("dimensions") or []:
        dim_key = dim.get("key")
        for sub in dim.get("subcategories") or []:
            yield dim_key, sub.get("key"), sub.get("score"), sub.get("finding") or ""


def extract(screen, months_since_screen=0):
    """The public entrypoint. `screen`: a screens/{date} doc dict (or None).
    `months_since_screen`: how old the screen is, used as the kernel age for
    every signal derived from it -- a raise-in-motion signal read from a
    six-month-old screen is genuinely staler than one read today, and
    radar_hazard's kernels already know how to decay that.

    Returns {"signals": [{"key", "monthsSinceEvent"}, ...],
             "growthTier": "hypergrowth"|"strong"|None,
             "growthEvidence": [...],
             "sourceScreenDate": <the screen's own date, for provenance>}
    -- `signals` drops straight into radar_hazard.compute()'s
    active_signals param."""
    if not screen:
        return {"signals": [], "growthTier": None, "growthEvidence": [], "sourceScreenDate": None}

    signals = []
    texts = []
    for dim_key, sub_key, score, finding in _iter_subcategories(screen):
        texts.append(finding)
        rule = TIMING_SUBCATEGORIES.get(sub_key)
        if not rule or score is None:
            continue
        if score >= rule["min_score"]:
            signals.append({"key": rule["kernel"], "monthsSinceEvent": months_since_screen})
        elif rule.get("distress_at") is not None and score <= rule["distress_at"]:
            signals.append({"key": rule["distress_kernel"], "monthsSinceEvent": months_since_screen})

    # Dimension-level `evidence` strings carry growth claims too (often the
    # synthesis names the number the subcategory finding had to truncate to
    # fit its 12-word cap).
    for dim in screen.get("dimensions") or []:
        texts.append(dim.get("evidence") or "")
    texts.append(screen.get("rationale") or "")

    growth_tier, growth_evidence = extract_growth_tier(texts)
    if growth_tier == "hypergrowth":
        signals.append({"key": "hypergrowth_revenue", "monthsSinceEvent": months_since_screen})
    elif growth_tier == "strong":
        signals.append({"key": "strong_revenue_growth", "monthsSinceEvent": months_since_screen})

    return {
        "signals": signals,
        "growthTier": growth_tier,
        "growthEvidence": growth_evidence[:3],  # cap: this is display context, not a dump
        "sourceScreenDate": screen.get("date"),
    }
