#!/usr/bin/env node
// Loads the first 10 real partner VCs (from Oscar's Attio "ID8 Partner VCs"
// export) into partnerVCs, with their full PitchBook portfolio history --
// the test batch for the VC-portfolio-in-hub feature. Real data, real doc
// ids (not "example-" prefixed) -- upsert-safe (merge:true keyed by a
// deterministic slug) so it's safe to re-run as more of the 76-firm list
// gets processed. Does NOT touch the `companies` collection / deal
// pipeline at all -- portfolio companies land only in partnerVCs.portfolio,
// matched against the real pipeline at *read* time via companyIndex, never
// written into it.
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
    await db.collection('partnerVCs').doc(slug).set({ ...data, createdAt: new Date() }, { merge: true });
    console.log(`partnerVCs/${slug}  (${firm.portfolio.length} portfolio companies)`);
  }
  console.log(`\nDone. ${firms.length} partner VCs written.`);
}

main().then(() => process.exit(0)).catch((err) => { console.error(err); process.exit(1); });
