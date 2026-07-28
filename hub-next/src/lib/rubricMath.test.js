import { describe, expect, it } from 'vitest';
import { dimensionScore, fitScore } from './rubricMath';

describe('dimensionScore', () => {
  it('averages subcategory scores to 1 decimal', () => {
    expect(dimensionScore([{ score: 1 }, { score: 2 }, { score: 4 }])).toBe(2.3);
  });

  it('ignores subcategories with a null/empty score rather than treating them as 0', () => {
    // mirrors deal_intelligence/rubric.py's dimension_score(): a subcategory
    // the model dropped is absent from the mean, not a silent zero that
    // would unfairly tank the dimension.
    expect(dimensionScore([{ score: 4 }, { score: null }, { score: '' }])).toBe(4);
  });

  it('returns 0 for no subcategories at all', () => {
    expect(dimensionScore([])).toBe(0);
    expect(dimensionScore(undefined)).toBe(0);
  });

  it('floors at 1 when every subcategory is 1 -- the hard-gate trigger stage1_fit.py checks for', () => {
    expect(dimensionScore([{ score: 1 }, { score: 1 }])).toBe(1);
  });
});

describe('fitScore', () => {
  it('averages dimension scores to 1 decimal, matching rubric.py weighted_score at equal weights', () => {
    const dims = [1, 2, 3, 4, 2, 3].map((score) => ({ score }));
    expect(fitScore(dims)).toBe(2.5);
  });

  it('returns 0 for no dimensions at all', () => {
    expect(fitScore([])).toBe(0);
  });
});
