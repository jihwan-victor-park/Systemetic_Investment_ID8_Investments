#!/usr/bin/env node
/**
 * Bulk-rename market map titles from a CSV.
 *
 * Usage:
 *   node scripts/bulk-rename-map-titles.mjs market-map-titles.csv
 *
 * CSV format (from extract-map-titles.mjs):
 *   current_title,actual_title
 *   "Old Name","New Name"
 *
 * Reads CSV, prompts for confirmation, then updates Firestore.
 */

import * as fs from 'fs';
import * as readline from 'readline';
import * as path from 'path';
import admin from 'firebase-admin';
import { parse } from 'csv-parse/sync';

const csvFile = process.argv[2];
if (!csvFile) {
  console.error('Usage: node scripts/bulk-rename-map-titles.mjs <csv-file>');
  process.exit(1);
}

if (!fs.existsSync(csvFile)) {
  console.error(`File not found: ${csvFile}`);
  process.exit(1);
}

const firebaseKeyPath = process.env.FIREBASE_ADMIN_KEY || './firebase-key.json';
if (!fs.existsSync(firebaseKeyPath)) {
  console.error(`Error: ${firebaseKeyPath} not found`);
  process.exit(1);
}

const serviceAccount = JSON.parse(fs.readFileSync(firebaseKeyPath, 'utf8'));
admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
const db = admin.firestore();

async function confirm(message) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(`${message} (yes/no): `, (ans) => {
      rl.close();
      resolve(ans.toLowerCase() === 'yes' || ans.toLowerCase() === 'y');
    });
  });
}

async function main() {
  const csvText = fs.readFileSync(csvFile, 'utf8');
  const records = parse(csvText, { columns: true, skip_empty_lines: true });

  // Filter out entries where actual title == "(PDF)" or "(no image)" or "(error)"
  const toUpdate = records.filter(
    (r) =>
      r.actual_title &&
      !r.actual_title.startsWith('(') &&
      r.current_title !== r.actual_title
  );

  if (toUpdate.length === 0) {
    console.log('No title changes needed.');
    process.exit(0);
  }

  console.log(`Found ${toUpdate.length} entries with title changes:\n`);
  for (const row of toUpdate) {
    console.log(`  "${row.current_title}"`);
    console.log(`  → "${row.actual_title}"\n`);
  }

  const ok = await confirm(`Apply these ${toUpdate.length} renames?`);
  if (!ok) {
    console.log('Cancelled.');
    process.exit(0);
  }

  console.log('Updating Firestore...');
  let updated = 0;
  let failed = 0;

  for (const row of toUpdate) {
    try {
      // Find the doc with this title
      const snap = await db
        .collection('marketMapEntries')
        .where('title', '==', row.current_title)
        .limit(1)
        .get();

      if (snap.empty) {
        console.error(`  ✗ Not found: "${row.current_title}"`);
        failed++;
        continue;
      }

      const doc = snap.docs[0];
      await doc.ref.update({ title: row.actual_title });
      console.log(`  ✓ "${row.current_title}" → "${row.actual_title}"`);
      updated++;
    } catch (err) {
      console.error(`  ✗ Error updating "${row.current_title}":`, err.message);
      failed++;
    }
  }

  console.log(`\nDone: ${updated} updated, ${failed} failed.`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
