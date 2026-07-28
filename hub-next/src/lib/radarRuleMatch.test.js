import { describe, expect, it } from 'vitest';
import { matchExclusionRule, isRadarRelevant, previewKeywordMatches, ruleRegex } from './radarRuleMatch';

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

describe('matchExclusionRule', () => {
  const rules = {
    keywords: ['wealth management', 'biotech'],
    categories: ['Real Estate'],
    companies: ['bad-fit-co'],
  };

  it('matches on description keyword', () => {
    const hit = matchExclusionRule({ slug: 'arcawealth', name: 'ArcaWealth', description: 'A wealth management and financial advisory platform.' }, rules);
    expect(hit).toEqual({ type: 'keyword', term: 'wealth management' });
  });

  it('matches on exact category, case/whitespace-insensitively', () => {
    const hit = matchExclusionRule({ slug: 'x', name: 'X', radarCategory: '  real estate ' }, rules);
    expect(hit).toEqual({ type: 'category', term: 'Real Estate' });
  });

  it('matches a manually-excluded company by slug regardless of its text', () => {
    const hit = matchExclusionRule({ slug: 'bad-fit-co', name: 'Bad Fit Co', description: 'perfectly on-thesis text' }, rules);
    expect(hit).toEqual({ type: 'company', term: 'Bad Fit Co' });
  });

  it('returns null for a company matching nothing', () => {
    expect(matchExclusionRule({ slug: 'y', name: 'Y', description: 'AI infrastructure for enterprise pipelines.' }, rules)).toBeNull();
  });

  it('keepAnyway overrides every rule type, including a manual company exclusion', () => {
    const hit = matchExclusionRule(
      { slug: 'arcawealth', name: 'ArcaWealth', description: 'wealth management' },
      rules,
      ['arcawealth']
    );
    expect(hit).toBeNull();
  });

  it('isRadarRelevant is the boolean inverse', () => {
    expect(isRadarRelevant({ slug: 'y', name: 'Y', description: 'AI infra' }, rules)).toBe(true);
    expect(isRadarRelevant({ slug: 'arcawealth', name: 'A', description: 'wealth management' }, rules)).toBe(false);
  });
});

describe('previewKeywordMatches', () => {
  const companies = [
    { slug: 'a', name: 'Anysphere', description: 'AI coding assistant' },
    { slug: 'b', name: 'ArcaWealth', description: 'wealth management platform' },
    { slug: 'c', name: 'Cascade Bio', description: 'gene therapy for rare disease' },
  ];

  it('is empty below the minimum keyword length', () => {
    expect(previewKeywordMatches('ai', companies, [])).toEqual([]);
  });

  it('returns only currently-kept companies that would newly match', () => {
    const hits = previewKeywordMatches('wealth', companies, []);
    expect(hits.map((c) => c.slug)).toEqual(['b']);
  });

  it('excludes companies already caught by an existing keyword, since this previews the NEW term in isolation', () => {
    const hits = previewKeywordMatches('bio', companies, ['gene therapy']);
    expect(hits).toEqual([]);
  });
});
