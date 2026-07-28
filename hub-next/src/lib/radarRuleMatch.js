// Pure matching logic for the Radar relevance-exclusion list (RADAR_PLAN.md
// §1.6) -- deliberately no 'server-only' import and no Firestore dependency,
// same reasoning as lib/stages.js: this needs to run identically in the
// admin panel's client-side dry-run preview (matching against companies
// already in memory, before a rule is even saved) and in the server-side
// stage-page filter (lib/radarRules.js), so the two can never disagree
// about what a rule would catch.
//
// Word-boundary matching, not substring -- sectorRelevance.js's existing
// EXCLUDED_KEYWORDS check uses plain `text.includes(kw)`, which is fine for
// a short hand-curated list but a real trap for a keyword box anyone can
// type into: 'crypto' would match 'cryptography', silently dropping a
// confidential-compute company. A multi-word phrase (e.g. 'wealth
// management') gets its internal whitespace treated as flexible (one-or-more
// whitespace), so 'wealth  management' or a line-wrapped description still
// matches.
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function ruleRegex(term) {
  const escaped = escapeRegExp(term.trim().toLowerCase()).replace(/\s+/g, '\\s+');
  return new RegExp(`\\b${escaped}\\b`, 'i');
}

// Minimum keyword length before it's allowed to become a rule at all --
// short fragments ('ai', 'it') match almost everything and would silently
// gut the list. Matches the warning the admin panel shows below this length.
export const MIN_KEYWORD_LENGTH = 3;

function textOf(company) {
  return [company?.description, company?.radarCategory, company?.category, company?.industry]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

// rules: { keywords: string[], categories: string[], companies: string[] (slugs) }
// Returns the matched rule as a small descriptor, or null if nothing matches
// (including when keepAnywaySlugs pins this company past a rule that would
// otherwise have caught it) -- callers use the descriptor both to decide
// visibility and to explain *why* a company is hidden.
export function matchExclusionRule(company, rules, keepAnywaySlugs = []) {
  if (!rules) return null;
  if (company?.slug && keepAnywaySlugs.includes(company.slug)) return null;

  if (company?.slug && (rules.companies || []).includes(company.slug)) {
    return { type: 'company', term: company.name || company.slug };
  }

  const category = (company?.radarCategory || company?.category || '').trim().toLowerCase();
  if (category) {
    const catHit = (rules.categories || []).find((c) => c.trim().toLowerCase() === category);
    if (catHit) return { type: 'category', term: catHit };
  }

  const text = textOf(company);
  if (text) {
    const kwHit = (rules.keywords || []).find((kw) => ruleRegex(kw).test(text));
    if (kwHit) return { type: 'keyword', term: kwHit };
  }

  return null;
}

export function isRadarRelevant(company, rules, keepAnywaySlugs = []) {
  return matchExclusionRule(company, rules, keepAnywaySlugs) === null;
}

// Used by the admin panel's live preview -- which currently-kept companies
// (out of a candidate list) would a not-yet-saved term additionally exclude.
// Deliberately ignores categories/companies/keepAnyway: this previews one
// new keyword in isolation, not the combined effect of the whole ruleset.
export function previewKeywordMatches(term, companies, existingKeywords = []) {
  if (!term || term.trim().length < MIN_KEYWORD_LENGTH) return [];
  const alreadyExcluded = new Set(
    companies
      .filter((c) => existingKeywords.some((kw) => ruleRegex(kw).test(textOf(c))))
      .map((c) => c.slug)
  );
  const re = ruleRegex(term);
  return companies.filter((c) => !alreadyExcluded.has(c.slug) && re.test(textOf(c)));
}
