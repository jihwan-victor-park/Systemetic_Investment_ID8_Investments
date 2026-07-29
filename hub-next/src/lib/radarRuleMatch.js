// Matching logic for the Radar keyword filter chips (lib/radarRules.js /
// RadarKeywordFilter.jsx) -- deliberately no 'server-only' import and no
// Firestore dependency, so it runs identically in the client-side filter
// chips and wherever a row's `filterValues.keyword` gets built server-side
// (radarTableColumns.jsx).
//
// Word-boundary matching, not substring -- sectorRelevance.js's existing
// EXCLUDED_KEYWORDS check uses plain `text.includes(kw)`, which is fine for
// a short hand-curated list but a real trap for a keyword box anyone can
// type into: 'crypto' would match 'cryptography', wrongly tagging a
// confidential-compute company as a crypto match. A multi-word phrase (e.g.
// 'wealth management') gets its internal whitespace treated as flexible
// (one-or-more whitespace), so 'wealth  management' or a line-wrapped
// description still matches.
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function ruleRegex(term) {
  const escaped = escapeRegExp(term.trim().toLowerCase()).replace(/\s+/g, '\\s+');
  return new RegExp(`\\b${escaped}\\b`, 'i');
}

// Minimum keyword length before it's allowed to become a chip at all --
// short fragments ('ai', 'it') match almost everything and would make the
// filter useless. Matches the warning RadarKeywordFilter.jsx shows below
// this length.
export const MIN_KEYWORD_LENGTH = 3;

function textOf(company) {
  return [company?.description, company?.radarCategory, company?.category, company?.industry]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

// Every stored keyword term that matches this company's text -- feeds the
// row's `filterValues.keyword` array so SortableTable's filterGroups can
// filter down to whichever chip(s) are toggled on. Purely a view filter now:
// a company matching zero keywords still renders, it just won't show up
// once a keyword chip is active.
export function matchedKeywords(company, keywords = []) {
  const text = textOf(company);
  if (!text) return [];
  return keywords.filter((k) => ruleRegex(k.term || k).test(text)).map((k) => k.term || k);
}
