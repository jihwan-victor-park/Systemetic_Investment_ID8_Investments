import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import RadarRulesAdmin from '@/components/RadarRulesAdmin';
import { RADAR_TABLE_COLUMNS, radarCompanyToRow } from '@/components/radarTableColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { getRadarRules } from '@/lib/radarRules';
import { matchExclusionRule } from '@/lib/radarRuleMatch';
import { buildInvestorIndex, partnerDomainIndex } from '@/lib/companyIndex';
import { TAG_OPTIONS } from '@/lib/stages';

export const metadata = {
  title: 'Radar',
  description: 'Series B-or-earlier deals sourced from the Top 10 VC and Qualified Deals workflows, watched until their next round.',
};

export const dynamic = 'force-dynamic';

// A real stage, same shape as Watchlist/Pipeline/Qualified/New. Populated
// two ways: Attio sets it directly on Series B-or-earlier deals (see
// pipeline/app.py's determine_stage -- widened from Series A to Series B
// 2026-07-28, RADAR_PLAN.md Part I: a company that just closed a B can't
// raise again for 18-24 months, so it's a company to watch, not a live
// opportunity), forwarded onto stage='radar' by
// deal_intelligence/config.py's ATTIO_STAGE_MAP. An internal user can also
// move any company here by hand via its own StageSelect dropdown.
export default async function RadarPage() {
  const [companies, tier1, partners, session, rules] = await Promise.all([
    listCompanies(), listTopVCs(), listPartnerVCs(), auth(), getRadarRules(),
  ]);
  const canEdit = session?.user?.role === 'internal';
  // Additive: a company shows up here either because its primary stage IS
  // Radar (the old, still-supported behavior) OR because it's carrying the
  // `radar` tag independently -- auto-added by deal_intelligence/
  // radar_state.py whenever a company passes the mandate screen, regardless
  // of whatever stage it actually lives in (e.g. a company parked in
  // Pipeline that's ALSO being watched for its next round shows up here
  // too, hot/cold from the capital clock). See lib/stages.js's TAGS comment.
  const radarCompanies = companies.filter((c) => c.stage === 'radar' || c.tags?.includes('radar'));
  const keepAnywaySlugs = (rules.keepAnyway || []).map((k) => k.slug);
  const visible = radarCompanies.filter((c) => !matchExclusionRule(c, rules, keepAnywaySlugs));
  const hiddenCount = radarCompanies.length - visible.length;
  const investorIndex = buildInvestorIndex(tier1, partners);
  const domainIndex = partnerDomainIndex(partners);
  const rows = visible.map((c) => radarCompanyToRow(c, { canEdit, investorIndex, domainIndex }));

  return (
    <>
      <h1>Radar</h1>
      <p>Series B-or-earlier deals sourced from the Top 10 VC and Qualified Deals workflows &mdash; watched until their next round, which is where ID8 actually invests.</p>
      <p>Some companies arrive through those workflows legitimately, but are obviously off-thesis once you read what they do (a wealth-management or financial-advisory platform, for example). Add a keyword or phrase below and it applies here immediately — preview shows exactly who it would drop before you save it. Nothing is ever deleted; an excluded company can always be pinned back with &ldquo;Keep anyway.&rdquo;</p>
      <RadarRulesAdmin radarCompanies={radarCompanies} />
      {hiddenCount > 0 && (
        <p>{hiddenCount} {hiddenCount === 1 ? 'company' : 'companies'} hidden by the relevance-exclusion list above (off-thesis by category or description).</p>
      )}
      <SortableTable
        columns={RADAR_TABLE_COLUMNS}
        rows={rows}
        defaultSort={{ key: 'dealDate', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing on Radar yet."
        tagFilterOptions={TAG_OPTIONS}
      />
    </>
  );
}
