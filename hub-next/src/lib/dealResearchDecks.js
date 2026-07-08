import 'server-only';
import { db } from './firestore';

export async function listDealResearchDecks() {
  const snap = await db().collection('dealResearchDecks').orderBy('companyName').get();
  return snap.docs.map((doc) => {
    const d = doc.data();
    return { id: doc.id, companyName: d.companyName, thesis: d.thesis, stage: d.stage, deckPath: d.deckPath };
  });
}
