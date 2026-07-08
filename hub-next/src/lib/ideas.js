import 'server-only';
import { db, isoDate } from './firestore';

export async function listIdeas() {
  const snap = await db().collection('ideas').orderBy('createdAt', 'desc').get();
  return snap.docs.map((doc) => {
    const d = doc.data();
    return { id: doc.id, type: d.type, title: d.title, note: d.note || '', createdAt: isoDate(d.createdAt) };
  });
}

export async function addIdea({ type, title, note }) {
  const ref = await db().collection('ideas').add({ type, title, note: note || '', createdAt: new Date() });
  return ref.id;
}

export async function deleteIdea(id) {
  await db().collection('ideas').doc(id).delete();
}
