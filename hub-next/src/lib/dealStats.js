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
// Each row carries the same mandate/access pair as mandateStats, per round:
// `qualified` (deals at that round meeting our mandate) and `pipeline` (the ones
// we got into), plus the rate between them. So the breakdown answers "which
// rounds can we actually get into" -- the question the LP slide is about, and
// invisible from a plain count. `count` is every tracked deal at that round,
// which is what the row's share of the book is measured on.
export function bySeries(companies, { fold = true } = {}) {
  const buckets = new Map();
  for (const c of companies) {
    const label = normalizeSeries(c.round);
    const b = buckets.get(label) || { count: 0, qualified: 0, pipeline: 0, mandate: 0 };
    b.count += 1;
    if (inStage(c, 'qualified')) b.qualified += 1;
    if (inStage(c, 'pipeline')) b.pipeline += 1;
    // Same qualified-union-pipeline denominator mandateStats uses -- see the
    // comment there for why a bare `qualified` denominator produces a 533%.
    if (inStage(c, 'qualified') || inStage(c, 'pipeline')) b.mandate += 1;
    buckets.set(label, b);
  }

  let rows = [...buckets.entries()].map(([label, b]) => ({ label, ...b }));
  if (fold) {
    const canonical = rows.filter((r) => SERIES_ORDER.includes(r.label) || r.label === SERIES_UNKNOWN);
    const other = rows.filter((r) => !SERIES_ORDER.includes(r.label) && r.label !== SERIES_UNKNOWN);
    // One stray round is its own row -- folding a single bucket into "Other
    // rounds" renames it for no gain and hides which round it was.
    if (other.length > 1) {
      const sum = (k) => other.reduce((s, r) => s + r[k], 0);
      rows = [...canonical, {
        label: SERIES_OTHER,
        count: sum('count'),
        qualified: sum('qualified'),
        pipeline: sum('pipeline'),
        mandate: sum('mandate'),
        members: other.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
          .map((r) => `${r.label} (${r.count})`),
      }];
    }
  }

  const total = companies.length;
  return rows
    .map((r) => ({
      ...r,
      pct: total ? (r.count / total) * 100 : 0,
      // Access rate within THIS round -- "we get into 84% of the Series A that
      // fit our mandate" is the finding; that same row's share of the book isn't.
      accessPct: r.mandate ? (r.pipeline / r.mandate) * 100 : null,
    }))
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

// The one ratio the dashboard exists to show, in Oscar's own words (2026-08-13):
// "qualified have our mandate, pipeline are the ones we get access to."
//
//   QUALIFIED = the mandate. Deals that clear ID8's screen -- the market we
//   should be able to play in.
//   PIPELINE  = access. The ones ID8 actually got into.
//   rate      = pipeline / qualified.
//
// This is the live version of the LP sourcing slide's "Deal Count = 117
// Sourced = 25 (21%)". `sourced` is the same idea as that slide's word, kept as
// an alias so the page and the deck use one vocabulary.
//
// THE DENOMINATOR. `stage` is a single funnel POSITION, so a deal that moved
// Qualified -> Pipeline is counted in pipeline and no longer in qualified: the
// two sets are disjoint, not nested. That makes a literal pipeline / qualified
// unsafe as a rate -- a round where more deals advanced than are still sitting
// at Qualified goes over 100% (Series A reads 533% on the 2026-08-13 data: 16
// in pipeline, 3 still qualified). A percentage that can exceed 100% isn't a
// percentage.
//
// So the mandate is qualified UNION pipeline -- every deal that met the screen,
// whether or not it has already advanced -- and access is the pipeline share of
// it. That's the same question ("of our mandate, how much do we get access
// to"), just with a denominator that holds: always <= 100%, and it stops
// swinging every time a deal moves from one stage to the other. On 2026-08-13
// it reads 100 of 293 = 34%.
export function mandateStats(companies) {
  const qualified = companies.filter((c) => inStage(c, 'qualified'));
  const pipeline = companies.filter((c) => inStage(c, 'pipeline'));
  const mandate = companies.filter((c) => inStage(c, 'qualified') || inStage(c, 'pipeline'));
  // BOTH qualified and in pipeline -- Oscar, 2026-08-13: "the ones [that] are
  // both pipeline and qualified / qualified, so that's the real number." The
  // strictest read of access: not just deals we got into, but deals we got into
  // that we had also independently judged to fit the mandate.
  //
  // This is only a real set because the CSV import now writes Attio's stage
  // HISTORY as additive tags (import_attio_deals_csv.stage_history_tags). Stage
  // alone is one funnel position, so a deal that moved Qualified -> Pipeline
  // stops counting as qualified the moment it advances, and this intersection
  // measured 0 of 336 across the entire book. With history folded in, a deal
  // that was Qualified and is now Pipeline carries both.
  const both = mandate.filter((c) => inStage(c, 'qualified') && inStage(c, 'pipeline'));
  return {
    ...ratio(pipeline.length, mandate.length),
    qualifiedCount: qualified.length,
    pipelineCount: pipeline.length,
    investedCount: companies.filter((c) => inStage(c, 'invested')).length,
    mandateTotal: mandate.length,
    // Denominator is `qualified` exactly as asked -- and here that's safe,
    // unlike the headline rate above, because `both` is a SUBSET of qualified
    // by construction, so it can never exceed 100%.
    converted: { ...ratio(both.length, qualified.length), both: both.length },
    // Every doc the public stage bars CAN'T show: 'new' is the untriaged holding
    // bucket, deliberately absent from PUBLIC_STAGES (lib/stages.js), so without
    // this the chart quietly omits real deals and the reader has no way to tell.
    needsTriageCount: companies.filter((c) => c.stage === 'new').length,
  };
}

export function computeDealStats(companies) {
  return {
    total: companies.length,
    byStage: byStage(companies),
    bySeries: bySeries(companies),
    mandate: mandateStats(companies),
  };
}
