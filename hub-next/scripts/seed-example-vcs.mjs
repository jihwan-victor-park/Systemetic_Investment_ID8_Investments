#!/usr/bin/env node
// Seeds a handful of clearly-fake example Partner VCs + companies so the
// VCs tab and the Portfolio graph view have something real to look at.
// Every doc this script writes uses a deterministic "example-" prefixed id
// (never Firestore's random auto-id), so they sort together and are
// trivially identifiable and deletable from the Firebase console -- nothing
// this script writes should ever be mistaken for real data. Safe to re-run
// (every write is an upsert keyed by that id).
//
// Usage:
//   FIRESTORE_EMULATOR_HOST=localhost:8090 node scripts/seed-example-vcs.mjs   (local)
//   GCP_PROJECT_ID=molten-crowbar-498920-q8 node scripts/seed-example-vcs.mjs  (real project)
//
// To remove everything this script added: in the Firebase console, open
// Firestore, and in `companies` and `partnerVCs` delete every doc whose id
// starts with "example-" -- they're the only docs with that prefix.
import { Firestore } from '@google-cloud/firestore';

const db = new Firestore({ projectId: process.env.GCP_PROJECT_ID || undefined });

const TODAY = new Date().toISOString().slice(0, 10);

// Companies ID8 has "screened" (fitScore + gate) -- these are what let the
// Portfolio graph actually show varying color/thickness. A portfolio entry
// whose name doesn't match one of these renders as a thin grey "not scored"
// line, same as it would for any real, un-screened portfolio company.
const EXAMPLE_COMPANIES = [
  { slug: 'example-nova-robotics', name: 'Nova Robotics', website: 'novarobotics.example', stage: 'qualified', fitScore: 3.7, gate: true },
  { slug: 'example-fieldsense-ai', name: 'FieldSense AI', website: 'fieldsense.example', stage: 'qualified', fitScore: 3.9, gate: true },
  { slug: 'example-brightline-health', name: 'Brightline Health', website: 'brightlinehealth.example', stage: 'watchlist', fitScore: 2.4, gate: false },
  { slug: 'example-cascade-analytics', name: 'Cascade Analytics', website: 'cascadeanalytics.example', stage: 'pipeline', fitScore: 1.8, gate: false },
];

const EXAMPLE_PARTNER_VCS = [
  {
    slug: 'example-brightpath-ventures',
    name: 'Brightpath Ventures',
    trackedBy: 'Oscar',
    contact: 'J. Kim',
    sector: 'AI, Bio',
    website: 'brightpath.example',
    note: 'Example data — safe to delete, doc id starts with "example-".',
    portfolio: [
      { company: 'Nova Robotics', industry: 'AI', series: 'Series B' },
      { company: 'FieldSense AI', industry: 'AI', series: 'Series A' },
      { company: 'Brightline Health', industry: 'Bio', series: 'Series C' },
      { company: 'Cascade Analytics', industry: 'Consumer', series: 'Seed' },
      { company: 'Fernway Robotics', industry: 'AI', series: 'Series B' },
      { company: 'Loomis Biotech', industry: 'Bio', series: 'Seed' },
    ],
    news: [],
  },
  {
    slug: 'example-northstar-capital',
    name: 'Northstar Capital',
    trackedBy: 'Isabella',
    contact: 'R. Alvarez',
    sector: 'Consumer, AI',
    website: 'northstar.example',
    note: 'Example data — safe to delete, doc id starts with "example-".',
    portfolio: [
      { company: 'Nova Robotics', industry: 'AI', series: 'Series B' },
      { company: 'Cascade Analytics', industry: 'Consumer', series: 'Seed' },
      { company: 'Alderwood Consumer', industry: 'Consumer', series: 'Series A' },
      { company: 'Ridgeline Data', industry: 'AI', series: 'Series D' },
      { company: 'Trellis Health', industry: 'Bio', series: 'Series B' },
    ],
    news: [],
  },
];

async function main() {
  for (const c of EXAMPLE_COMPANIES) {
    await db.collection('companies').doc(c.slug).set({ name: c.name, website: c.website, stage: c.stage });
    await db.collection('companies').doc(c.slug).collection('screens').doc(TODAY).set({
      date: TODAY,
      fitScore: c.fitScore,
      rawScore: c.fitScore,
      verdict: c.gate ? 'clears gate · go / ic review' : 'more diligence',
      gate: c.gate,
    });
    console.log(`companies/${c.slug}  (fitScore ${c.fitScore.toFixed(1)}, gate=${c.gate})`);
  }

  for (const v of EXAMPLE_PARTNER_VCS) {
    const { slug, ...data } = v;
    await db.collection('partnerVCs').doc(slug).set({ ...data, createdAt: new Date() }, { merge: true });
    console.log(`partnerVCs/${slug}  (${v.portfolio.length} portfolio companies)`);
  }

  console.log('\nDone. Every doc written has an id starting with "example-" — delete those from the Firebase console to remove all of it.');
}

main().then(() => process.exit(0)).catch((err) => { console.error(err); process.exit(1); });
