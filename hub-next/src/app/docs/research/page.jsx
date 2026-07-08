import Link from 'next/link';
import { H2 } from '@/components/Prose';
import { Note } from '@/components/Admonition';
import { listCompanies } from '@/lib/companies';
import { listDealResearchDecks } from '@/lib/dealResearchDecks';

export const metadata = { title: 'Research', description: 'The knowledge base behind the systems.' };

export const dynamic = 'force-dynamic';

export default async function ResearchIndexPage() {
  const [companies, decks] = await Promise.all([listCompanies(), listDealResearchDecks()]);
  const sortedCompanies = [...companies].sort((a, b) => {
    const ad = a.latestScreen?.date || '';
    const bd = b.latestScreen?.date || '';
    return bd.localeCompare(ad);
  });

  return (
    <>
      <h1>Research</h1>
      <p>Deal research and the knowledge base behind the systems. Each entry links to the source deck.</p>

      <H2>Deal screens</H2>
      <p>
        Stage 1 fit screens produced by <Link href="/docs/projects/intelligence">Deal Intelligence</Link> — one
        page per company, scored against the ID8 rubric with a dated screen history.
      </p>
      <table>
        <thead><tr><th>Company</th><th>Latest screen</th><th>Report</th></tr></thead>
        <tbody>
          {sortedCompanies.map((c) => (
            <tr key={c.slug}>
              <td>{c.name}</td>
              <td>
                {c.latestScreen ? `${c.latestScreen.date.slice(0, 10)}${c.latestScreen.roundStage ? ` · ${c.latestScreen.roundStage}` : ''}` : '—'}
              </td>
              <td><Link href={`/docs/research/companies/${c.slug}`}>View screen →</Link></td>
            </tr>
          ))}
        </tbody>
      </table>

      <H2>Deal research</H2>
      <table>
        <thead><tr><th>Company</th><th>Thesis</th><th>Stage</th><th>Deck</th></tr></thead>
        <tbody>
          {decks.map((d) => (
            <tr key={d.id}>
              <td>{d.companyName}</td>
              <td>{d.thesis}</td>
              <td>{d.stage}</td>
              <td><a href={d.deckPath}>PPTX →</a></td>
            </tr>
          ))}
        </tbody>
      </table>

      <H2>Market maps</H2>
      <p>A directory of external VC market maps and industry landscape reports, browsable by category and by firm with a freshness read on each one.</p>
      <table>
        <thead><tr><th>What</th><th>Description</th><th>Link</th></tr></thead>
        <tbody>
          <tr>
            <td>Market Map Directory</td>
            <td>Restyled into the Latent Order system — search, category/firm grouping, freshness filter.</td>
            <td><Link href="/docs/research/market-map">View →</Link></td>
          </tr>
          <tr>
            <td>Market Map Directory (original)</td>
            <td>The source directory as received, unstyled, kept for comparison.</td>
            <td><a href="/research/market-map-original.html">View →</a></td>
          </tr>
        </tbody>
      </table>

      <H2>How to add a document</H2>
      <ol>
        <li>Put the file in <code>hub-next/public/research/</code>.</li>
        <li>Add a row via the Market Map &quot;+ Add new&quot; tab, or a deal-research row directly in Firestore.</li>
        <li>It publishes immediately — no rebuild needed.</li>
      </ol>

      <Note>Keep the newest entries easy to find. For long write-ups, a deck or a PDF reads better than a Word file.</Note>
    </>
  );
}
