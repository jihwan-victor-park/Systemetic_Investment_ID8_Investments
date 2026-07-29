import { describe, expect, it } from 'vitest';
import { radarHeatScore, radarHeatBreakdown, radarHotnessFromScore, bestFitScore } from './radarHeatScore';

const CONFIG = { hotWindowMonths: 3, hotThreshold: 5 };
const TODAY = new Date('2026-07-29T00:00:00Z');

describe('radarHeatBreakdown', () => {
  it('gives full timing points once inside the configured hot window', () => {
    const c = { radar: { clock: { predictedWindowOpen: '2026-09-01' } } }; // ~1 month out
    expect(radarHeatBreakdown(c, CONFIG, null, TODAY).timing).toBe(6);
  });

  it('gives full timing points for a window already open/past, not less', () => {
    const c = { radar: { clock: { predictedWindowOpen: '2026-01-01' } } };
    expect(radarHeatBreakdown(c, CONFIG, null, TODAY).timing).toBe(6);
  });

  it('gives partial credit while approaching, within 2x the window', () => {
    const c = { radar: { clock: { predictedWindowOpen: '2026-12-01' } } }; // ~4 months out
    expect(radarHeatBreakdown(c, CONFIG, null, TODAY).timing).toBe(3);
  });

  it('gives zero timing points far out', () => {
    const c = { radar: { clock: { predictedWindowOpen: '2028-01-01' } } };
    expect(radarHeatBreakdown(c, CONFIG, null, TODAY).timing).toBe(0);
  });

  it('gives zero timing points with no window estimate at all -- unscored, not "known cold"', () => {
    const c = {};
    expect(radarHeatBreakdown(c, CONFIG, null, TODAY).timing).toBe(0);
  });

  it('scales a 1-4 fit score to the same 0-6 range as timing', () => {
    expect(radarHeatBreakdown({}, CONFIG, 4, TODAY).fit).toBe(6);
    expect(radarHeatBreakdown({}, CONFIG, 1, TODAY).fit).toBe(1.5);
    expect(radarHeatBreakdown({}, CONFIG, null, TODAY).fit).toBe(0);
  });
});

describe('radarHeatScore / radarHotnessFromScore', () => {
  it('is hot when timing alone clears the threshold', () => {
    const c = { radar: { clock: { predictedWindowOpen: '2026-08-01' } } };
    const score = radarHeatScore(c, CONFIG, null, TODAY);
    expect(radarHotnessFromScore(score, CONFIG)).toBe('hot');
  });

  it('is hot when fit alone clears the threshold even with no timing signal', () => {
    const score = radarHeatScore({}, CONFIG, 4, TODAY);
    expect(radarHotnessFromScore(score, CONFIG)).toBe('hot');
  });

  it('is cold for a far-out, unscored company', () => {
    const score = radarHeatScore({}, CONFIG, null, TODAY);
    expect(radarHotnessFromScore(score, CONFIG)).toBe('cold');
  });

  it('respects a raised hotThreshold', () => {
    const c = { radar: { clock: { predictedWindowOpen: '2026-08-01' } } };
    const score = radarHeatScore(c, CONFIG, null, TODAY);
    expect(radarHotnessFromScore(score, { ...CONFIG, hotThreshold: 100 })).toBe('cold');
  });
});

describe('bestFitScore', () => {
  it('prefers the company\'s own Stage 1 screen over a portfolio-match fallback', () => {
    expect(bestFitScore({ latestScreen: { fitScore: 3 } }, 4)).toBe(3);
  });

  it('falls back to the best Stage 0 portfolio-match score when there\'s no Stage 1 screen', () => {
    expect(bestFitScore({}, 2.5)).toBe(2.5);
  });

  it('is null when neither is available', () => {
    expect(bestFitScore({}, null)).toBeNull();
  });
});
