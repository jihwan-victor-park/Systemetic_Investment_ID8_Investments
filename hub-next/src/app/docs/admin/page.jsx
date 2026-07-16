import { H2 } from '@/components/Prose';
import IdeaBoard from '@/components/IdeaBoard';
import AccessRequests from '@/components/AccessRequests';
import TopVCsAdmin from '@/components/TopVCsAdmin';
import AttioImportButton from '@/components/AttioImportButton';

export const metadata = { title: 'Admin', description: 'Capture ideas and suggestions, plus working notes.' };

export default function AdminPage() {
  return (
    <>
      <h1>Admin</h1>
      <p>Capture ideas, suggestions, and requests as they come up. Working notes that do not belong on a project page also live here.</p>

      <H2>Attio import</H2>
      <p>Pull every deal from Attio, regardless of stage, into the <a href="/docs/new-deals">New Deals</a> tab for manual triage. Never overwrites an existing company's stage — only refreshes its round/HQ/lead-investor context.</p>
      <AttioImportButton />

      <H2>Investor access requests</H2>
      <p>Anyone who signs in from outside id8investments.com lands here for approval before they can reach the investor research view.</p>
      <AccessRequests />

      <H2>Top 10 VCs</H2>
      <p>Manually curated tier/sector list — shows on the <a href="/docs/top-vcs">Top 10 VCs</a> tab. Internal only, not shown to investors.</p>
      <TopVCsAdmin />

      <H2>Capture</H2>
      <IdeaBoard />

      <H2>Deprecated workflows</H2>
      <table>
        <thead><tr><th>Workflow</th><th>Replaced by</th><th>Note</th></tr></thead>
        <tbody>
          <tr><td><em>none yet</em></td><td></td><td></td></tr>
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
