import { describe, it, expect } from 'vitest';
import {
  bySeries, byStage, computeDealStats, coverageRatios, inStage, normalizeSeries,
  SERIES_OTHER, SERIES_UNKNOWN,
} from './dealStats';

const co = (slug, { stage = 'watchlist', tags = [], round = null, access = null } = {}) =>
  ({ slug, stage, tags, round, access });

describe('inStage', () => {
  it('matches the primary stage', () => {
    expect(inStage(co('a', { stage: 'pipeline' }), 'pipeline')).toBe(true);
  });

  it('matches an additive tag on a company whose primary stage is something else', () => {
    // The whole reason the pipeline-AND-qualified intersection is meaningful.
    expect(inStage(co('a', { stage: 'pipeline', tags: ['qualified'] }), 'qualified')).toBe(true);
  });

  it('is false for a stage the company has neither way', () => {
    expect(inStage(co('a', { stage: 'watchlist' }), 'pipeline')).toBe(false);
  });

  it('tolerates a company with no tags array', () => {
    expect(inStage({ slug: 'a', stage: 'watchlist' }, 'pipeline')).toBe(false);
  });
});

describe('normalizeSeries', () => {
  it('folds spelling and spacing variants of the same round together', () => {
    expect(normalizeSeries('series b')).toBe('Series B');
    expect(normalizeSeries('  Series B  ')).toBe('Series B');
    expect(normalizeSeries('B')).toBe('Series B');
  });

  it('normalizes seed spellings', () => {
    expect(normalizeSeries('Seed')).toBe('Seed');
    expect(normalizeSeries('preseed')).toBe('Pre-Seed');
    expect(normalizeSeries('pre seed')).toBe('Pre-Seed');
  });

  it('keeps a real but non-standard round verbatim instead of hiding it', () => {
    // "Growth"/"Series B1" are genuine answers; rewriting them to "Not
    // recorded" would misreport the pipeline's actual composition.
    expect(normalizeSeries('Growth')).toBe('Growth');
    expect(normalizeSeries('Series B1')).toBe('Series B1');
  });

  it('buckets a genuinely absent series explicitly', () => {
    expect(normalizeSeries(null)).toBe(SERIES_UNKNOWN);
    expect(normalizeSeries('')).toBe(SERIES_UNKNOWN);
    expect(normalizeSeries('   ')).toBe(SERIES_UNKNOWN);
  });
});

describe('bySeries', () => {
  it('counts the folded buckets and sums to the total', () => {
    const companies = [
      co('a', { round: 'Series B' }), co('b', { round: 'series b' }), co('c', { round: 'B' }),
      co('d', { round: 'Seed' }), co('e', { round: null }),
    ];
    const rows = bySeries(companies);
    expect(rows.find((r) => r.label === 'Series B').count).toBe(3);
    expect(rows.find((r) => r.label === 'Seed').count).toBe(1);
    expect(rows.find((r) => r.label === SERIES_UNKNOWN).count).toBe(1);
    expect(rows.reduce((s, r) => s + r.count, 0)).toBe(companies.length);
  });

  it('orders by the round progression, not by count', () => {
    const companies = [
      co('a', { round: 'Series C' }), co('b', { round: 'Series C' }), co('c', { round: 'Series C' }),
      co('d', { round: 'Seed' }),
    ];
    expect(bySeries(companies).map((r) => r.label)).toEqual(['Seed', 'Series C']);
  });

  it('puts an unrecognized round after the known ones and the unknown bucket last', () => {
    const companies = [
      co('a', { round: null }), co('b', { round: 'Zebra Round' }), co('c', { round: 'Series A' }),
    ];
    expect(bySeries(companies).map((r) => r.label)).toEqual(['Series A', 'Zebra Round', SERIES_UNKNOWN]);
  });

  it('reports percentages of the whole universe', () => {
    const rows = bySeries([co('a', { round: 'Seed' }), co('b', { round: 'Series A' })]);
    expect(rows.every((r) => r.pct === 50)).toBe(true);
  });

  it('is empty rather than throwing on no companies', () => {
    expect(bySeries([])).toEqual([]);
  });
});

describe('byStage', () => {
  it('counts a company in every stage it belongs to, primary or tagged', () => {
    const companies = [co('a', { stage: 'pipeline', tags: ['qualified'] })];
    const rows = byStage(companies);
    expect(rows.find((r) => r.stage === 'pipeline').count).toBe(1);
    expect(rows.find((r) => r.stage === 'qualified').count).toBe(1);
    expect(rows.find((r) => r.stage === 'watchlist').count).toBe(0);
  });

  it('never offers Needs Triage as a public stage row', () => {
    expect(byStage([co('a', { stage: 'new' })]).some((r) => r.stage === 'new')).toBe(false);
  });

  it('carries a human label for every row', () => {
    expect(byStage([]).every((r) => typeof r.label === 'string' && r.label.length > 0)).toBe(true);
  });
});

describe('coverageRatios', () => {
  const companies = [
    co('a', { stage: 'pipeline', tags: ['qualified'] }),  // pipeline AND qualified
    co('b', { stage: 'pipeline' }),                       // pipeline only
    co('c', { stage: 'qualified' }),                      // qualified only
    co('d', { stage: 'watchlist' }),                      // neither
  ];

  it('active share is the UNION over the whole universe, never a sum', () => {
    // Summing pipeline (2) + qualified (2) would report 4 of 4 -- double
    // counting company 'a', which is exactly the deal the first ratio is about.
    const { activeShare } = coverageRatios(companies);
    expect(activeShare).toEqual({ numerator: 3, denominator: 4, pct: 75 });
  });

  it('surfaces both directions of the gap between the two buckets', () => {
    const r = coverageRatios(companies);
    expect(r.qualifiedNotInPipeline).toBe(1);
    expect(r.pipelineNotQualified).toBe(1);
    expect(r.bothCount).toBe(1);
  });

  it('counts untriaged deals, which no public stage bar can show', () => {
    const r = coverageRatios([...companies, co('e', { stage: 'new' })]);
    expect(r.needsTriageCount).toBe(1);
  });

  it('handles an empty universe', () => {
    const r = coverageRatios([]);
    expect(r.activeShare.pct).toBeNull();
    expect(r.pipelineCount).toBe(0);
  });
});

describe('coverageRatios: mandate access', () => {
  // Access lives on Attio's own Access field, not on the pipeline-AND-qualified
  // intersection -- that intersection is 0 of 336 on real data because nothing
  // writes the 'qualified' tag, so a ratio built on it would report a storage
  // artifact. See the function's own comment.
  const companies = [
    co('a', { stage: 'pipeline', access: 'access' }),
    co('b', { stage: 'pipeline', access: 'no_access' }),
    co('c', { stage: 'qualified', access: 'access' }),
    co('d', { stage: 'qualified', access: 'no_access' }),
    co('e', { stage: 'qualified', access: 'no_access' }),
    co('f', { stage: 'qualified' }),               // in the mandate, not assessed
    co('g', { stage: 'watchlist', access: 'access' }), // outside the mandate entirely
  ];

  it('rates access over ASSESSED mandate deals, never over the whole population', () => {
    const { mandateAccess } = coverageRatios(companies);
    expect(mandateAccess.population).toBe(6);  // 'g' is not in the mandate
    expect(mandateAccess.recorded).toBe(5);    // 'f' is unassessed
    expect(mandateAccess.access).toBe(2);
    expect(mandateAccess.pct).toBe(40);        // 2/5, NOT 2/6
  });

  it('keeps unassessed deals visible instead of scoring them as a no', () => {
    // Treating unset as no_access would report 33% here (2/6) and quietly
    // invent a negative answer for every deal nobody has looked at.
    expect(coverageRatios(companies).mandateAccess.unrecorded).toBe(1);
  });

  it('splits the rate by stage, because the two run very differently', () => {
    const { accessByStage } = coverageRatios(companies);
    const byKey = Object.fromEntries(accessByStage.map((s) => [s.stage, s]));
    expect(byKey.pipeline.pct).toBe(50);                     // 1 access of 2 assessed
    expect(byKey.qualified.pct).toBeCloseTo(33.33, 1);       // 1 access of 3 assessed ('f' unassessed)
    expect(byKey.qualified.recorded).toBe(3);
  });

  it('reports a null percentage rather than dividing by zero', () => {
    const r = coverageRatios([co('a', { stage: 'pipeline' })]);
    expect(r.mandateAccess.pct).toBeNull();
    expect(r.mandateAccess.recorded).toBe(0);
    expect(r.mandateAccess.population).toBe(1);
  });

  it('ignores an unrecognized access value rather than counting it either way', () => {
    const r = coverageRatios([co('a', { stage: 'pipeline', access: 'maybe' })]);
    expect(r.mandateAccess.recorded).toBe(0);
    expect(r.mandateAccess.access).toBe(0);
  });
});

describe('computeDealStats', () => {
  it('reports one honest total alongside the deliberately-overlapping stage counts', () => {
    const companies = [
      co('a', { stage: 'pipeline', tags: ['qualified'] }),
      co('b', { stage: 'watchlist' }),
    ];
    const stats = computeDealStats(companies);
    expect(stats.total).toBe(2);
    // Stage counts sum to 3 for 2 companies -- correct, and why `total` is
    // computed separately rather than by summing them.
    expect(stats.byStage.reduce((s, r) => s + r.count, 0)).toBe(3);
  });
});

describe('bySeries: folding the long tail', () => {
  // Real 2026-08-13 data runs to 22 buckets, 12 of them holding one or two
  // deals -- SAFEs, secondaries, PitchBook's "Later Stage VC" placeholder, and
  // an investor name ("NEA") that landed in the Series field. All of that buries
  // the six rounds carrying 90% of the book.
  const messy = [
    ...Array.from({ length: 5 }, (_, i) => co(`b${i}`, { round: 'Series B' })),
    co('x1', { round: 'Series B SAFE' }),
    co('x2', { round: 'Later Stage VC' }),
    co('x3', { round: 'NEA' }),
    co('u1', { round: null }),
  ];

  it('folds every non-canonical round into one row', () => {
    const rows = bySeries(messy);
    expect(rows.map((r) => r.label)).toEqual(['Series B', SERIES_OTHER, SERIES_UNKNOWN]);
    expect(rows.find((r) => r.label === SERIES_OTHER).count).toBe(3);
  });

  it('folds without dropping -- the rows still sum to the total', () => {
    expect(bySeries(messy).reduce((s, r) => s + r.count, 0)).toBe(messy.length);
  });

  it('names the folded members, biggest first, so a bad import is findable', () => {
    const other = bySeries(messy).find((r) => r.label === SERIES_OTHER);
    expect(other.members).toEqual(['Later Stage VC (1)', 'NEA (1)', 'Series B SAFE (1)']);
  });

  it('leaves a lone stray round as its own row rather than renaming it', () => {
    const rows = bySeries([co('a', { round: 'Series B' }), co('b', { round: 'Growth II' })]);
    expect(rows.map((r) => r.label)).toEqual(['Series B', 'Growth II']);
  });

  it('orders Other rounds after the ladder and Not recorded last', () => {
    const rows = bySeries(messy);
    expect(rows.at(-1).label).toBe(SERIES_UNKNOWN);
    expect(rows.at(-2).label).toBe(SERIES_OTHER);
  });

  it('can be asked for the raw unfolded breakdown', () => {
    expect(bySeries(messy, { fold: false }).length).toBe(5);
  });
});
