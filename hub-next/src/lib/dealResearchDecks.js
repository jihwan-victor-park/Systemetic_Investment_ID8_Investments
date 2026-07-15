import 'server-only';
import { db, isoDate } from './firestore';

export async function listDealResearchDecks() {
  const snap = await db().collection('dealResearchDecks').orderBy('companyName').get();
  return snap.docs.map((doc) => {
    const d = doc.data();
    return { id: doc.id, companyName: d.companyName, thesis: d.thesis, stage: d.stage, deckPath: d.deckPath, createdAt: isoDate(d.createdAt) };
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
    createdAt: isoDate(d.createdAt),
  };
}
