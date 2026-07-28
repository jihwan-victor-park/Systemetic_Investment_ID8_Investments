import 'server-only';
import { unstable_cache, revalidateTag } from 'next/cache';
import { db } from './firestore';

// The Radar relevance-exclusion list (RADAR_PLAN.md §1.6) -- editable from
// the Admin page (RadarRulesAdmin.jsx), applied on the Radar tab
// (docs/radar/page.jsx) via lib/radarRuleMatch.js's matchExclusionRule.
// One document, not one-doc-per-rule: the whole list is small (tens of
// entries, not thousands) and always read as a unit, same reasoning as
// stages.js -- no reason to pay for a collection query over a handful of
// strings.
const DOC_REF = () => db().collection('radarRules').doc('current');

// Seeded from sectorRelevance.js's EXCLUDED_KEYWORDS (the existing
// hardcoded off-thesis list for partner-VC portfolios) plus wealth
// management / financial advisory / registered investment adviser --
// added 2026-07-28 after a real case (a wealth-management company that
// arrived through the Top 10 VC workflow legitimately, but reads as clearly
// off-thesis by category and business description). Only used the first
// time this doc is read and doesn't exist yet; every edit after that is
// real, admin-driven state.
const DEFAULT_RULES = {
  keywords: [
    'biotech', 'pharma', 'therapeutic', 'life science', 'drug discovery',
    'clinical trial', 'medical device', 'diagnostics', 'genomic', 'gene therapy',
    'oncology', 'agriculture', 'agtech', 'farming', 'real estate', 'proptech',
    'wealth management', 'financial advisory', 'registered investment adviser',
  ],
  categories: [],
  companies: [],       // manual per-company excludes, by slug -- {slug, name, reason, addedBy, addedAt}
  keepAnyway: [],      // slugs pinned past every current AND future rule -- {slug, name, addedBy, addedAt}
};

function normalizeRules(data) {
  return {
    keywords: (data?.keywords || []).map((k) => (typeof k === 'string' ? k : k.term)).filter(Boolean),
    categories: (data?.categories || []).map((c) => (typeof c === 'string' ? c : c.term)).filter(Boolean),
    companies: data?.companies || [],
    keepAnyway: data?.keepAnyway || [],
    // Raw, richer entries (with addedBy/addedAt) for the admin panel to
    // render provenance -- the plain-string arrays above are what the
    // matcher (radarRuleMatch.js) actually consumes.
    keywordEntries: (data?.keywords || []).map((k) => (typeof k === 'string' ? { term: k } : k)),
    categoryEntries: (data?.categories || []).map((c) => (typeof c === 'string' ? { term: c } : c)),
  };
}

export const getRadarRules = unstable_cache(
  async () => {
    const snap = await DOC_REF().get();
    if (!snap.exists) return normalizeRules(DEFAULT_RULES);
    return normalizeRules(snap.data());
  },
  ['radar-rules'],
  { tags: ['radar-rules'] }
);

async function readRaw() {
  const snap = await DOC_REF().get();
  return snap.exists ? snap.data() : { ...DEFAULT_RULES };
}

export async function addKeywordRule(term, addedBy) {
  const clean = (term || '').trim().toLowerCase();
  if (!clean) throw new Error('empty-term');
  const data = await readRaw();
  const keywords = data.keywords || [];
  const already = keywords.some((k) => (typeof k === 'string' ? k : k.term).toLowerCase() === clean);
  if (!already) {
    keywords.push({ term: clean, addedBy: addedBy || null, addedAt: new Date().toISOString() });
  }
  await DOC_REF().set({ ...data, keywords }, { merge: true });
  revalidateTag('radar-rules');
}

export async function removeKeywordRule(term) {
  const clean = (term || '').trim().toLowerCase();
  const data = await readRaw();
  const keywords = (data.keywords || []).filter(
    (k) => (typeof k === 'string' ? k : k.term).toLowerCase() !== clean
  );
  await DOC_REF().set({ ...data, keywords }, { merge: true });
  revalidateTag('radar-rules');
}

export async function addCompanyExclusion(slug, name, reason, addedBy) {
  if (!slug) throw new Error('missing-slug');
  const data = await readRaw();
  const companies = (data.companies || []).filter((c) => c.slug !== slug);
  companies.push({ slug, name: name || slug, reason: reason || '', addedBy: addedBy || null, addedAt: new Date().toISOString() });
  await DOC_REF().set({ ...data, companies }, { merge: true });
  revalidateTag('radar-rules');
}

export async function removeCompanyExclusion(slug) {
  const data = await readRaw();
  const companies = (data.companies || []).filter((c) => c.slug !== slug);
  await DOC_REF().set({ ...data, companies }, { merge: true });
  revalidateTag('radar-rules');
}

// "Keep anyway" -- pins a company past every CURRENT and FUTURE rule, so
// re-adding a keyword later (e.g. someone re-adds 'wealth' six months from
// now) doesn't silently re-exclude a company a human already vouched for.
// See radarRuleMatch.js's matchExclusionRule -- checked before any rule.
export async function setKeepAnyway(slug, name, keep, addedBy) {
  if (!slug) throw new Error('missing-slug');
  const data = await readRaw();
  const keepAnyway = (data.keepAnyway || []).filter((k) => k.slug !== slug);
  if (keep) {
    keepAnyway.push({ slug, name: name || slug, addedBy: addedBy || null, addedAt: new Date().toISOString() });
  }
  await DOC_REF().set({ ...data, keepAnyway }, { merge: true });
  revalidateTag('radar-rules');
}
