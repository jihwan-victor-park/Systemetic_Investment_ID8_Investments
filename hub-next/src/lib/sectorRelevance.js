// Hard, deterministic (no LLM) sector-relevance rule -- the first of two
// passes Oscar wants over the ~1,000-company VC-partner scan: a near-free
// keyword pass to shrink "thousands" down to "hundreds" before the heavier
// (but still lighter-than-Stage-1) pass runs on whatever's left. Default is
// "in scope" unless the company's own text unambiguously matches a
// known-excluded vertical -- a company with no description yet stays
// visible rather than being hidden before anyone's had a chance to read it.
//
// Starting list, not exhaustive -- built from the one concrete example given
// (biotech) plus its obvious life-sciences neighbors; extend
// EXCLUDED_KEYWORDS as more off-thesis verticals come up in practice.
const EXCLUDED_KEYWORDS = [
  'biotech',
  'pharma',
  'therapeutic',
  'life science',
  'drug discovery',
  'clinical trial',
  'medical device',
  'diagnostics',
  'genomic',
  'gene therapy',
  'oncology',
  'agriculture',
  'agtech',
  'farming',
  'real estate',
  'proptech',
];

function textOf(entry) {
  return [entry?.description, entry?.category, entry?.industry].filter(Boolean).join(' ').toLowerCase();
}

export function isSectorInScope(entry) {
  const text = textOf(entry);
  if (!text) return true;
  return !EXCLUDED_KEYWORDS.some((kw) => text.includes(kw));
}

// Stage 0 Portfolio Fit's own weighted score (deal_intelligence/portfolio_fit.py,
// rubric_portfolio.py), 1-4 scale -- written onto each company as `fitScore`
// once the paid research pass has actually run. 3.0 is that rubric's own
// PORTFOLIO_TRACK_THRESHOLD (the "track" cutoff; below it is "monitor"/"drop"),
// so this mirrors the deal list's identical sub-3.0 hide rule at the same
// semantic boundary. A company not yet scored (fitScore missing/undefined --
// large funds over the per-fund cap are deferred, never evaluated) is not
// hidden by this check; only a real sub-3.0 score is a hide reason.
const MIN_FIT_SCORE = 3.0;

function isFitScoreInScope(entry) {
  return typeof entry?.fitScore !== 'number' || entry.fitScore >= MIN_FIT_SCORE;
}

// Portfolio-company scope check -- layers the real deterministic prefilter
// (deal_intelligence/portfolio_prefilter.py: geography NA/Europe, business
// status, no-enrichment-data, AI-relevance keyword+embeddings) on top of this
// file's own lighter keyword check. That Python pass stamps `prefilterPass`/
// `prefilterReason` directly onto each company in partner-vcs-seed.json, so
// this is just reading its verdict, not re-deriving one -- single source of
// truth stays the Python side. `prefilterPass === false` hides the company;
// `true` or missing (funds over 500 companies are deferred, not evaluated,
// so they carry no field at all -- see run_all()'s DEFAULT_MAX_FUND_SIZE)
// falls back to the plain keyword check, same as before this existed. A real
// sub-3.0 fitScore hides it too, same threshold the deal list uses.
export function isPortfolioCompanyInScope(entry) {
  if (entry?.prefilterPass === false) return false;
  if (!isFitScoreInScope(entry)) return false;
  return isSectorInScope(entry);
}
