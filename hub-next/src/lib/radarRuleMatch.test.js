import { describe, expect, it } from 'vitest';
import { matchedKeywords, ruleRegex } from './radarRuleMatch';

describe('ruleRegex', () => {
  it('matches a keyword as a whole word, not a substring', () => {
    expect(ruleRegex('crypto').test('confidential-compute cryptography startup')).toBe(false);
    expect(ruleRegex('crypto').test('a crypto exchange')).toBe(true);
  });

  it('treats internal whitespace in a phrase as flexible', () => {
    expect(ruleRegex('wealth management').test('a wealth  management platform')).toBe(true);
    expect(ruleRegex('wealth management').test('grows generational wealth through management fees')).toBe(false);
  });

  it('is case-insensitive', () => {
    expect(ruleRegex('Biotech').test('a BIOTECH company')).toBe(true);
  });
});

describe('matchedKeywords', () => {
  const keywords = [{ term: 'wealth management' }, { term: 'biotech' }];

  it('matches on description text', () => {
    const hits = matchedKeywords({ slug: 'arcawealth', name: 'ArcaWealth', description: 'A wealth management and financial advisory platform.' }, keywords);
    expect(hits).toEqual(['wealth management']);
  });

  it('matches on radarCategory too', () => {
    const hits = matchedKeywords({ slug: 'x', name: 'X', radarCategory: 'Biotech research' }, keywords);
    expect(hits).toEqual(['biotech']);
  });

  it('returns every matching term, not just the first', () => {
    const hits = matchedKeywords({ slug: 'z', name: 'Z', description: 'biotech wealth management rollup' }, keywords);
    expect(hits).toEqual(['wealth management', 'biotech']);
  });

  it('returns an empty array for a company matching nothing -- it still renders, it just filters differently', () => {
    expect(matchedKeywords({ slug: 'y', name: 'Y', description: 'AI infrastructure for enterprise pipelines.' }, keywords)).toEqual([]);
  });

  it('accepts a plain string keyword list too (legacy shape)', () => {
    expect(matchedKeywords({ slug: 'y', name: 'Y', description: 'a biotech company' }, ['biotech'])).toEqual(['biotech']);
  });
});
