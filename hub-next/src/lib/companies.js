import 'server-only';
import { db, isoDate } from './firestore';
import { dimensionScore, fitScore } from './rubricMath';

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

function _mapScreen(slug, screenId, d) {
  return {
    id: screenId,
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
  const screens = screensSnap.docs.map((s) => _mapScreen(slug, s.id, s.data()));
  return { slug, name: data.name, website: data.website, screens };
}

// Edits a single field on a screen -- a subcategory's score or finding, a
// dimension's evidence, or the deal-level rationale -- and, when a
// subcategory score changes, recomputes that dimension's score and the
// screen's fitScore/rawScore via rubricMath.js (the same equal-weight-mean
// logic deal_intelligence/rubric.py uses) so the persisted numbers never
// drift from what's displayed. Internal-role-only; enforced by the API route.
export async function updateScreenField(slug, screenId, patch) {
  const { dimensionKey, subcategoryKey, field, value } = patch || {};
  const ref = db().collection('companies').doc(slug).collection('screens').doc(screenId);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('screen-not-found');
  const data = snap.data();
  const dimensions = data.dimensions || [];

  if (field === 'rationale') {
    await ref.set({ rationale: String(value ?? '') }, { merge: true });
    return _mapScreen(slug, screenId, { ...data, rationale: String(value ?? '') });
  }

  const dimIdx = dimensions.findIndex((d) => d.key === dimensionKey);
  if (dimIdx === -1) throw new Error('dimension-not-found');
  const dim = { ...dimensions[dimIdx], subcategories: [...(dimensions[dimIdx].subcategories || [])] };

  if (field === 'evidence') {
    dim.evidence = String(value ?? '');
  } else if (field === 'score' || field === 'finding') {
    if (!subcategoryKey) throw new Error('missing-subcategory-key');
    const subIdx = dim.subcategories.findIndex((s) => s.key === subcategoryKey);
    if (subIdx === -1) throw new Error('subcategory-not-found');
    const sub = { ...dim.subcategories[subIdx] };
    if (field === 'score') {
      const n = Number(value);
      if (!Number.isInteger(n) || n < 1 || n > 4) throw new Error('invalid-score');
      sub.score = n;
    } else {
      sub.finding = String(value ?? '');
    }
    dim.subcategories[subIdx] = sub;
    dim.score = dimensionScore(dim.subcategories);
  } else {
    throw new Error('invalid-field');
  }

  const newDimensions = [...dimensions];
  newDimensions[dimIdx] = dim;
  const newFitScore = fitScore(newDimensions);
  const update = { dimensions: newDimensions, fitScore: newFitScore, rawScore: newFitScore };
  await ref.set(update, { merge: true });
  return _mapScreen(slug, screenId, { ...data, ...update });
}

export async function listCompanySlugsForSidebar() {
  const snap = await db().collection('companies').orderBy('name').get();
  return snap.docs.map((doc) => ({ slug: doc.id, name: doc.data().name }));
}
