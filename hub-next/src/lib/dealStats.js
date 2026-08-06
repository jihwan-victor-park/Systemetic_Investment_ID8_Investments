// Pure computation over an already-fetched companies[] list (same shape
// listCompanies() returns) -- no I/O, unit-testable with fabricated
// fixtures, same idiom as rubricMath.js. Feeds the summary-statistics
// landing page (Oscar, 2026-08-06: "Basically deals qualified/pipeline (the
// ones we get access to), and other metrics such as trending sectors in our
// qualified deals, amounts maybe, averages of the raises of the companies
// we like, average time between rounds... Be imaginative.").
//
// Every count here is a REAL fact about the data as it exists today, not a
// guess -- a company with no radarCategory/roundSize/etc is excluded from
// that specific metric's denominator rather than counted as a zero, same
// "missing is not zero" convention the rest of this codebase already uses
// (radar_hazard.py, radar_market_heat.py, import_attio_deals_csv.py).

const MS_PER_DAY = 1000 * 60 * 60 * 24;

function byStageCounts(companies) {
  const counts = {};
  for (const c of companies) counts[c.stage] = (counts[c.stage] || 0) + 1;
  return counts;
}

// 'passed'/'qualified'/'radar' etc are ADDITIVE tags on top of `stage` (see
// lib/stages.js's TAGS comment) -- a company can be counted here AND in
// byStageCounts's own bucket at once. Deliberately NOT merged into one
// partition (see project_hub_deal_pipeline_stats_prep memory: "a naive sum
// by stage will double-count").
function byTagCounts(companies, tags) {
  const counts = {};
  for (const tag of tags) counts[tag] = companies.filter((c) => c.tags?.includes(tag)).length;
  return counts;
}

// "Access" cross-tabbed with stage (Oscar: "deals qualified/pipeline (the
// ones we get access to)") -- access is sparse (mostly unrecorded in this
// export), so these are real, currently-small numbers, not "most deals
// have no access" implied by a raw total.
function accessByStage(companies, stages) {
  const out = {};
  for (const stage of stages) {
    const inStage = companies.filter((c) => c.stage === stage || c.tags?.includes(stage));
    out[stage] = {
      total: inStage.length,
      access: inStage.filter((c) => c.access === 'access').length,
      noAccess: inStage.filter((c) => c.access === 'no_access').length,
    };
  }
  return out;
}

// Top sectors (radarCategory is the closest thing to a sector/category tag
// this schema has) among Qualified deals specifically -- "trending sectors
// in our qualified deals." `limit` caps the returned list; ties broken by
// insertion order (first-seen category), not re-sorted alphabetically.
function topSectors(companies, { stage = 'qualified', limit = 8 } = {}) {
  const inStage = companies.filter((c) => c.stage === stage || c.tags?.includes(stage));
  const counts = new Map();
  for (const c of inStage) {
    if (!c.radarCategory) continue;
    counts.set(c.radarCategory, (counts.get(c.radarCategory) || 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([category, count]) => ({ category, count }));
}

// Average/median round size among "companies we like" -- Qualified deals
// with a real roundSize on file. Millions, one decimal.
function raiseSizeStats(companies, { stage = 'qualified' } = {}) {
  const sizes = companies
    .filter((c) => (c.stage === stage || c.tags?.includes(stage)) && c.roundSize)
    .map((c) => c.roundSize)
    .sort((a, b) => a - b);
  if (sizes.length === 0) return { count: 0, avgMillions: null, medianMillions: null };
  const avg = sizes.reduce((s, n) => s + n, 0) / sizes.length;
  const mid = Math.floor(sizes.length / 2);
  const median = sizes.length % 2 ? sizes[mid] : (sizes[mid - 1] + sizes[mid]) / 2;
  return {
    count: sizes.length,
    avgMillions: Math.round((avg / 1_000_000) * 10) / 10,
    medianMillions: Math.round((median / 1_000_000) * 10) / 10,
  };
}

// Average days between rounds for a company with more than one round on
// file -- the ONLY real multi-round dataset in this schema is the
// `companyKey` family import_attio_deals_csv.py's additional-round docs
// create (createAdditionalRound in companies.js uses the same field for
// hand-added rounds too), each carrying its own `roundDate`. A company with
// only one round contributes nothing here (no gap to measure), same
// "excluded from the denominator, not a zero" convention as the rest of
// this module.
function avgDaysBetweenRounds(companies) {
  const families = new Map();
  for (const c of companies) {
    const key = c.companyKey || c.slug;
    if (!families.has(key)) families.set(key, []);
    if (c.roundDate) families.get(key).push(c.roundDate);
  }
  const gaps = [];
  for (const dates of families.values()) {
    if (dates.length < 2) continue;
    const sorted = [...dates].sort();
    for (let i = 1; i < sorted.length; i++) {
      const days = (new Date(sorted[i]) - new Date(sorted[i - 1])) / MS_PER_DAY;
      if (days > 0) gaps.push(days);
    }
  }
  if (gaps.length === 0) return { companiesWithMultipleRounds: 0, avgDays: null };
  return {
    companiesWithMultipleRounds: gaps.length,
    avgDays: Math.round(gaps.reduce((s, d) => s + d, 0) / gaps.length),
  };
}

// Median Stage 1 fit score among Qualified deals -- "the companies we like,"
// quantified rather than just counted.
function medianFitScore(companies, { stage = 'qualified' } = {}) {
  const scores = companies
    .filter((c) => (c.stage === stage || c.tags?.includes(stage)) && c.latestScreen?.fitScore != null)
    .map((c) => c.latestScreen.fitScore)
    .sort((a, b) => a - b);
  if (scores.length === 0) return null;
  const mid = Math.floor(scores.length / 2);
  return Math.round((scores.length % 2 ? scores[mid] : (scores[mid - 1] + scores[mid]) / 2) * 10) / 10;
}

// What fraction of Qualified deals have real Tier 1 / Top 10 backing on
// file -- a concrete "is our pipeline actually Tier-1-adjacent" read,
// distinct from the Partner VC portfolio-match column (this is deal-level
// investor data, see import_attio_deals_csv.py's own docstring).
function tier1BackedRate(companies, { stage = 'qualified' } = {}) {
  const inStage = companies.filter((c) => c.stage === stage || c.tags?.includes(stage));
  if (inStage.length === 0) return { total: 0, top10: 0, tier1_33: 0 };
  return {
    total: inStage.length,
    top10: inStage.filter((c) => c.top10Investors?.length > 0).length,
    tier1_33: inStage.filter((c) => c.tier1_33Investors?.length > 0).length,
  };
}

export function computeDealStats(companies) {
  const PIPELINE_STAGES = ['watchlist', 'pipeline', 'qualified', 'radar', 'invested'];
  return {
    total: companies.length,
    byStage: byStageCounts(companies),
    byTag: byTagCounts(companies, ['passed', 'qualified', 'radar', 'pipeline']),
    accessByStage: accessByStage(companies, PIPELINE_STAGES),
    topSectors: topSectors(companies),
    raiseSizeStats: raiseSizeStats(companies),
    avgDaysBetweenRounds: avgDaysBetweenRounds(companies),
    medianFitScore: medianFitScore(companies),
    tier1BackedRate: tier1BackedRate(companies),
  };
}
