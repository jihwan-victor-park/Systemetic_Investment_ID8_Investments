import Link from 'next/link';
import { listDealResearchDecks } from '@/lib/dealResearchDecks';

export const metadata = { title: 'Deal Summaries', description: 'Companies ID8 has done real research work on.' };

export const dynamic = 'force-dynamic';

export default async function DealsPage() {
  const decks = await listDealResearchDecks();

  return (
    <>
      <h1>Deal Summaries</h1>
      <p>Companies ID8 has done real diligence work on — this populates as investment memos and deal summaries are created.</p>
      <table>
        <thead><tr><th>Company</th><th>Thesis</th><th>Stage</th></tr></thead>
        <tbody>
          {decks.map((d) => (
            <tr key={d.id}>
              <td><Link href={`/docs/deals/${d.id}`}>{d.companyName}</Link></td>
              <td>{d.thesis}</td>
              <td>{d.stage}</td>
            </tr>
          ))}
          {decks.length === 0 && (
            <tr><td colSpan={3}><em>No deal summaries yet.</em></td></tr>
          )}
        </tbody>
      </table>
    </>
  );
}
