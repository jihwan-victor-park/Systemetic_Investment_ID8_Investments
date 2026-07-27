import 'server-only';
import { unstable_cache, revalidateTag } from 'next/cache';
import { db, isoDate } from './firestore';

// Same force-dynamic/no-route-cache reasoning as companies.js's own
// CACHE_SECONDS comment -- every /docs/* page load was re-running this full
// collection read from scratch.
const CACHE_SECONDS = 60;

export const listIdeas = unstable_cache(async () => {
  const snap = await db().collection('ideas').orderBy('createdAt', 'desc').get();
  return snap.docs.map((doc) => {
    const d = doc.data();
    return { id: doc.id, type: d.type, title: d.title, note: d.note || '', createdAt: isoDate(d.createdAt) };
  });
}, ['list-ideas'], { tags: ['ideas'], revalidate: CACHE_SECONDS });

export async function addIdea({ type, title, note }) {
  const ref = await db().collection('ideas').add({ type, title, note: note || '', createdAt: new Date() });
  revalidateTag('ideas');
  return ref.id;
}

export async function deleteIdea(id) {
  await db().collection('ideas').doc(id).delete();
  revalidateTag('ideas');
}
