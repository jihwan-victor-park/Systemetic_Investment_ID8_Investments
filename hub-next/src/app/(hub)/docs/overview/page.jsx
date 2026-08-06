import { H2 } from '@/components/Prose';
import StatusPill from '@/components/StatusPill';
import DealStatsDashboard from '@/components/DealStatsDashboard';
import { listCompanies } from '@/lib/companies';

export const metadata = { title: 'Dashboard', description: 'ID8’s deal pipeline, at a glance.' };

export const dynamic = 'force-dynamic';

const SYSTEMS = [
  { name: 'PitchBook → Attio Pipeline', what: 'Pulls deal, company, and investor data into Attio and keeps the investor graph accurate.', status: 'Live' },
  { name: 'Apollo Reach Out', what: 'Builds clean family office and RIA lists, scores them, and loads outbound sequences.', status: 'Live' },
  { name: 'Deal Intelligence', what: 'AI agents score every qualified deal against our rubric and deep-research the best ones.', status: 'Live' },
  { name: 'Investment Memo Generator', what: '16-agent workflow that writes a complete formatted investment memo from raw deal data.', status: 'Live' },
  { name: 'Documentation System', what: 'Latent Order design system for building and publishing ID8 operating guides.', status: 'Live' },
];

// The landing page (Oscar, 2026-08-06: "the landing page to be the summary
// statistics of the hub") -- this is what the Navbar's "Dashboard" link and
// the sidebar's top entry both point at. The stats dashboard leads; the
// existing "AI Capabilities" writeup (what this page used to be, in full)
// stays below it rather than getting deleted -- still real, still useful,
// just no longer the first thing you see on sign-in.
export default async function OverviewPage() {
  const companies = await listCompanies();

  return (
    <>
      <h1>Dashboard</h1>
      <DealStatsDashboard companies={companies} />

      <H2>AI Capabilities</H2>
      <p>
        ID8 runs a set of AI and automation systems that turn raw market data into fund workflows. This hub is
        where each one is documented: what it does, how to use it, how it works, and where the code lives. As we
        add systems, they live here too.
      </p>

      <H2>The idea</H2>
      <p>
        A growth-stage co-invest fund wins on three things: a clean pipeline, sharp outbound, and knowing what the
        lead VCs in its network are doing before everyone else. Each system below covers one of those.
      </p>

      <H2>The systems</H2>
      <table>
        <thead>
          <tr><th>System</th><th>What it does</th><th>Status</th></tr>
        </thead>
        <tbody>
          {SYSTEMS.map((s) => (
            <tr key={s.name}>
              <td>{s.name}</td>
              <td>{s.what}</td>
              <td><StatusPill status={s.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <H2>Why it holds together</H2>
      <p>
        The pipeline is the CRM layer. Apollo is the outbound layer. Intelligence is the proprietary layer that
        compounds the data the other two collect. The memo generator is the output layer — it turns that research
        into an institutional-grade deliverable. The documentation system is how every one of these gets
        documented: cover, DOCX, and hub page. Each one is a system with its own page, not a one-off script.
      </p>
    </>
  );
}
