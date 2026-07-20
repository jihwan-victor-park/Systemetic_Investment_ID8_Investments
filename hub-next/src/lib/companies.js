import 'server-only';
import { db, isoDate } from './firestore';
import { dimensionScore, fitScore } from './rubricMath';
import { STAGES } from './stages';

// Firestore Timestamp fields don't survive JSON.stringify as anything
// useful on their own (see isoDate) -- normalize the whole origin map here
// so every reader (table column, detail page) gets plain serializable
// values, and missing origin (every company that predates this feature)
// comes back as null rather than a half-populated object.
function _mapOrigin(o) {
  if (!o) return null;
  return {
    source: o.source || null,
    attioRecordId: o.attioRecordId || null,
    attioStage: o.attioStage || null,
    round: o.round || null,
    hq: o.hq || null,
    leadInvestors: o.leadInvestors || null,
    importedAt: isoDate(o.importedAt),
  };
}

export async function listCompanies() {
  const snap = await db().collection('companies').orderBy('name').get();
  // One Firestore round trip per company for its latest screen -- run them
  // concurrently (Promise.all preserves snap.docs' name-sorted order in the
  // result regardless of which query resolves first) instead of sequentially,
  // which used to serialize one network round trip per company and got
  // dramatically slower as the company count grew (300+ after the Attio
  // bulk import).
  return Promise.all(snap.docs.map(async (doc) => {
    const data = doc.data();
    const latestSnap = await db()
      .collection('companies')
      .doc(doc.id)
      .collection('screens')
      .orderBy('date', 'desc')
      .limit(1)
      .get();
    const latest = latestSnap.empty ? null : latestSnap.docs[0].data();
    return {
      slug: doc.id,
      name: data.name,
      website: data.website,
      // Every company that predates the Watchlist/Pipeline split has no
      // `stage` field written yet -- treat that as "qualified" since that's
      // where they were all shown before these buckets existed.
      stage: STAGES.includes(data.stage) ? data.stage : 'qualified',
      round: data.round || null,
      origin: _mapOrigin(data.origin),
      latestScreen: latest
        ? {
            date: isoDate(latest.date),
            roundStage: latest.roundStage || null,
            fitScore: latest.fitScore ?? null,
            gate: latest.gate ?? (latest.verdict || '').startsWith('clears gate'),
          }
        : null,
    };
  }));
}

// Moves a company between Watchlist / Pipeline / Qualified Deals -- the
// dropdown on each stage table's row calls this via the /api/companies/
// [slug]/stage route. Internal-role-only; enforced by the API route.
export async function updateCompanyStage(slug, stage) {
  if (!STAGES.includes(stage)) throw new Error('invalid-stage');
  const ref = db().collection('companies').doc(slug);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('company-not-found');
  await ref.set({ stage }, { merge: true });
  return { slug, stage };
}

// Updates the hub's own editable Series value -- independent of
// origin.round (Attio's last-synced value, refreshed on every re-import).
// Once edited here, push_company_from_attio's don't-clobber rule means a
// later Attio re-import never overwrites it. Internal-role-only; enforced
// by the API route.
export async function updateCompanyRound(slug, round) {
  const ref = db().collection('companies').doc(slug);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('company-not-found');
  const value = String(round ?? '').trim() || null;
  await ref.set({ round: value }, { merge: true });
  return { slug, round: value };
}

function _mapScreen(slug, screenId, d) {
  return {
    id: screenId,
    date: isoDate(d.date),
    roundStage: d.roundStage || null,
    fitScore: d.fitScore ?? null,
    rawScore: d.rawScore ?? null,
    verdict: d.verdict || null,
    // `gate` is a first-class field on screens written after this feature
    // shipped; earlier screens only ever stored the derived `verdict` badge
    // text ("clears gate · ..."), so fall back to reading that instead of
    // requiring a backfill.
    gate: d.gate ?? (d.verdict || '').startsWith('clears gate'),
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
  return { slug, name: data.name, website: data.website, origin: _mapOrigin(data.origin), screens };
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

// Removes a company from whichever stage table it's in and wipes its screen
// history -- Firestore doesn't cascade-delete subcollections, so the screens
// docs need their own batch delete alongside the company doc itself.
// Internal-role-only; enforced by the API route.
export async function deleteCompany(slug) {
  const ref = db().collection('companies').doc(slug);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('company-not-found');
  const screensSnap = await ref.collection('screens').get();
  const batch = db().batch();
  screensSnap.docs.forEach((doc) => batch.delete(doc.ref));
  batch.delete(ref);
  await batch.commit();
}

export async function listCompanySlugsForSidebar() {
  const snap = await db().collection('companies').orderBy('name').get();
  return snap.docs.map((doc) => {
    const data = doc.data();
    return { slug: doc.id, name: data.name, stage: STAGES.includes(data.stage) ? data.stage : 'qualified' };
  });
}
