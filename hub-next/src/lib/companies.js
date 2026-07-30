import 'server-only';
import { unstable_cache, revalidateTag } from 'next/cache';
import { db, isoDate } from './firestore';
import { dimensionScore, fitScore } from './rubricMath';
import { STAGES, TAGS } from './stages';
import { companySlug } from './companySlug';

// Every /docs/* route is force-dynamic (see DocsShell/layout.jsx's own
// comment on why -- sidebar freshness), which disables Next's route-level
// cache entirely, so without this every one of those page loads re-ran
// listCompanies()'s N+1 (one Firestore read per company, on top of the full
// collection read) from scratch. CACHE_SECONDS trades a little staleness
// for everyone ELSE'S view (your own edits still show immediately via
// revalidateTag('companies') below, from every write function in this file)
// for a large cut in Firestore reads/latency -- this was the single biggest
// contributor to "the site is slow" once portfolios grew past a few hundred
// companies with real Stage 0 fit data attached.
const CACHE_SECONDS = 60;

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
    // The round's close date, off Attio's 'deal_date' slug (see
    // deal_intelligence/firestore_push.py) -- added 2026-07-28 for Radar's
    // capital-clock math (RADAR_PLAN.md Part I), which needs it to estimate
    // runway/cash-out. Same don't-clobber relationship to the top-level
    // `roundDate` (below) that origin.round already has with `round`.
    roundDate: o.roundDate || null,
    // The round's size in real dollars, off Attio's 'deal_size' currency
    // slug (see deal_intelligence/firestore_push.py) -- added 2026-07-28,
    // Radar's capital clock (RADAR_PLAN.md Part III) needs this as
    // `roundSize`, its other burn-math input besides headcount. Same
    // don't-clobber relationship to the top-level `roundSize` (below) that
    // origin.round already has with `round`.
    roundSize: o.roundSize || null,
    hq: o.hq || null,
    leadInvestors: o.leadInvestors || null,
    // Attio's own "Radar Category" field -- the category a Top 10 VC deal
    // arrives under when it's Series A or earlier. Raw, last-synced value;
    // radarCategory (top-level, below) is the hub's own editable copy, same
    // don't-clobber relationship origin.round already has with `round`.
    radarCategory: o.radarCategory || null,
    importedAt: isoDate(o.importedAt),
  };
}

// Reads the same {date, roundStage, fitScore, gate} shape listCompanies()
// has always returned, preferring the denormalized copy on the company doc
// itself (written at screen-creation time by
// deal_intelligence/firestore_push.py as of 2026-07-28) over a subcollection
// query. `gate` falls back to parsing `verdict` only for the pre-2026-07-28
// subcollection shape, which never had a `gate` field of its own.
function _mapLatestScreen(raw) {
  if (!raw) return null;
  return {
    date: isoDate(raw.date),
    roundStage: raw.roundStage || null,
    fitScore: raw.fitScore ?? null,
    gate: raw.gate ?? (raw.verdict || '').startsWith('clears gate'),
  };
}

export const listCompanies = unstable_cache(async () => {
  const snap = await db().collection('companies').orderBy('name').get();
  // Denormalized fast path (see _mapLatestScreen above): a company screened
  // since 2026-07-28 carries its own latest-screen summary right on this
  // doc, so most companies need zero extra reads here. Only a company that
  // predates that change (or hasn't been re-screened since) falls through to
  // the slow path below -- one Firestore round trip per such company, same
  // as this whole function used to do for every company before the fix.
  // That fallback population shrinks to zero once
  // scripts/backfill-latest-screen.mjs has run once in production.
  return Promise.all(snap.docs.map(async (doc) => {
    const data = doc.data();
    let latestScreen = _mapLatestScreen(data.latestScreen);
    if (latestScreen === null && data.latestScreen === undefined) {
      const latestSnap = await db()
        .collection('companies')
        .doc(doc.id)
        .collection('screens')
        .orderBy('date', 'desc')
        .limit(1)
        .get();
      latestScreen = latestSnap.empty ? null : _mapLatestScreen(latestSnap.docs[0].data());
    }
    return {
      slug: doc.id,
      name: data.name,
      website: data.website,
      // Every company that predates the Watchlist/Pipeline split has no
      // `stage` field written yet -- treat that as "qualified" since that's
      // where they were all shown before these buckets existed.
      stage: STAGES.includes(data.stage) ? data.stage : 'qualified',
      round: data.round || null,
      roundDate: data.roundDate || null,
      roundSize: data.roundSize || null,
      // PitchBook's company description, off Attio -- refreshed on every
      // import/screen (see deal_intelligence/firestore_push.py), not a
      // hub-editable field like round/radarCategory. Feeds the
      // relevance-exclusion list (RADAR_PLAN.md §1.6, lib/radarRules.js).
      description: data.description || null,
      // Hub-editable copies -- same relationship to their Attio-synced
      // origin.* counterpart as `round` has to `origin.round` (see
      // updateCompanyRadarCategory below): once set here, a re-import never
      // clobbers it.
      radarCategory: data.radarCategory || null,
      pitchbookUrl: data.pitchbookUrl || null,
      // Attio's own "Top 10 VC" deal flag, synced on every Attio import --
      // see deal_intelligence/firestore_push.py's push_company_from_attio.
      // Not hub-editable (no don't-clobber rule like round/radarCategory
      // above): it should always mirror whatever Attio currently says.
      top10VC: !!data.top10VC,
      origin: _mapOrigin(data.origin),
      latestScreen,
      // Mandate screen + capital clock + scan schedule (RADAR_PLAN.md Part
      // VIII), written by deal_intelligence/radar_state.py -- null for
      // every non-Radar company, and for a Radar company that hasn't had
      // its first recompute yet (a brand-new arrival, before the Attio-
      // import hook or the next backfill/scan-runner pass touches it).
      // Read-only here; see hub-next/src/lib/radar.js for formatters.
      radar: data.radar || null,
      // Additive tags (see stages.js's TAGS comment) -- 'qualified'/'radar'
      // membership independent of `stage`.
      tags: Array.isArray(data.tags) ? data.tags : [],
      // This company's own cap table, by domain (Attio's investors_ref
      // reference field, see deal_intelligence/attio_io.py's
      // _investor_domains) -- feeds companyIndex.js's domainMatchesFromIndex,
      // a different check than the name-match above (does this company
      // already have one of OUR partner VCs as an investor). Added 2026-07-28.
      investorDomains: Array.isArray(data.investorDomains) ? data.investorDomains : [],
    };
  }));
}, ['list-companies'], { tags: ['companies'], revalidate: CACHE_SECONDS });

function backendHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.PIPELINE_INTERNAL_SECRET) headers['X-Internal-Secret'] = process.env.PIPELINE_INTERNAL_SECRET;
  return headers;
}

// Mirrors a hand-made stage change back onto the matching Attio Deal record
// via pipeline/app.py's /update-deal-stage (see that route's own docstring
// for the write-format details). Attio -> hub-next sync has existed for a
// while (push_company_from_attio); this is the direction that didn't exist
// at all until now -- a stage edit made directly in hub-next used to stay
// siloed in Firestore forever, silently drifting from whatever Attio still
// showed. Best-effort and non-blocking: the Firestore write above is
// hub-next's own source of truth regardless of whether this succeeds, and a
// company with no origin.attioRecordId (created directly in the hub, never
// synced from Attio) has nothing to push back to -- skipped, not an error.
async function pushStageToAttio(slug, stage, attioRecordId) {
  if (!attioRecordId) return;
  if (!process.env.PIPELINE_BASE_URL) {
    console.warn(`pushStageToAttio(${slug}): PIPELINE_BASE_URL not configured -- skipping Attio write-back`);
    return;
  }
  try {
    const res = await fetch(`${process.env.PIPELINE_BASE_URL}/update-deal-stage`, {
      method: 'POST',
      headers: backendHeaders(),
      body: JSON.stringify({ record_id: attioRecordId, stage }),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      console.error(`pushStageToAttio(${slug}): pipeline returned ${res.status}: ${text.slice(0, 300)}`);
    }
  } catch (e) {
    console.error(`pushStageToAttio(${slug}): request failed:`, e);
  }
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
  revalidateTag('companies');
  await pushStageToAttio(slug, stage, snap.data()?.origin?.attioRecordId);
  return { slug, stage };
}

// Sets a company's full `tags` array from the multiselect editor
// (StageMultiSelect.jsx, formerly TagsSelect.jsx before TAGS widened to
// every public stage 2026-07-30) -- overwrite, not arrayUnion, since the UI
// already shows (and the user is explicitly choosing) the complete
// resulting set, including removing a tag the server auto-added. See
// stages.js's TAGS comment for the auto-add mechanism this can override.
// Internal-role-only; enforced by the API route.
export async function updateCompanyTags(slug, tags) {
  const clean = Array.from(new Set((tags || []).filter((t) => TAGS.includes(t))));
  const ref = db().collection('companies').doc(slug);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('company-not-found');
  await ref.set({ tags: clean }, { merge: true });
  revalidateTag('companies');
  return { slug, tags: clean };
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
  revalidateTag('companies');
  return { slug, round: value };
}

// Same not-clobbered-by-Attio-reimport relationship as updateCompanyRound
// above, for the Radar Category the deal arrived under (Attio's own field --
// see origin.radarCategory in _mapOrigin). Internal-role-only; enforced by
// the API route.
export async function updateCompanyRadarCategory(slug, radarCategory) {
  const ref = db().collection('companies').doc(slug);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('company-not-found');
  const value = String(radarCategory ?? '').trim() || null;
  await ref.set({ radarCategory: value }, { merge: true });
  revalidateTag('companies');
  return { slug, radarCategory: value };
}

// PitchBook profile URL -- plain hub-editable field, no Attio counterpart.
// Internal-role-only; enforced by the API route.
export async function updateCompanyPitchbookUrl(slug, pitchbookUrl) {
  const ref = db().collection('companies').doc(slug);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('company-not-found');
  const value = String(pitchbookUrl ?? '').trim() || null;
  await ref.set({ pitchbookUrl: value }, { merge: true });
  revalidateTag('companies');
  return { slug, pitchbookUrl: value };
}

// Promotes a partner VC's portfolio company into the real pipeline at a
// chosen stage -- the opt-in counterpart to the automatic name-match every
// portfolio table row already shows via companyIndex. Never fires on its
// own; only from a partner's own "Add..." control, and never
// touches a company that's already there (a slug collision here most often
// means a name mismatch between the portfolio entry and an existing pipeline
// company -- surfacing that as an error is safer than silently overwriting
// whatever stage it's already in). Internal-role-only; enforced by the API
// route.
//
// `round` is required, not inferred here -- the caller (PromoteToPipeline.jsx)
// pre-fills it from whatever the portfolio entry/Stage 0 scan already knows
// (the researched current round when available), but a human confirms it
// before the company enters the real pipeline with a blank Series field.
export async function createCompanyFromPortfolio({ name, stage, sourceVCName, round }) {
  if (!STAGES.includes(stage)) throw new Error('invalid-stage');
  const slug = companySlug(name);
  if (!slug) throw new Error('invalid-name');
  const roundValue = String(round ?? '').trim();
  if (!roundValue) throw new Error('invalid-round');
  const ref = db().collection('companies').doc(slug);
  const snap = await ref.get();
  if (snap.exists) throw new Error('already-exists');
  await ref.set({
    name,
    website: null,
    stage,
    round: roundValue,
    origin: { source: 'partner-vc-portfolio', leadInvestors: sourceVCName || null, importedAt: new Date() },
  });
  revalidateTag('companies');
  return { slug, stage, round: roundValue };
}

// Every company doc's "family" identity for multi-round tracking --
// `companyKey` is absent on every doc created before this feature (the
// single-round-per-company era), which is fine: those all implicitly key off
// their own slug, so nothing needs a backfill for existing data to keep
// working exactly as it did before.
function companyKeyOf(data, slug) {
  return data.companyKey || slug;
}

// Lets ID8 track a second (or third...) round for a company already in the
// pipeline without overwriting the existing entry -- e.g. Series A is
// Qualified, then months later the same company raises a Series B and we
// want a distinct tracked deal for it, not a silent overwrite of the first
// one. The new doc's id is `${companyKey}--${roundSlug}`, never a bare-slug
// collision with the original (whose id is untouched) -- that also keeps the
// external Attio-import pipeline's own slug-based dedup (companySlug.js)
// matching only the first round's doc, not this one. Rejects an exact
// duplicate round for the same company family (case-insensitive) -- that's
// the "don't have a duplicated round" half of the ask; a differently-worded
// but effectively-same round is on the caller to catch. Internal-role-only;
// enforced by the API route.
export async function createAdditionalRound(baseSlug, { round, stage }) {
  if (!STAGES.includes(stage)) throw new Error('invalid-stage');
  const roundValue = String(round ?? '').trim();
  if (!roundValue) throw new Error('invalid-round');

  const baseRef = db().collection('companies').doc(baseSlug);
  const baseSnap = await baseRef.get();
  if (!baseSnap.exists) throw new Error('company-not-found');
  const baseData = baseSnap.data();
  const companyKey = companyKeyOf(baseData, baseSlug);

  const familySnap = await db().collection('companies').where('companyKey', '==', companyKey).get();
  const existingRounds = new Set(familySnap.docs.map((d) => (d.data().round || '').trim().toLowerCase()));
  // The base doc itself only shows up in that query once it's been given a
  // companyKey (below, on this or an earlier additional round) -- until
  // then, check its own round directly so a same-name duplicate is still
  // caught on the very first additional round created.
  if (!baseData.companyKey) existingRounds.add((baseData.round || '').trim().toLowerCase());
  if (existingRounds.has(roundValue.toLowerCase())) throw new Error('duplicate-round');

  const roundSlugPart = companySlug(roundValue) || 'round';
  const newSlug = `${companyKey}--${roundSlugPart}`;
  const newRef = db().collection('companies').doc(newSlug);
  if ((await newRef.get()).exists) throw new Error('duplicate-round');

  await newRef.set({
    name: baseData.name,
    website: baseData.website || null,
    stage,
    round: roundValue,
    companyKey,
    origin: { source: 'additional-round', leadInvestors: baseData.origin?.leadInvestors || null, importedAt: new Date() },
  });
  if (!baseData.companyKey) await baseRef.set({ companyKey }, { merge: true });

  revalidateTag('companies');
  return { slug: newSlug, companyKey, round: roundValue, stage };
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

function _mapMemo(memoId, d) {
  return {
    id: memoId,
    date: isoDate(d.date),
    finalScore: d.finalScore ?? null,
    sections: d.sections || {},
    sources: d.sources || [],
  };
}

export const getCompany = unstable_cache(async (slug) => {
  const doc = await db().collection('companies').doc(slug).get();
  if (!doc.exists) return null;
  const data = doc.data();
  const [screensSnap, memosSnap] = await Promise.all([
    db().collection('companies').doc(slug).collection('screens').orderBy('date', 'desc').get(),
    db().collection('companies').doc(slug).collection('memos').orderBy('date', 'desc').get(),
  ]);
  const screens = screensSnap.docs.map((s) => _mapScreen(slug, s.id, s.data()));
  const memos = memosSnap.docs.map((m) => _mapMemo(m.id, m.data()));
  return {
    slug,
    name: data.name,
    website: data.website,
    stage: STAGES.includes(data.stage) ? data.stage : 'qualified',
    round: data.round || null,
    roundDate: data.roundDate || null,
    roundSize: data.roundSize || null,
    radarCategory: data.radarCategory || null,
    pitchbookUrl: data.pitchbookUrl || null,
    // Added 2026-07-30 for CompanyDetailPage's own "at a glance" facts block
    // -- both were already denormalized onto the company doc for other
    // consumers (listCompanies' `description`, deal_intelligence/
    // radar_state.py's `fields_from_company_doc` hq fallback) but getCompany
    // itself never read them back, so the one page meant to show "more
    // overall data" about a company had less of it than the list views did.
    description: data.description || null,
    hq: data.hq || data.origin?.hq || null,
    origin: _mapOrigin(data.origin),
    radar: data.radar || null,
    tags: Array.isArray(data.tags) ? data.tags : [],
    screens,
    memos,
  };
}, ['get-company'], { tags: ['companies'], revalidate: CACHE_SECONDS });

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
    revalidateTag('companies');
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
  revalidateTag('companies');
  return _mapScreen(slug, screenId, { ...data, ...update });
}

// Removes ONE screen (Oscar, 2026-07-29: "allow me to delete screen or shit
// that has failed to clean up easily" -- a scoring-failed stub, most often,
// but any screen a user wants gone) without touching the company doc or its
// other screens. If the deleted screen was the one denormalized onto
// `company.latestScreen` (the Score column every stage table reads),
// recomputes it from whatever screen is now most recent -- falls back to
// `null` (no screens left) rather than leaving a stale reference to a doc
// that no longer exists, same "don't let a table quietly show a ghost
// value" concern the radar auto-drop bug just taught this codebase.
// Internal-role-only; enforced by the API route.
export async function deleteScreen(slug, screenId) {
  const ref = db().collection('companies').doc(slug);
  const screenRef = ref.collection('screens').doc(screenId);
  const screenSnap = await screenRef.get();
  if (!screenSnap.exists) throw new Error('screen-not-found');
  await screenRef.delete();

  const companySnap = await ref.get();
  const latestScreen = companySnap.data()?.latestScreen;
  if (latestScreen?.date === screenId) {
    const remaining = await ref.collection('screens').orderBy('date', 'desc').limit(1).get();
    const next = remaining.docs[0];
    await ref.set({
      latestScreen: next
        ? { date: next.id, roundStage: next.data().roundStage ?? null, fitScore: next.data().fitScore, gate: next.data().gate }
        : null,
    }, { merge: true });
  }
  revalidateTag('companies');
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
  revalidateTag('companies');
}

export const listCompanySlugsForSidebar = unstable_cache(async () => {
  const snap = await db().collection('companies').orderBy('name').get();
  return snap.docs.map((doc) => {
    const data = doc.data();
    return {
      slug: doc.id,
      name: data.name,
      stage: STAGES.includes(data.stage) ? data.stage : 'qualified',
    };
  });
}, ['list-company-slugs-sidebar'], { tags: ['companies'], revalidate: CACHE_SECONDS });
