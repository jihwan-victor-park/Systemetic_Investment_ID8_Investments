"""Embeddings-based AI-relevance signal for the Phase 1 portfolio pre-filter
(see portfolio_prefilter.py). Answers a narrower question than the paid
portfolio_fit LLM pass does: not "how deep/defensible is this company's AI
moat" (that's ai_thesis_fit's real 1-4 judgment, reserved for researched
companies), just "is AI even a plausible relevant concept here at all" --
the coarse recall-favoring signal Phase 1 needs to avoid burning a Perplexity
call on a company with zero chance of clearing that gate.

Why embeddings, not just keywords: category/keyword matching cannot separate
two companies with near-identical PitchBook taxonomy and near-identical
description phrasing but fundamentally different substance -- e.g. "Operator
of a subscription-based publishing platform" (Substack, a real engineering-
built tech company) vs "Operator of a streaming platform intended to tell
stories" (a media/content company with zero AI or tech differentiation).
Neither literally contains an AI keyword, and both use generic SaaS-sounding
language ("platform"). A semantic embedding comparison catches signal that
literal word-overlap can't -- e.g. a description in different words entirely
("reinforcement learning agent for robotic manipulation") still lands near
the positive reference cluster with no shared keyword at all.

Still deterministic: OpenAI's embeddings endpoint is a single forward pass
through a fixed model, no sampling/temperature -- the same input text always
returns the same vector, so this satisfies the same "same input -> same
output, every time" requirement as the rest of Phase 1's checks. What makes
it non-deterministic in the colloquial sense is just that it's an external
API call (network dependency, tiny per-call cost) -- not that its output
varies.

Reference set: mostly the rubric's OWN ai_thesis_fit anchor language
(rubric_portfolio.py PARAMS) rather than an independently invented
classification scheme, so this is a fast/free approximation of the exact
dimension the paid LLM later scores for real -- plus a handful of real
company descriptions (drawn from already-enriched portfolio data, chosen
from OUTSIDE the set of companies this module gets tested against, to avoid
circularity) in company-blurb register, since the rubric anchors themselves
are written for a post-research judgment call, not one-line PitchBook blurbs.

Caching: embeddings are cached to disk keyed by a hash of the exact input
text, so re-running the filter over the same (unchanged) portfolio never
re-calls the API -- keeps cost near zero at repeat-run/large-portfolio scale
and keeps results perfectly reproducible run-to-run (a cached score can't
silently drift if OpenAI ever updates a model's weights under the same name).
"""
import hashlib
import json
import os

import numpy as np

from . import config

EMBED_MODEL = "text-embedding-3-small"
_CACHE_PATH = os.path.join(os.path.dirname(__file__), "output", "ai_relevance_embed_cache.json")

# ── Reference set ────────────────────────────────────────────────────────────

# Rubric's own language (rubric_portfolio.py PARAMS["ai_thesis_fit"]) --
# anchor 1 is the clean negative; 2-4 collectively represent "AI is at least
# plausibly relevant," which is the coarse bar Phase 1 actually needs.
_RUBRIC_NEGATIVE = (
    "No meaningful AI component -- a thin wrapper calling a third-party "
    "foundation-model API with no differentiation."
)
_RUBRIC_POSITIVE = [
    "AI is the core, defensible moat -- proprietary architecture or a "
    "demonstrated data flywheel that is genuinely hard to replicate with a "
    "foundation-model update.",
    "AI is a genuine, evidenced part of the product's value -- real "
    "fine-tuning, a proprietary dataset, or meaningful engineering "
    "investment.",
    "Some AI usage but not clearly structural to the moat -- plausible AI "
    "framing without evidenced depth.",
]

# Real company descriptions in company-blurb register (not rubric-anchor
# register), drawn from already-enriched portfolio data -- deliberately NOT
# overlapping with the companies portfolio_prefilter.py's test run covers
# (Substack, Tucker Carlson Network, Vulcan Elements, Plaid, Neuralink, Juul
# Labs), to keep evaluation non-circular.
_EXAMPLE_POSITIVE = [
    "Developer of artificial intelligence inference hardware and cloud-based "
    "compute services designed for executing machine learning workloads.",
    "Developer of an artificial intelligence platform designed to support "
    "knowledge work through task breakdown and document analysis.",
    "Manufacturer of a wafer-scale artificial intelligence processing "
    "platform intended to provide machine learning by training and "
    "inference of models on a single machine.",
    "Operator of a general-purpose company intended to bridge the gap "
    "between artificial intelligence and the physical world.",
    "Developer of an artificial intelligence research laboratory and "
    "foundational model architecture designed for the secure development "
    "of superhuman intelligence.",
]
_EXAMPLE_NEGATIVE = [
    "Developer of a business intelligence platform designed to make "
    "budgeting and planning easier for small and medium enterprises.",
    "Operator of a campus marketing and events agency intended to help "
    "brands reach students via ambassadors and campus events.",
    "Developer of a data management platform designed for connecting data "
    "buyers with data sellers in a smart, scalable way.",
    "Developer of a talent acquisition platform designed to automate the "
    "sourcing and referral of top-tier passive candidates.",
    "Developer of a cloud-based enterprise performance management software "
    "intended to help businesses in sectors like life sciences, "
    "manufacturing and automation of financial processes.",
]

POSITIVE_REFERENCES = _RUBRIC_POSITIVE + _EXAMPLE_POSITIVE
NEGATIVE_REFERENCES = [_RUBRIC_NEGATIVE] + _EXAMPLE_NEGATIVE


# ── Embedding + cache ────────────────────────────────────────────────────────

def _cache_key(text):
    return hashlib.sha256(f"{EMBED_MODEL}::{text}".encode("utf-8")).hexdigest()


def _load_cache():
    if os.path.exists(_CACHE_PATH):
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache):
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def embed(texts, cache=None):
    """texts: list[str]. Returns list[np.ndarray], one per input, in order.
    Cache-first -- only ever calls the API for text not already cached."""
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to deal_intelligence/.env "
            "yourself (this module never writes secrets to disk) -- see "
            "ai_relevance_embeddings.py's module docstring."
        )
    from openai import OpenAI  # imported lazily so the rest of Phase 1 works with no API key at all

    owns_cache = cache is None
    if owns_cache:
        cache = _load_cache()

    to_fetch = [t for t in texts if _cache_key(t) not in cache]
    if to_fetch:
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        resp = client.embeddings.create(model=EMBED_MODEL, input=to_fetch)
        for text, item in zip(to_fetch, resp.data):
            cache[_cache_key(text)] = item.embedding
        if owns_cache:
            _save_cache(cache)

    return [np.array(cache[_cache_key(t)]) for t in texts]


def _cosine(a, b):
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


def ai_relevance_score(description):
    """Returns (score: float, label: str). score is
    max(similarity to any positive reference) - max(similarity to any
    negative reference) -- positive means closer to the AI-relevant cluster,
    negative means closer to the not-AI cluster. label is a short human-
    readable reason, same transparency convention as the rest of Phase 1."""
    if not description:
        return 0.0, "no description -- neutral"

    cache = _load_cache()
    all_refs = POSITIVE_REFERENCES + NEGATIVE_REFERENCES
    ref_vecs = embed(all_refs, cache=cache)
    desc_vec = embed([description], cache=cache)[0]
    _save_cache(cache)  # persist whatever got newly fetched across both calls above

    n_pos = len(POSITIVE_REFERENCES)
    pos_sims = [_cosine(desc_vec, v) for v in ref_vecs[:n_pos]]
    neg_sims = [_cosine(desc_vec, v) for v in ref_vecs[n_pos:]]
    best_pos, best_neg = max(pos_sims), max(neg_sims)
    score = best_pos - best_neg

    if score > 0.02:
        label = f"embeddings: AI-relevant (+{score:.3f}, closest positive sim={best_pos:.3f})"
    elif score < -0.02:
        label = f"embeddings: not AI-relevant ({score:.3f}, closest negative sim={best_neg:.3f})"
    else:
        label = f"embeddings: ambiguous ({score:.3f}) -- passed through"
    return score, label
