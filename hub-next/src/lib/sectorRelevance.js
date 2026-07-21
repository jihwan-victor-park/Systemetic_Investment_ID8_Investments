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
