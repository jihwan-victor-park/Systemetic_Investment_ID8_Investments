#!/usr/bin/env node
// Loads every partner VC in scripts/data/partner-vcs-seed.json (all 75, as
// of the real Attio "ID8 Partner VCs" export parsed by
// parse-partner-vcs-csv.mjs) into partnerVCs -- fund identity/metadata for
// all of them, plus full PitchBook portfolio history for the ones already
// enriched. Real data, real doc ids (not "example-" prefixed) -- upsert-safe
// (merge:true keyed by a deterministic slug) so it's safe to re-run as more
// firms get portfolio-enriched later. Does NOT touch the `companies`
// collection / deal pipeline at all -- portfolio companies land only in
// partnerVCs.portfolio, matched against the real pipeline at *read* time via
// companyIndex, never written into it.
//
// Usage:
//   FIRESTORE_EMULATOR_HOST=localhost:8090 node scripts/backfill-partner-vcs.mjs   (local)
//   GCP_PROJECT_ID=molten-crowbar-498920-q8 node scripts/backfill-partner-vcs.mjs  (real project)
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { Firestore } from '@google-cloud/firestore';

const db = new Firestore({ projectId: process.env.GCP_PROJECT_ID || undefined });
const __dirname = dirname(fileURLToPath(import.meta.url));

const SEED_PATH = join(__dirname, 'data', 'partner-vcs-seed.json');
const firms = JSON.parse(readFileSync(SEED_PATH, 'utf-8'));

async function main() {
  for (const firm of firms) {
    const { slug, ...data } = firm;
    const ref = db.collection('partnerVCs').doc(slug);
    // Re-running this against all 75 (10 already real, 65 brand new) must
    // not stamp a fresh createdAt on the 10 that already exist -- an
    // unconditional `new Date()` here would silently overwrite their real
    // creation dates on every re-run.
    const snap = await ref.get();
    const payload = snap.exists ? data : { ...data, createdAt: new Date() };
    await ref.set(payload, { merge: true });
    console.log(`partnerVCs/${slug}  (${firm.portfolio.length} portfolio companies)${snap.exists ? '' : ' — new'}`);
  }
  console.log(`\nDone. ${firms.length} partner VCs written.`);
}

main().then(() => process.exit(0)).catch((err) => { console.error(err); process.exit(1); });
