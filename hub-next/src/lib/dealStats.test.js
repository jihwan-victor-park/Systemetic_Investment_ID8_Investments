import { describe, it, expect } from 'vitest';
import {
  bySeries, byStage, computeDealStats, inStage, mandateStats, normalizeSeries,
  SERIES_OTHER, SERIES_UNKNOWN,
} from './dealStats';

const co = (slug, { stage = 'watchlist', tags = [], round = null } = {}) => ({ slug, stage, tags, round });

describe('inStage', () => {
  it('matches the primary stage', () => {
    expect(inStage(co('a', { stage: 'pipeline' }), 'pipeline')).toBe(true);
  });

  it('matches an additive tag on a company whose primary stage is something else', () => {
    // How a Passed deal records the pipeline access it actually had -- see
    // isSourced below, which depends entirely on this.
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

describe('mandateStats', () => {
  // Oscar's own definition, 2026-08-13: "qualified have our mandate, pipeline
  // are the ones we get access to." So the rate is pipeline / qualified.
  const companies = [
    co('a', { stage: 'qualified' }),
    co('b', { stage: 'qualified' }),
    co('c', { stage: 'qualified' }),
    co('d', { stage: 'qualified' }),
    co('e', { stage: 'pipeline' }),
    co('f', { stage: 'pipeline' }),
    co('g', { stage: 'watchlist' }),
    co('h', { stage: 'new' }),
  ];

  it('rates pipeline against the whole mandate', () => {
    const m = mandateStats(companies);
    expect(m.qualifiedCount).toBe(4);
    expect(m.pipelineCount).toBe(2);
    expect(m.mandateTotal).toBe(6);   // qualified UNION pipeline
    expect(m.pct).toBeCloseTo(33.33, 1);   // 2/6
  });

  it('cannot exceed 100% when more deals have advanced than remain qualified', () => {
    // The bug this denominator exists to prevent: qualified and pipeline are
    // disjoint (stage is one funnel position), so pipeline / qualified read
    // 533% for Series A on real 2026-08-13 data. A percentage that can exceed
    // 100% is not a percentage.
    const lopsided = [
      co('a', { stage: 'qualified' }),
      ...Array.from({ length: 9 }, (_, i) => co(`p${i}`, { stage: 'pipeline' })),
    ];
    const m = mandateStats(lopsided);
    expect(m.pct).toBe(90);   // 9/10, not 900%
    expect(m.pct).toBeLessThanOrEqual(100);
  });

  it('counts a stage carried as an additive tag', () => {
    // A deal filed elsewhere in Attio but tagged into pipeline still counts as
    // access -- that is how the CSV import records a passed deal we got into.
    const m = mandateStats([co('a', { stage: 'qualified' }), co('b', { stage: 'passed', tags: ['pipeline'] })]);
    expect(m.pipelineCount).toBe(1);
    expect(m.qualifiedCount).toBe(1);
    expect(m.mandateTotal).toBe(2);
    expect(m.pct).toBe(50);
  });

  it('reports a null rate rather than dividing by zero', () => {
    const m = mandateStats([co('a', { stage: 'watchlist' })]);
    expect(m.pct).toBeNull();
    expect(m.qualifiedCount).toBe(0);
  });

  it('counts untriaged deals, which no public stage bar can show', () => {
    expect(mandateStats(companies).needsTriageCount).toBe(1);
  });
});

describe('bySeries: mandate and access per round', () => {
  const companies = [
    co('a', { round: 'Series B', stage: 'qualified' }),
    co('b', { round: 'Series B', stage: 'qualified' }),
    co('c', { round: 'Series B', stage: 'pipeline' }),
    co('d', { round: 'Series C', stage: 'qualified' }),
    co('e', { round: 'Series C', stage: 'watchlist' }),
  ];

  it('carries qualified, pipeline and mandate counts per round', () => {
    const b = bySeries(companies).find((r) => r.label === 'Series B');
    expect(b.qualified).toBe(2);
    expect(b.pipeline).toBe(1);
    expect(b.mandate).toBe(3);   // qualified UNION pipeline
    expect(b.count).toBe(3);     // every tracked deal at that round
  });

  it('rates access within the round, against that round\'s mandate', () => {
    const rows = bySeries(companies);
    expect(rows.find((r) => r.label === 'Series B').accessPct).toBeCloseTo(33.33, 1);   // 1/3
    expect(rows.find((r) => r.label === 'Series C').accessPct).toBe(0);                 // 0/1
  });

  it('is null, not zero, for a round with nothing in the mandate to rate', () => {
    const rows = bySeries([co('a', { round: 'Seed', stage: 'watchlist' })]);
    expect(rows[0].accessPct).toBeNull();
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
