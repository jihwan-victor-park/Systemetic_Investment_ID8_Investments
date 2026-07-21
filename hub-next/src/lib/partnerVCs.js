import 'server-only';
import { db, isoDate } from './firestore';

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
    latestRound: p.latestRound || '',
    latestRoundDate: p.latestRoundDate || null,
    category: p.category || '',
    description: p.description || '',
    pitchbookUrl: p.pitchbookUrl || '',
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
