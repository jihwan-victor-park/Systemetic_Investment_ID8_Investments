import 'server-only';
import { db, isoDate } from './firestore';

const COLLECTION = 'topVCs';

export async function listTopVCs() {
  const snap = await db().collection(COLLECTION).orderBy('tier').orderBy('name').get();
  return snap.docs.map((doc) => {
    const d = doc.data();
    return {
      id: doc.id,
      name: d.name,
      tier: d.tier,
      sector: d.sector || '',
      website: d.website || '',
      note: d.note || '',
      createdAt: isoDate(d.createdAt),
    };
  });
}

export async function addTopVC({ name, tier, sector, website, note }) {
  const ref = await db().collection(COLLECTION).add({
    name,
    tier,
    sector: sector || '',
    website: website || '',
    note: note || '',
    createdAt: new Date(),
  });
  return ref.id;
}

export async function deleteTopVC(id) {
  await db().collection(COLLECTION).doc(id).delete();
}
