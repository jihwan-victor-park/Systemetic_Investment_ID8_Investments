import 'server-only';
import { listCompanies } from './companies';
import { listTopVCs } from './topVCs';
import { listPartnerVCs } from './partnerVCs';
import { buildInvestorIndex, investorDomainIndex, allInvestorMatches } from './companyIndex';
import { STAGE_BASEPATH, STAGES, STAGE_LABELS } from './stages';

// Deliberately NOT an LLM call -- same house rule as Deal Intelligence Stage
// 1 (Perplexity-only, no incidental Claude/Anthropic calls): this is a
// structured filter over data the Hub already has, not a natural-language
// query parser. "Search the Hub" in the UI is a facet panel (VC / round /
// Radar Category / stage / minimum fit score), not a chat prompt -- honest
// about what it actually does rather than pretending at NLU the underlying
// data doesn't support yet (there's no "probability to raise" signal to
// query against until that metric exists).
export async function searchHub({ vc, round, radarCategory, stage, minFitScore } = {}) {
  const [companies, tier1, partners] = await Promise.all([listCompanies(), listTopVCs(), listPartnerVCs()]);

  const vcQuery = (vc || '').trim().toLowerCase();
  const roundQuery = (round || '').trim().toLowerCase();
  const categoryQuery = (radarCategory || '').trim().toLowerCase();
  const stageFilter = STAGES.includes(stage) ? stage : null;
  const minScore = minFitScore != null && minFitScore !== '' ? Number(minFitScore) : null;
  const investorIndex = buildInvestorIndex(tier1, partners);
  const domainIndex = investorDomainIndex(tier1, partners);

  return companies
    .map((c) => ({ c, matches: allInvestorMatches(investorIndex, c.name, domainIndex, c.investorDomains) }))
    .filter(({ c, matches }) => {
      if (stageFilter && c.stage !== stageFilter && !c.tags?.includes(stageFilter)) return false;
      if (roundQuery && !(c.round || '').toLowerCase().includes(roundQuery)) return false;
      if (categoryQuery && !(c.radarCategory || '').toLowerCase().includes(categoryQuery)) return false;
      if (minScore != null && (c.latestScreen?.fitScore ?? -Infinity) < minScore) return false;
      if (vcQuery && !matches.some((m) => m.via.toLowerCase().includes(vcQuery))) return false;
      return true;
    })
    .map(({ c, matches }) => ({
      slug: c.slug,
      name: c.name,
      stage: c.stage,
      stageLabel: STAGE_LABELS[c.stage] || c.stage,
      round: c.round || null,
      radarCategory: c.radarCategory || null,
      fitScore: c.latestScreen?.fitScore ?? null,
      via: matches.map((m) => m.via),
      href: `${STAGE_BASEPATH[c.stage] || STAGE_BASEPATH.qualified}/${c.slug}`,
    }))
    .sort((a, b) => (b.fitScore ?? -1) - (a.fitScore ?? -1));
}
