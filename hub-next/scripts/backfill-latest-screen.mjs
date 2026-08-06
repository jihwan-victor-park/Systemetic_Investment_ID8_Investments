#!/usr/bin/env node
// One-time backfill for the performance fix in lib/companies.js's
// listCompanies() (2026-07-28): copies each company's latest screen (by
// `date` desc) from its screens subcollection onto the parent doc as
// `latestScreen` -- the exact shape deal_intelligence/firestore_push.py now
// writes at screen-creation time going forward. Without this, every company
// screened before that fix falls back to the old one-Firestore-read-per-
// company path in listCompanies() until it happens to get re-screened.
// Running this once collapses that fallback population to zero immediately
// instead of waiting on re-screens to trickle it down.
//
// Safe to re-run: only ever overwrites `latestScreen` with what the
// screens subcollection actually says, never touches anything else on the
// company doc, and a company with no screens is skipped (left at
// latestScreen: null, same as listCompanies() already treats a screen-less
// company).
//
// Usage:
//   FIRESTORE_EMULATOR_HOST=localhost:8090 node scripts/backfill-latest-screen.mjs   (local)
//   GCP_PROJECT_ID=molten-crowbar-498920-q8 node scripts/backfill-latest-screen.mjs  (real project)
import { Firestore } from '@google-cloud/firestore';

const db = new Firestore({ projectId: process.env.GCP_PROJECT_ID || undefined });

async function main() {
  const companiesSnap = await db.collection('companies').get();
  console.log(`${companiesSnap.size} companies found.`);

  let updated = 0;
  let skippedNoScreen = 0;
  let skippedAlreadySet = 0;

  for (const doc of companiesSnap.docs) {
    const data = doc.data();
    if (data.latestScreen) {
      skippedAlreadySet++;
      continue;
    }
    const screensSnap = await db
      .collection('companies')
      .doc(doc.id)
      .collection('screens')
      .orderBy('date', 'desc')
      .limit(1)
      .get();
    if (screensSnap.empty) {
      // Explicitly stamp `latestScreen: null` rather than leaving the field
      // absent (2026-08-06 fix -- this branch used to just `continue`,
      // which meant a screen-less company's `latestScreen` field stayed
      // genuinely UNDEFINED forever, not null. listCompanies()'s fallback
      // check is `latestScreen === null && data.latestScreen === undefined`
      // -- undefined is exactly what re-triggers its one-Firestore-read-per-
      // company fallback on EVERY page load, for EVERY screen-less company,
      // forever. A screen-less company was never actually helped by this
      // script before this fix, despite the docstring above already
      // claiming it was.
      await doc.ref.set({ latestScreen: null }, { merge: true });
      skippedNoScreen++;
      continue;
    }
    const latest = screensSnap.docs[0].data();
    await doc.ref.set(
      {
        latestScreen: {
          date: latest.date,
          roundStage: latest.roundStage || null,
          fitScore: latest.fitScore ?? null,
          gate: latest.gate ?? (latest.verdict || '').startsWith('clears gate'),
        },
      },
      { merge: true }
    );
    updated++;
    console.log(`companies/${doc.id}  <-  latestScreen from ${latest.date}`);
  }

  console.log(`\nDone. ${updated} updated, ${skippedAlreadySet} already had latestScreen, ${skippedNoScreen} have no screens at all.`);
}

main().then(() => process.exit(0)).catch((err) => { console.error(err); process.exit(1); });
