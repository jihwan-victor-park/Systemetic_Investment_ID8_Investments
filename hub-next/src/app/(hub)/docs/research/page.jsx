import Link from 'next/link';
import { H2 } from '@/components/Prose';
import { Note } from '@/components/Admonition';

export const metadata = { title: 'Research', description: 'Market maps and the knowledge base behind the systems.' };

export default async function ResearchIndexPage() {
  return (
    <>
      <h1>Research</h1>
      <p>
        Market maps and reference material. Deal-specific research lives under{' '}
        <Link href="/docs/deals">Deal Screening</Link> and <Link href="/docs/qualified-deals">Qualified Deals</Link> now.
      </p>

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
