import 'server-only';
import { db, isoDate } from './firestore';

export async function listCompanies() {
  const snap = await db().collection('companies').orderBy('name').get();
  const companies = [];
  for (const doc of snap.docs) {
    const data = doc.data();
    const latestSnap = await db()
      .collection('companies')
      .doc(doc.id)
      .collection('screens')
      .orderBy('date', 'desc')
      .limit(1)
      .get();
    const latest = latestSnap.empty ? null : latestSnap.docs[0].data();
    companies.push({
      slug: doc.id,
      name: data.name,
      website: data.website,
      latestScreen: latest
        ? { date: isoDate(latest.date), roundStage: latest.roundStage || null, fitScore: latest.fitScore ?? null }
        : null,
    });
  }
  return companies;
}

export async function getCompany(slug) {
  const doc = await db().collection('companies').doc(slug).get();
  if (!doc.exists) return null;
  const data = doc.data();
  const screensSnap = await db()
    .collection('companies')
    .doc(slug)
    .collection('screens')
    .orderBy('date', 'desc')
    .get();
  const screens = screensSnap.docs.map((s) => {
    const d = s.data();
    return {
      id: s.id,
      date: isoDate(d.date),
      roundStage: d.roundStage || null,
      fitScore: d.fitScore ?? null,
      rawScore: d.rawScore ?? null,
      verdict: d.verdict || null,
      hardAutoPassNote: d.hardAutoPassNote || null,
      dimensions: d.dimensions || [],
      rationale: d.rationale || '',
      confidence: d.confidence || null,
      sources: d.sources || [],
      docxPath: d.docxPath || `/research/companies/${slug}.docx`,
    };
  });
  return { slug, name: data.name, website: data.website, screens };
}

export async function listCompanySlugsForSidebar() {
  const snap = await db().collection('companies').orderBy('name').get();
  return snap.docs.map((doc) => ({ slug: doc.id, name: doc.data().name }));
}
