import 'server-only';
import { db } from './firestore';

export async function listMarketMapEntries() {
  const snap = await db().collection('marketMapEntries').orderBy('createdAt', 'desc').get();
  return snap.docs.map((doc) => {
    const d = doc.data();
    return {
      id: doc.id,
      firm: d.firm,
      title: d.title,
      cat: d.category,
      url: d.url,
      ym: d.ym ?? null,
      date: d.dateLabel,
      note: d.note || undefined,
    };
  });
}

export async function addMarketMapEntry({ firm, title, category, url, ym, dateLabel, note }) {
  const ref = await db().collection('marketMapEntries').add({
    firm,
    title,
    category,
    url,
    ym: ym ?? null,
    dateLabel,
    note: note || null,
    createdAt: new Date(),
  });
  return ref.id;
}
