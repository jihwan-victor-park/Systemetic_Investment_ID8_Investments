import { STAGE_BASEPATH } from './stages';

// Cross-references a VC portfolio company (just a name, typed in by hand)
// against ID8's own `companies` collection -- the same "has ID8 actually
// screened this" question Hot Deals already answers when attributing a
// gated company back to a VC's portfolio, just walked in the other
// direction: given a company *name*, has ID8 screened it, and if so what's
// its real fit score and where does it live in the hub. No 'server-only'
// import -- this only touches already-fetched plain data (listCompanies()'s
// output), safe to build in a Server Component and hand the resulting plain
// object down to a Client Component like any other serializable prop.
export function buildCompanyIndex(companies) {
  const map = {};
  for (const c of companies) {
    if (!c.name) continue;
    map[c.name.trim().toLowerCase()] = {
      slug: c.slug,
      stage: c.stage,
      fitScore: c.latestScreen?.fitScore ?? null,
      gate: c.latestScreen?.gate ?? false,
    };
  }
  return map;
}

// The href for "the real company page" if ID8 has screened this name,
// else null -- callers fall back to the VC-portfolio-only drill-in
// (/docs/vcs/company/[slug]) when this returns null.
export function companyHref(index, name) {
  const entry = index[(name || '').trim().toLowerCase()];
  if (!entry) return null;
  const basePath = STAGE_BASEPATH[entry.stage] || STAGE_BASEPATH.qualified;
  return `${basePath}/${entry.slug}`;
}

export function lookupFitScore(index, name) {
  const entry = index[(name || '').trim().toLowerCase()];
  return entry ? entry.fitScore : null;
}
