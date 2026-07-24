import 'server-only';
import { unstable_cache, revalidateTag } from 'next/cache';
import { db, isoDate } from './firestore';
import { matchContacts } from './contactMatch';

const ATTIO_WORKSPACE = 'i-d-8-investments';

export function attioCompanyUrl(attioId) {
  return attioId ? `https://app.attio.com/${ATTIO_WORKSPACE}/company/${attioId}` : '';
}

const COLLECTION = 'partnerVCs';

// Normalizes one portfolio-company entry -- a raw, schema-less object on the
// VC doc's `portfolio` array. `roundInvested` is the canonical field going
// forward (the round the migration/backfill will write); it falls back to
// the legacy `series` value so the ~200 entries already backfilled under the
// old field name (see project_partner_vc_portfolio_backfill_jul2026 memory)
// still show a value instead of going blank. `series` itself is left
// untouched on write -- nothing here deletes it, this is a read-side
// fallback only.
function _mapPortfolioEntry(p) {
  return {
    company: p.company,
    industry: p.industry || '',
    roundInvested: p.roundInvested || p.series || '',
    investorSince: p.investorSince || null,
    latestRound: p.latestRound || '',
    latestRoundDate: p.latestRoundDate || null,
    // Set by portfolio_fit.write_back() only when the stage-resolution pass
    // replaced a stale/generic on-file round with the true researched one --
    // holds the original PitchBook value for provenance (shown on hover).
    latestRoundOnFile: p.latestRoundOnFile || '',
    category: p.category || '',
    description: p.description || '',
    pitchbookUrl: p.pitchbookUrl || '',
    // Stamped by deal_intelligence/portfolio_prefilter.py's run_all() --
    // undefined for anything not yet evaluated (funds over 500 companies are
    // deliberately deferred, see DEFAULT_MAX_FUND_SIZE), never inferred here.
    prefilterPass: p.prefilterPass ?? null,
    prefilterReason: p.prefilterReason || '',
    // Stage 0 Portfolio Fit results, stamped by deal_intelligence/portfolio_fit.py's
    // write_back() -- null until a company has actually been scored (only the
    // subset run through the paid pass has these). fitCurrentStage is the round
    // the dedicated stage-resolution pass researched, more current than latestRound.
    fitScore: p.fitScore ?? null,
    fitTier: p.fitTier || '',
    fitCurrentStage: p.fitCurrentStage || '',
    fitRaiseProbability: p.fitRaiseProbability || '',
    fitTooEarly: p.fitTooEarly ?? null,
    fitRationale: p.fitRationale || '',
    fitScoredAt: p.fitScoredAt || null,
    // Per-dimension breakdown (AI/Thesis, Founder/Team, Fundamentals, Stage &
    // Backing) + the supporting evidence strings -- everything the fit-score
    // hover popover shows, same depth as a Stage 1 screen.
    fitDimensions: p.fitDimensions || [],
    fitConfidence: p.fitConfidence || '',
    fitHardPassReason: p.fitHardPassReason || '',
    fitCurrentStageEvidence: p.fitCurrentStageEvidence || '',
    fitRaiseProbabilityEvidence: p.fitRaiseProbabilityEvidence || '',
    fitResearchFlag: p.fitResearchFlag || '',
    // The deterministic timing-only starting point (portfolio_timing.py),
    // before the model's qualitative overlay -- fitRaiseProbability above is
    // the final band after that overlay.
    fitBaseRateBand: p.fitBaseRateBand || '',
  };
}

// A partner's own personal contact into a VC firm -- distinct from topVCs
// (the curated Tier 1 list). trackedBy/contact/portfolio are still entirely
// admin-typed, but name/description/attioCategories/connectionStrength now
// come from a real Attio export (see scripts/parse-partner-vcs-csv.mjs) --
// `description` is the fund's own literal blurb (e.g. "we invest $500k-$2M
// in pre-traction companies"), deliberately kept separate from
// `attioCategories` (Attio's own tag, e.g. "Venture Capital"). Both feed the
// same isSectorInScope keyword check portfolio companies already use --
// see PartnerPortfolioSection.jsx and the VC page's own "may be off-thesis"
// flag -- letting a fund-level description cheaply flag an entire portfolio
// as likely off-thesis before ever pulling its individual companies.
function _mapVC(doc) {
  const d = doc.data();
  return {
    id: doc.id,
    name: d.name,
    trackedBy: d.trackedBy || '',
    contact: d.contact || '',
    contactEmails: d.contactEmails || '',
    contacts: matchContacts(d.contact || '', d.contactEmails || ''),
    attioId: d.attioId || '',
    sector: d.sector || '',
    website: d.website || '',
    note: d.note || '',
    description: d.description || '',
    attioCategories: d.attioCategories || '',
    connectionStrength: d.connectionStrength || '',
    portfolio: (d.portfolio || []).map(_mapPortfolioEntry),
    news: d.news || [],
    createdAt: isoDate(d.createdAt),
  };
}

// force-dynamic on every /docs/* route (see DocsShell/layout.jsx) means no
// route-level cache -- listPartnerVCs() fetches ALL 74 VC docs (7+MB and
// growing as Stage 0 scoring adds fields to each portfolio company) on nearly
// every page in the hub (Watchlist/Pipeline/Qualified/Radar/Invested, every
// company detail page's investor cross-reference, Hot Deals, the VCs
// directory, search...). CACHE_SECONDS trades a little staleness (an edit
// shows up for OTHER viewers within this window; your own always shows
// immediately via revalidateTag('partner-vcs') below) for a large cut in
// Firestore reads -- this was the single biggest "site is slow" contributor
// once portfolios grew past a few hundred scored companies.
const CACHE_SECONDS = 60;

export const listPartnerVCs = unstable_cache(async () => {
  const snap = await db().collection(COLLECTION).orderBy('name').get();
  return snap.docs.map(_mapVC);
}, ['list-partner-vcs'], { tags: ['partner-vcs'], revalidate: CACHE_SECONDS });

export const getPartnerVC = unstable_cache(async (id) => {
  const doc = await db().collection(COLLECTION).doc(id).get();
  return doc.exists ? _mapVC(doc) : null;
}, ['get-partner-vc'], { tags: ['partner-vcs'], revalidate: CACHE_SECONDS });

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
  revalidateTag('partner-vcs');
  return ref.id;
}

// Same shallow merge-patch pattern as updateTopVC -- callers send the whole
// portfolio/news array back on every edit.
export async function updatePartnerVC(id, patch) {
  const ref = db().collection(COLLECTION).doc(id);
  const snap = await ref.get();
  if (!snap.exists) throw new Error('vc-not-found');
  await ref.set(patch, { merge: true });
  revalidateTag('partner-vcs');
  return { id };
}

export async function deletePartnerVC(id) {
  await db().collection(COLLECTION).doc(id).delete();
  revalidateTag('partner-vcs');
}
