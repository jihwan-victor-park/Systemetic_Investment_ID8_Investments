import { notFound } from 'next/navigation';
import { getDealResearchDeck } from '@/lib/dealResearchDecks';

export const dynamic = 'force-dynamic';

export async function generateMetadata({ params }) {
  const { id } = await params;
  const deck = await getDealResearchDeck(id);
  if (!deck) return {};
  return { title: deck.companyName, description: deck.thesis };
}

export default async function InvestmentMemoPage({ params }) {
  const { id } = await params;
  const deck = await getDealResearchDeck(id);
  if (!deck || deck.docType !== 'investment-memo') notFound();

  return (
    <>
      <h1>{deck.companyName}</h1>
      <p><strong>Stage:</strong> {deck.stage || '—'}</p>
      <p><strong>Thesis</strong><br />{deck.thesis}</p>
      {deck.deckPath && <p><a href={deck.deckPath}>Download full investment memo →</a></p>}
    </>
  );
}
