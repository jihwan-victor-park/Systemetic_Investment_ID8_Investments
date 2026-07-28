import 'server-only';
import { unstable_cache, revalidateTag } from 'next/cache';
import { db, isoDate } from './firestore';

// Same force-dynamic/no-route-cache reasoning as companies.js's own
// CACHE_SECONDS comment -- every /docs/* page load was re-running this full
// collection read from scratch.
const CACHE_SECONDS = 60;

// `docType` splits this one collection into the Hub's two "Docs" sub-tabs
// (Deal Screening / Investment Memo) -- 'deal-summary' | 'investment-memo'.
// Missing/anything else defaults to 'deal-summary', matching how every entry
// behaved before this field existed, so nothing already in the collection
// needs re-tagging to keep showing up where it always has. Whatever
// generates a real investment memo going forward needs to set
// docType: 'investment-memo' on write for it to bucket correctly.
export const listDealResearchDecks = unstable_cache(async () => {
  const snap = await db().collection('dealResearchDecks').orderBy('companyName').get();
  return snap.docs.map((doc) => {
    const d = doc.data();
    return {
      id: doc.id,
      companyName: d.companyName,
      thesis: d.thesis,
      stage: d.stage,
      deckPath: d.deckPath,
      docType: d.docType === 'investment-memo' ? 'investment-memo' : 'deal-summary',
      createdAt: isoDate(d.createdAt),
    };
  });
}, ['list-deal-research-decks'], { tags: ['deal-research-decks'], revalidate: CACHE_SECONDS });

export async function deleteDealResearchDeck(id) {
  await db().collection('dealResearchDecks').doc(id).delete();
  revalidateTag('deal-research-decks');
}

export const getDealResearchDeck = unstable_cache(async (id) => {
  const doc = await db().collection('dealResearchDecks').doc(id).get();
  if (!doc.exists) return null;
  const d = doc.data();
  return {
    id: doc.id,
    companyName: d.companyName,
    thesis: d.thesis,
    stage: d.stage,
    deckPath: d.deckPath,
    docType: d.docType === 'investment-memo' ? 'investment-memo' : 'deal-summary',
    createdAt: isoDate(d.createdAt),
  };
}, ['get-deal-research-deck'], { tags: ['deal-research-decks'], revalidate: CACHE_SECONDS });
