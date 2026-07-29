import { auth } from '@/auth';
import RadarBoard from '@/components/RadarBoard';
import { radarCompanyToRow } from '@/components/radarTableColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { getRadarConfig } from '@/lib/radarConfig';
import { getRadarKeywords } from '@/lib/radarRules';
import { buildInvestorIndex, investorDomainIndex } from '@/lib/companyIndex';

export const metadata = {
  title: 'Radar',
  description: 'Series B-or-earlier deals watched until their next round.',
};

export const dynamic = 'force-dynamic';

// A real stage, same shape as Watchlist/Pipeline/Qualified/New. Populated
// two ways: Attio sets it directly on Series B-or-earlier deals (see
// pipeline/app.py's determine_stage), forwarded onto stage='radar' by
// deal_intelligence/config.py's ATTIO_STAGE_MAP. An internal user can also
// move any company here by hand via its own StageSelect dropdown.
export default async function RadarPage() {
  const [companies, tier1, partners, session, radarConfig, keywords] = await Promise.all([
    listCompanies(), listTopVCs(), listPartnerVCs(), auth(), getRadarConfig(), getRadarKeywords(),
  ]);
  const canEdit = session?.user?.role === 'internal';
  // Additive: a company shows up here either because its primary stage IS
  // Radar (the old, still-supported behavior) OR because it's carrying the
  // `radar` tag independently -- auto-added by deal_intelligence/
  // radar_state.py whenever a company passes the mandate screen, regardless
  // of whatever stage it actually lives in. See lib/stages.js's TAGS comment.
  // Nothing is hidden from here anymore (2026-07-29) -- the old
  // keyword-exclusion admin panel silently dropped rows that matched a saved
  // term; that's gone, keywords are click-to-filter chips now (RadarBoard).
  //
  // The one exception: `radar.droppedAt` (2026-07-29) -- radar_state.py's
  // auto-drop, stamped once a company's heat has sat below the watch floor
  // for a few consecutive scans. Reversible and never deletes anything (see
  // that module's own docstring); a company whose real `stage` is literally
  // 'radar' can't have that stage cleared by radar_state.py's tag op, so
  // this filter is what actually hides it here. Still fully findable/
  // restorable from its own company page.
  const radarCompanies = companies.filter(
    (c) => (c.stage === 'radar' || c.tags?.includes('radar')) && !c.radar?.droppedAt
  );
  const investorIndex = buildInvestorIndex(tier1, partners);
  const domainIndex = investorDomainIndex(tier1, partners);

  const rows = radarCompanies.map((c) =>
    radarCompanyToRow(c, { canEdit, investorIndex, domainIndex, radarConfig, keywords })
  );
  const hotRows = rows.filter((r) => r.meta.hot);
  const coldRows = rows.filter((r) => !r.meta.hot);

  return (
    <>
      <h1>Radar</h1>
      <RadarBoard hotRows={hotRows} coldRows={coldRows} keywords={keywords} radarConfig={radarConfig} canEdit={canEdit} />
    </>
  );
}
