import Link from 'next/link';
import { listCompanies } from '@/lib/companies';

export const metadata = { title: 'Qualified Deals', description: 'Every deal Deal Intelligence has screened, updated automatically each run.' };

export const dynamic = 'force-dynamic';

// Shorter labels than the company docs' own frontmatter titles (which carry a
// PitchBook category suffix, e.g. "Pocket (Business/Productivity Software)") —
// the company page's own H1 shows the full title; only this table doesn't.
const COMPANY_SHORT_NAME = {
  heypocket: 'Pocket',
  warp: 'Warp',
  getpie: 'PieTech',
};

export default async function QualifiedDealsPage() {
  const companies = await listCompanies();
  const sorted = [...companies].sort((a, b) => {
    const ad = a.latestScreen?.date || '';
    const bd = b.latestScreen?.date || '';
    return bd.localeCompare(ad);
  });

  return (
    <>
      <h1>Qualified Deals</h1>
      <p>
        Every deal that reaches the Qualified stage gets scored by{' '}
        <Link href="/docs/projects/intelligence">Deal Intelligence</Link>'s weekly Stage 1 screen against the ID8
        rubric — this list populates automatically as those runs complete, no manual step required.
      </p>
      <table>
        <thead><tr><th>Company</th><th>Latest screen</th><th>Report</th></tr></thead>
        <tbody>
          {sorted.map((c) => (
            <tr key={c.slug}>
              <td>{COMPANY_SHORT_NAME[c.slug] || c.name}</td>
              <td>
                {c.latestScreen ? `${c.latestScreen.date.slice(0, 10)}${c.latestScreen.roundStage ? ` · ${c.latestScreen.roundStage}` : ''}` : '—'}
              </td>
              <td><Link href={`/docs/qualified-deals/${c.slug}`}>View screen →</Link></td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr><td colSpan={3}><em>No screened deals yet.</em></td></tr>
          )}
        </tbody>
      </table>
    </>
  );
}
