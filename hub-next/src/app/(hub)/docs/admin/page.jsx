import { H2 } from '@/components/Prose';
import IdeaBoard from '@/components/IdeaBoard';
import AccessRequests from '@/components/AccessRequests';
import TopVCsAdmin from '@/components/TopVCsAdmin';
import PartnerVCsAdmin from '@/components/PartnerVCsAdmin';
import AttioImportButton from '@/components/AttioImportButton';
import SortableTable from '@/components/SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from '@/components/companyStageColumns';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { buildInvestorIndex, partnerDomainIndex } from '@/lib/companyIndex';
import { TAG_OPTIONS } from '@/lib/stages';
import { auth } from '@/auth';

export const metadata = { title: 'Admin', description: 'Capture ideas and suggestions, plus working notes.' };

export const dynamic = 'force-dynamic';

export default async function AdminPage() {
  const [session, companies, tier1, partners] = await Promise.all([auth(), listCompanies(), listTopVCs(), listPartnerVCs()]);
  const canEdit = session?.user?.role === 'internal';
  const investorIndex = buildInvestorIndex(tier1, partners);
  const domainIndex = partnerDomainIndex(partners);
  const needsTriageRows = companies
    .filter((c) => c.stage === 'new')
    .map((c) => companyToRow(c, { basePath: '/docs/new-deals', canEdit, investorIndex, domainIndex }));
  return (
    <>
      <h1>Admin</h1>
      <p>Capture ideas, suggestions, and requests as they come up. Working notes that do not belong on a project page also live here.</p>

      <H2>Attio import</H2>
      <p>Pull every deal from Attio into the hub tab that matches its Attio stage (Watchlist, Pipeline, Qualified, Radar, or Invested) — anything else lands in Needs Triage below. Never overwrites an existing company's stage — only refreshes its round/HQ/lead-investor context.</p>
      <AttioImportButton />

      <H2>Needs Triage</H2>
      <p>Deals Attio didn't give a stage for, so they never got auto-sorted into Watchlist/Pipeline/Qualified/Radar/Invested. Assign each one a real stage below — that's also the only way a company ends up back here, so once it's assigned it drops off this list for good.</p>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={needsTriageRows}
        defaultSort={{ key: 'dealDate', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing needs triage right now."
        tagFilterOptions={TAG_OPTIONS}
      />

      <H2>Investor access requests</H2>
      <p>Anyone who signs in from outside id8investments.com lands here for approval before they can reach the investor research view.</p>
      <AccessRequests />

      <H2>Tier 1 VCs</H2>
      <p>Manually curated tier/sector list — shows on the <a href="/docs/vcs">VCs</a> tab. Fund characteristics, portfolio/deals, and news are added from each firm's own detail page after it's created here. Internal only, not shown to investors.</p>
      <TopVCsAdmin />

      <H2>Partner VCs</H2>
      <p>A partner's own personal contact into a VC firm — separate from the curated Tier 1 list above, also shown on the <a href="/docs/vcs">VCs</a> tab. Not Attio-synced yet; everything here is typed in by hand.</p>
      <PartnerVCsAdmin defaultTrackedBy={session?.user?.name || ''} />

      <H2>Capture</H2>
      <IdeaBoard />

      <H2>Deprecated workflows</H2>
      <table>
        <thead><tr><th>Workflow</th><th>Replaced by</th><th>Note</th></tr></thead>
        <tbody>
          <tr><td>"New Deals" public tab</td><td>Needs Triage (above)</td><td>Same table, same per-row stage assignment — just moved off the public Deals nav since most of what landed there already had a real Attio stage and was only there from a stage-mapping bug.</td></tr>
        </tbody>
      </table>

      <H2>Data sources and access</H2>
      <table>
        <thead><tr><th>Source</th><th>Used by</th><th>Access</th></tr></thead>
        <tbody>
          <tr><td>PitchBook</td><td>Pipeline, Deal Intelligence</td><td>MCP</td></tr>
          <tr><td>Apollo</td><td>Apollo Reach Out</td><td>Master API key</td></tr>
          <tr><td>Attio</td><td>Pipeline, Apollo</td><td>API key</td></tr>
          <tr><td>Perplexity</td><td>Apollo enrichment, Deal Intelligence</td><td>API key</td></tr>
          <tr><td>Anthropic</td><td>Deal Intelligence</td><td>API key</td></tr>
        </tbody>
      </table>
    </>
  );
}
