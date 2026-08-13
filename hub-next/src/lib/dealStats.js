// Pure computation over an already-fetched companies[] list (same shape
// listCompanies() returns) -- no I/O, unit-testable with fabricated fixtures,
// same idiom as rubricMath.js/radarHeatScore.js. Feeds /docs/dashboard.
//
// Every number is derived from the live `companies` collection on each page
// load (the page is force-dynamic, listCompanies() is the only source), so
// nothing here is a hard-coded figure that can go stale -- add a deal in Attio,
// it lands in the hub, and these counts move on the next load.
//
// "Missing is not zero": a company with no Series on file is counted in its own
// explicit "Not recorded" bucket rather than silently dropped or lumped in with
// a real round, the same convention radar_hazard.py / import_attio_deals_csv.py
// already follow. Dropping them would make the series breakdown sum to less
// than the total with no visible explanation.

import { PUBLIC_STAGES, STAGE_LABELS } from './stages';

// A company is "in" a stage if that's its primary `stage` OR it carries the
// stage as an additive tag -- exactly the membership rule every stage tab
// itself uses (see lib/stages.js's TAGS comment, and e.g. pipeline/page.jsx's
// own filter). This is what makes the pipeline-AND-qualified intersection a
// real question at all: `stage` alone is single-valued, so on that field the
// two buckets could never overlap and the ratio would always read 0%.
export function inStage(c, stage) {
  return c.stage === stage || !!c.tags?.includes(stage);
}

// Canonical display order. Anything unrecognized sorts after these, ahead of
// the explicit not-recorded bucket, alphabetically among itself -- so a new
// round label ("Series G", "Growth II") shows up in a sensible place without
// needing this list edited first.
const SERIES_ORDER = [
  'Pre-Seed', 'Seed', 'Series A', 'Series B', 'Series C', 'Series D',
  'Series E', 'Series F', 'Series G', 'Series H', 'Growth', 'Secondary',
];
export const SERIES_UNKNOWN = 'Not recorded';

// Series is a free-text hub field (RoundInput) mirroring an Attio select, so
// the same round arrives spelled several ways -- "series b", "Series B ", and
// a bare "B" are one bucket, not three. Anything that isn't a recognizable
// round is kept VERBATIM (just whitespace-trimmed) rather than forced into
// "Not recorded": "Growth", "Series B1", "Secondary" are all real answers, and
// silently rewriting them would misreport the pipeline's actual composition.
export function normalizeSeries(raw) {
  const s = String(raw ?? '').trim();
  if (!s) return SERIES_UNKNOWN;
  const lower = s.toLowerCase().replace(/\s+/g, ' ');
  const bare = lower.match(/^(?:series\s+)?([a-h])$/);
  if (bare) return `Series ${bare[1].toUpperCase()}`;
  if (lower === 'pre-seed' || lower === 'preseed' || lower === 'pre seed') return 'Pre-Seed';
  if (lower === 'seed') return 'Seed';
  return s;
}

export const SERIES_OTHER = 'Other rounds';

function seriesSortKey(label) {
  if (label === SERIES_OTHER) return [2, label];
  if (label === SERIES_UNKNOWN) return [3, label];
  const i = SERIES_ORDER.indexOf(label);
  return i === -1 ? [1, label] : [0, String(i).padStart(2, '0')];
}

// {label, count, pct} per series, ordered by the canonical round progression
// above rather than by count -- a reader scanning this is asking "where does our
// book sit in the round spectrum", which a count-sorted list destroys.
//
// Everything off the canonical ladder is folded into one "Other rounds" row
// (carrying `members` so the UI can name them on hover). On the real 2026-08-13
// data the raw breakdown runs to 22 buckets, 12 of them holding one or two deals
// -- "Series B SAFE", "Series B Secondary", "Series B1", "Series E3", plus
// PitchBook's generic "Early Stage VC"/"Later Stage VC" placeholders and at
// least one outright bad import ("NEA", an investor name that landed in the
// Series field). Rendering all 22 buries the six rounds that carry 90% of the
// book, and past roughly seven classes a breakdown stops being readable at all.
//
// Folded, NOT dropped: the count still lands in the total, the row is visible,
// and its members are named on hover -- so a mis-imported Series is something a
// reader can notice and go fix, rather than something this function hides.
export function bySeries(companies, { fold = true } = {}) {
  const counts = new Map();
  for (const c of companies) {
    const label = normalizeSeries(c.round);
    counts.set(label, (counts.get(label) || 0) + 1);
  }

  let rows = [...counts.entries()].map(([label, count]) => ({ label, count }));
  if (fold) {
    const canonical = rows.filter((r) => SERIES_ORDER.includes(r.label) || r.label === SERIES_UNKNOWN);
    const other = rows.filter((r) => !SERIES_ORDER.includes(r.label) && r.label !== SERIES_UNKNOWN);
    // One stray round is its own row -- folding a single bucket into "Other
    // rounds" renames it for no gain and hides which round it was.
    if (other.length > 1) {
      rows = [...canonical, {
        label: SERIES_OTHER,
        count: other.reduce((s, r) => s + r.count, 0),
        members: other.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
          .map((r) => `${r.label} (${r.count})`),
      }];
    }
  }

  const total = companies.length;
  return rows
    .map((r) => ({ ...r, pct: total ? (r.count / total) * 100 : 0 }))
    .sort((a, b) => {
      const [ax, ay] = seriesSortKey(a.label);
      const [bx, by] = seriesSortKey(b.label);
      return ax - bx || (ay < by ? -1 : ay > by ? 1 : 0);
    });
}

// {stage, label, count} for every public stage, in PUBLIC_STAGES order. Uses
// the additive membership rule, so these deliberately DO overlap and must
// never be summed into a total -- see `total` on the returned object for the
// one honest whole-universe figure.
export function byStage(companies) {
  return PUBLIC_STAGES.map((stage) => ({
    stage,
    label: STAGE_LABELS[stage],
    count: companies.filter((c) => inStage(c, stage)).length,
  }));
}

function ratio(numerator, denominator) {
  return { numerator, denominator, pct: denominator ? (numerator / denominator) * 100 : null };
}

// The ratios Oscar asked for (2026-08-13), and one correction to how the first
// one has to be measured.
//
//   activeShare -- "number of pipeline/qualified overall": how much of the
//   entire tracked universe is in Pipeline OR Qualified at all, i.e. how much of
//   what we've ever looked at is live rather than parked in Watchlist/Radar or
//   already passed. UNION, not a sum: adding the two counts double-counts
//   anything in both.
//
//   mandateAccess -- "how much percentage of access we have to our mandate."
//   Measured as the access rate WITHIN the mandate universe (Pipeline union
//   Qualified), off Attio's own "Access" attribute -- imported onto
//   `company.access` as 'access'/'no_access' by
//   deal_intelligence/import_attio_deals_csv.py, added 2026-08-06 for exactly
//   this page ("deals qualified/pipeline (the ones we get access to) -- a real
//   dimension for the stats page").
//
//   NOT the literal "pipeline deals which are also qualified": that reads 0 of
//   336 on the 2026-08-13 data, because nothing ever writes the 'qualified'
//   tag (only the `stage`), so `stage` behaves as one funnel POSITION rather
//   than two orthogonal axes -- a deal is filed at qualified or at pipeline,
//   never recorded as both. A headline tile off that intersection would report
//   a storage artifact, not ID8's access. `bothCount` is still returned so the
//   integrity gap stays visible as a count.
//
//   The access field is SPARSE -- 67 of the 273 mandate deals carry a value --
//   so the denominator is recorded deals only, and `recorded`/`unrecorded` come
//   back with it so the page states its own coverage rather than implying that
//   206 unrecorded deals are a "no". Unknown is not no, the same
//   missing-is-not-zero rule as everywhere else here.
export function coverageRatios(companies) {
  const total = companies.length;
  const pipeline = companies.filter((c) => inStage(c, 'pipeline'));
  const qualified = companies.filter((c) => inStage(c, 'qualified'));
  const both = pipeline.filter((c) => inStage(c, 'qualified'));
  const mandate = companies.filter((c) => inStage(c, 'pipeline') || inStage(c, 'qualified'));
  return {
    activeShare: ratio(mandate.length, total),
    mandateAccess: accessRate(mandate),
    // Same rate for each half on its own -- the two run very differently (67%
    // of recorded pipeline deals vs 17% of recorded qualified ones on
    // 2026-08-13), and that gap IS the finding: we get into most of what we
    // actively work, and into few of the deals that merely fit the mandate.
    // One blended number hides it.
    accessByStage: [
      { stage: 'pipeline', ...accessRate(pipeline) },
      { stage: 'qualified', ...accessRate(qualified) },
    ],
    pipelineCount: pipeline.length,
    qualifiedCount: qualified.length,
    mandateCount: mandate.length,
    bothCount: both.length,
    qualifiedNotInPipeline: qualified.filter((c) => !inStage(c, 'pipeline')).length,
    pipelineNotQualified: pipeline.length - both.length,
    // Every doc the public stage bars CAN'T show: 'new' is the untriaged holding
    // bucket, deliberately absent from PUBLIC_STAGES (lib/stages.js), so without
    // this the chart quietly omits real deals and the reader has no way to tell.
    needsTriageCount: companies.filter((c) => c.stage === 'new').length,
  };
}

// Attio's Access attribute over an arbitrary population. `pct` is of RECORDED
// deals, never of the whole population -- treating 'unset' as 'no_access' would
// invent a negative answer for every deal nobody has assessed yet.
function accessRate(population) {
  const access = population.filter((c) => c.access === 'access').length;
  const noAccess = population.filter((c) => c.access === 'no_access').length;
  const recorded = access + noAccess;
  return {
    ...ratio(access, recorded),
    access,
    noAccess,
    recorded,
    unrecorded: population.length - recorded,
    population: population.length,
  };
}

export function computeDealStats(companies) {
  return {
    total: companies.length,
    byStage: byStage(companies),
    bySeries: bySeries(companies),
    ratios: coverageRatios(companies),
  };
}
