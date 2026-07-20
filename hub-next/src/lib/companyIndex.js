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

// The company's current pipeline stage if ID8 already tracks it, else null --
// null is the "not in our pipeline yet" signal callers use to offer an
// "Add to pipeline" action instead of a stage badge.
export function lookupStage(index, name) {
  const entry = index[(name || '').trim().toLowerCase()];
  return entry ? entry.stage : null;
}

// Best-effort case-insensitive name match against every VC's recorded
// portfolio -- Tier 1 VCs' deals[] first, then partner VCs' portfolio[].
// Not persisted: recomputed on every page load from whatever's currently in
// topVCs/partnerVCs, so a portfolio added after a company was already in the
// pipeline still attributes correctly on the next view. Returns null when no
// VC's recorded portfolio contains this company -- callers decide how to
// render "no match" (Hot Deals falls back to "Qualified screen"; the
// Watchlist/Pipeline/Qualified Deals tables just show "—").
export function findInvestorSource(companyName, tier1, partners) {
  const nameLc = (companyName || '').trim().toLowerCase();
  if (!nameLc) return null;
  for (const firm of tier1 || []) {
    if ((firm.deals || []).some((d) => d.company.toLowerCase() === nameLc)) {
      return { source: 'Tier 1 VC', via: firm.name, viaHref: `/docs/vcs/tier1/${firm.id}` };
    }
  }
  for (const p of partners || []) {
    if ((p.portfolio || []).some((x) => x.company.toLowerCase() === nameLc)) {
      return { source: 'Partner VC', via: p.trackedBy ? `${p.name} · ${p.trackedBy}` : p.name, viaHref: `/docs/vcs/partner/${p.id}` };
    }
  }
  return null;
}
