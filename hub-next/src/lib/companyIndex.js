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
// Known limitation once a company has more than one tracked round
// (createAdditionalRound in lib/companies.js): this map is keyed by name
// alone, so a second round's doc silently overwrites the first's entry here
// -- portfolio-table/graph cross-references will only ever resolve to
// whichever round happened to be processed last, never both. Fine for now
// (multi-round is schema/logic-ready but not yet in real use); revisit if
// that becomes a problem in practice, e.g. by keying on companyKey+round.
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

// The company's own doc slug if ID8 already tracks it, else null -- lets a
// portfolio row that's already in the pipeline offer RunAnalysisButton
// directly (same "Run Analysis" Stage 1 trigger the Watchlist/Pipeline/
// Qualified Deals tables use) without navigating away from the VC's page.
export function lookupSlug(index, name) {
  const entry = index[(name || '').trim().toLowerCase()];
  return entry ? entry.slug : null;
}

// The company's current pipeline stage if ID8 already tracks it, else null --
// null is the "not in our pipeline yet" signal callers use to offer an
// "Add..." action instead of a stage badge.
export function lookupStage(index, name) {
  const entry = index[(name || '').trim().toLowerCase()];
  return entry ? entry.stage : null;
}

// Best-effort case-insensitive name match against EVERY VC's recorded
// portfolio -- Tier 1 VCs' deals[] first, then partner VCs' portfolio[],
// returning every firm that holds this company, not just the first one
// found (a company like Anduril legitimately sits in several firms'
// portfolios at once). `via` is just the firm's own name -- never the
// internal `trackedBy` contact, which is ID8's own relationship-tracking
// detail, not something to surface next to a company row. Not persisted:
// recomputed on every page load from whatever's currently in topVCs/
// partnerVCs, so a portfolio added after a company was already in the
// pipeline still attributes correctly on the next view.
//
// Every stage table (Watchlist/Pipeline/Qualified/Radar/Invested/Admin/
// Top 10 VC/Hot Deals/hubSearch) used to call this once PER ROW/company,
// each call rescanning every Tier 1 firm's deals[] and every partner's
// portfolio[] from scratch -- O(rows x total portfolio entries), which
// crossed a million comparisons on the bigger stage tables once partner
// portfolios grew past ~2,850 companies (see
// project_partner_vc_portfolio_backfill_jul2026 memory). This walks
// tier1/partners exactly once and builds a name -> matches[] map instead,
// so every row after that is an O(1) lookup via investorMatchesFromIndex.
// A firm only ever contributes one match per company name, even if its
// portfolio data has an accidental duplicate entry for it.
export function buildInvestorIndex(tier1, partners) {
  const index = {};
  const add = (nameLc, entry) => {
    if (!nameLc) return;
    (index[nameLc] || (index[nameLc] = [])).push(entry);
  };
  for (const firm of tier1 || []) {
    const seen = new Set();
    for (const d of firm.deals || []) {
      const nameLc = (d.company || '').trim().toLowerCase();
      if (!nameLc || seen.has(nameLc)) continue;
      seen.add(nameLc);
      add(nameLc, { source: 'Tier 1 VC', via: firm.name, viaHref: `/docs/vcs/tier1/${firm.id}` });
    }
  }
  for (const p of partners || []) {
    const seen = new Set();
    for (const entry of p.portfolio || []) {
      const nameLc = (entry.company || '').trim().toLowerCase();
      if (!nameLc || seen.has(nameLc)) continue;
      seen.add(nameLc);
      add(nameLc, { source: 'Partner VC', via: p.name, viaHref: `/docs/vcs/partner/${p.id}` });
    }
  }
  return index;
}

// O(1) lookup into an index built once by buildInvestorIndex.
export function investorMatchesFromIndex(index, companyName) {
  return index[(companyName || '').trim().toLowerCase()] || [];
}

// Full-detail version of buildInvestorIndex's match, for a single company --
// against Tier 1 deals[] and partner portfolio[], but keeps the raw deal/
// portfolio-entry and firm objects (not just source/via/viaHref) so callers
// can render the same "Deals recorded" / "Partner relationships" tables
// InvestorRelationships expects. Shared by the VC-portfolio drill-in page
// (docs/vcs/company/[slug]) and CompanyDetailPage, so a screened pipeline
// company like Anduril shows the same partner-firm table an unscreened one
// like Honeycomb does, instead of only the drill-in page having it.
export function findInvestorMatches(companyName, tier1, partners) {
  const nameLc = (companyName || '').trim().toLowerCase();
  const tier1Matches = [];
  (tier1 || []).forEach((firm) => {
    (firm.deals || []).forEach((d) => {
      if (d.company.toLowerCase() === nameLc) tier1Matches.push({ d, firm });
    });
  });
  const partnerMatches = [];
  (partners || []).forEach((p) => {
    (p.portfolio || []).forEach((entry) => {
      if (entry.company.toLowerCase() === nameLc) partnerMatches.push({ entry, firm: p });
    });
  });
  return { tier1Matches, partnerMatches };
}
