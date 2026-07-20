import 'server-only';
import { db, isoDate } from './firestore';

const COLLECTION = 'partnerVCs';

// A partner's own personal contact into a VC firm -- distinct from topVCs
// (the curated Tier 1 list). Nothing here is Attio-synced yet (see
// docs/concepts/partner-vcs-and-hot-deals.html); trackedBy/contact/portfolio
// are entirely admin-typed until a real Attio relationship pipeline exists.
function _mapVC(doc) {
  const d = doc.data();
  return {
    id: doc.id,
    name: d.name,
    trackedBy: d.trackedBy || '',
    contact: d.contact || '',
    sector: d.sector || '',
    website: d.website || '',
    note: d.note || '',
    portfolio: d.portfolio || [],
    news: d.news || [],
    createdAt: isoDate(d.createdAt),
  };
}

export async function listPartnerVCs() {
  const snap = await db().collection(COLLECTION).orderBy('name').get();
  return snap.docs.map(_mapVC);
}

export async function getPartnerVC(id) {
  const doc = await db().collection(COLLECTION).doc(id).get();
  return doc.exists ? _mapVC(doc) : null;
}

export async function addPartnerVC({ name, trackedBy, contact, sector, website, note }) {
  const ref = await db().collection(COLLECTION).add({
    name,
    trackedBy: trackedBy || '',
    contact: contact || '',
    sector: sector || '',
    website: website || '',
    note: note || '',
    portfolio: [],
    news: [],
    createdAt: new Date(),
  });
  return ref.id;
}

// Same shallow merge-patch pattern as updateTopVC -- callers send the whole
// portfolio/news array back on every edit.
export async function updatePartnerVC(id, patch) {
  const ref = db().collection(COLLECTION).doc(id);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('vc-not-found');
  await ref.set(patch, { merge: true });
  return { id };
}

export async function deletePartnerVC(id) {
  await db().collection(COLLECTION).doc(id).delete();
}
