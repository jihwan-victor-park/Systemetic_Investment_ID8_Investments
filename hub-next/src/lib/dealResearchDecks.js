import 'server-only';
import { db, isoDate } from './firestore';

// `docType` splits this one collection into the Hub's two "Docs" sub-tabs
// (Deal Summaries / Investment Memo) -- 'deal-summary' | 'investment-memo'.
// Missing/anything else defaults to 'deal-summary', matching how every entry
// behaved before this field existed, so nothing already in the collection
// needs re-tagging to keep showing up where it always has. Whatever
// generates a real investment memo going forward needs to set
// docType: 'investment-memo' on write for it to bucket correctly.
export async function listDealResearchDecks() {
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
}

export async function deleteDealResearchDeck(id) {
  await db().collection('dealResearchDecks').doc(id).delete();
}

export async function getDealResearchDeck(id) {
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
}
