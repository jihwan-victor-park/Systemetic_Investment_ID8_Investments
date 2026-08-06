import { describe, expect, it } from 'vitest';
import { computeDealStats } from './dealStats';

function company(overrides = {}) {
  return {
    slug: 'acme', name: 'Acme', stage: 'pipeline', tags: [], roundSize: null,
    roundDate: null, radarCategory: null, latestScreen: null, top10Investors: [],
    tier1_33Investors: [], access: null, companyKey: null,
    ...overrides,
  };
}

describe('computeDealStats', () => {
  it('counts total and by-stage without double counting', () => {
    const stats = computeDealStats([
      company({ slug: 'a', stage: 'pipeline' }),
      company({ slug: 'b', stage: 'qualified' }),
      company({ slug: 'c', stage: 'qualified' }),
    ]);
    expect(stats.total).toBe(3);
    expect(stats.byStage.pipeline).toBe(1);
    expect(stats.byStage.qualified).toBe(2);
  });

  it('counts additive tags separately from stage, allowing double-counting', () => {
    // The real case this whole feature was built around: a company can be
    // BOTH stage='pipeline' AND tagged 'passed' at once.
    const stats = computeDealStats([
      company({ slug: 'a', stage: 'pipeline', tags: ['pipeline', 'passed'] }),
      company({ slug: 'b', stage: 'qualified', tags: ['qualified'] }),
    ]);
    expect(stats.byStage.pipeline).toBe(1);
    expect(stats.byTag.passed).toBe(1);
    expect(stats.total).toBe(2); // not inflated by the tag
  });

  it('cross-tabs access against each pipeline stage', () => {
    const stats = computeDealStats([
      company({ slug: 'a', stage: 'qualified', access: 'access' }),
      company({ slug: 'b', stage: 'qualified', access: 'no_access' }),
      company({ slug: 'c', stage: 'qualified', access: null }),
    ]);
    expect(stats.accessByStage.qualified).toEqual({ total: 3, access: 1, noAccess: 1 });
  });

  it('ranks top sectors among qualified deals only, ignoring null categories', () => {
    const stats = computeDealStats([
      company({ slug: 'a', stage: 'qualified', radarCategory: 'Fintech' }),
      company({ slug: 'b', stage: 'qualified', radarCategory: 'Fintech' }),
      company({ slug: 'c', stage: 'qualified', radarCategory: 'Healthcare' }),
      company({ slug: 'd', stage: 'qualified', radarCategory: null }),
      company({ slug: 'e', stage: 'pipeline', radarCategory: 'Fintech' }), // wrong stage, excluded
    ]);
    expect(stats.topSectors).toEqual([
      { category: 'Fintech', count: 2 },
      { category: 'Healthcare', count: 1 },
    ]);
  });

  it('computes average and median raise size in millions, excluding deals with no roundSize', () => {
    const stats = computeDealStats([
      company({ slug: 'a', stage: 'qualified', roundSize: 20_000_000 }),
      company({ slug: 'b', stage: 'qualified', roundSize: 40_000_000 }),
      company({ slug: 'c', stage: 'qualified', roundSize: null }),
    ]);
    expect(stats.raiseSizeStats).toEqual({ count: 2, avgMillions: 30, medianMillions: 30 });
  });

  it('reports no raise-size data as null, not a fabricated zero', () => {
    const stats = computeDealStats([company({ stage: 'qualified', roundSize: null })]);
    expect(stats.raiseSizeStats).toEqual({ count: 0, avgMillions: null, medianMillions: null });
  });

  it('averages days between rounds only for companies with 2+ rounds on file', () => {
    const stats = computeDealStats([
      company({ slug: 'a', companyKey: 'acme', roundDate: '2025-01-01' }),
      company({ slug: 'a--series-c', companyKey: 'acme', roundDate: '2025-07-01' }), // +181 days
      company({ slug: 'b', companyKey: 'other', roundDate: '2025-01-01' }), // only one round
    ]);
    expect(stats.avgDaysBetweenRounds.companiesWithMultipleRounds).toBe(1);
    expect(stats.avgDaysBetweenRounds.avgDays).toBe(181);
  });

  it('reports no multi-round data as null, not zero', () => {
    const stats = computeDealStats([company({ slug: 'a', companyKey: 'acme', roundDate: '2025-01-01' })]);
    expect(stats.avgDaysBetweenRounds).toEqual({ companiesWithMultipleRounds: 0, avgDays: null });
  });

  it('computes median fit score among qualified deals with a real score', () => {
    const stats = computeDealStats([
      company({ slug: 'a', stage: 'qualified', latestScreen: { fitScore: 2 } }),
      company({ slug: 'b', stage: 'qualified', latestScreen: { fitScore: 3 } }),
      company({ slug: 'c', stage: 'qualified', latestScreen: { fitScore: 4 } }),
      company({ slug: 'd', stage: 'qualified', latestScreen: null }),
    ]);
    expect(stats.medianFitScore).toBe(3);
  });

  it('counts Top 10 / Tier 1 (33) backing rate among qualified deals', () => {
    const stats = computeDealStats([
      company({ slug: 'a', stage: 'qualified', top10Investors: ['Sequoia Capital'], tier1_33Investors: ['Sequoia Capital'] }),
      company({ slug: 'b', stage: 'qualified', top10Investors: [], tier1_33Investors: ['8VC'] }),
      company({ slug: 'c', stage: 'qualified', top10Investors: [], tier1_33Investors: [] }),
    ]);
    expect(stats.tier1BackedRate).toEqual({ total: 3, top10: 1, tier1_33: 2 });
  });
});
