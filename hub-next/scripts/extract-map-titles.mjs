#!/usr/bin/env node
/**
 * Extract actual market-map titles from images using Claude vision.
 * Outputs a CSV: current_title,actual_title
 *
 * Usage: node scripts/extract-map-titles.mjs > market-map-titles.csv
 *
 * Requires:
 *   FIREBASE_ADMIN_KEY (path to service account JSON)
 *   ANTHROPIC_API_KEY (Claude API key)
 */

import * as fs from 'fs';
import * as path from 'path';
import admin from 'firebase-admin';
import { Storage } from '@google-cloud/storage';
import Anthropic from '@anthropic-ai/sdk';

const firebaseKeyPath = process.env.FIREBASE_ADMIN_KEY || './firebase-key.json';
if (!fs.existsSync(firebaseKeyPath)) {
  console.error(`Error: ${firebaseKeyPath} not found`);
  console.error('Set FIREBASE_ADMIN_KEY env var or place firebase-key.json in repo root');
  process.exit(1);
}

const serviceAccount = JSON.parse(fs.readFileSync(firebaseKeyPath, 'utf8'));
admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });

const db = admin.firestore();
const gcs = new Storage({ projectId: serviceAccount.project_id });
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const BUCKET = process.env.MARKET_MAP_BUCKET ||
  (serviceAccount.project_id.includes('q8') ? 'molten-crowbar-498920-q8-docx' : 'di-intelligence-docx');

async function downloadImage(imagePath) {
  const bucket = gcs.bucket(BUCKET);
  const file = bucket.file(imagePath);
  const [exists] = await file.exists();
  if (!exists) return null;
  const [data] = await file.download();
  return data;
}

async function extractMapTitle(currentTitle, imageBuffer, isDoc) {
  if (isDoc) return '(PDF)';
  if (!imageBuffer) return '(no image)';

  const base64 = imageBuffer.toString('base64');
  try {
    const response = await anthropic.messages.create({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 100,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: { type: 'base64', media_type: 'image/png', data: base64 },
            },
            {
              type: 'text',
              text: `Look at this market map image. What is the title or name of the map shown? Return ONLY the map title, nothing else. If you can't see a clear title, respond with: (untitled)`,
            },
          ],
        },
      ],
    });
    return response.content[0].type === 'text' ? response.content[0].text.trim() : '(unreadable)';
  } catch (err) {
    console.error(`Error extracting title for "${currentTitle}":`, err.message);
    return '(error)';
  }
}

async function main() {
  console.error('Fetching market map entries from Firestore...');
  const snap = await db.collection('marketMapEntries').orderBy('createdAt', 'desc').get();
  const entries = snap.docs.map((doc) => {
    const d = doc.data();
    return {
      id: doc.id,
      title: d.title,
      imagePath: d.imagePath,
      imageContentType: d.imageContentType,
    };
  });

  console.error(`Found ${entries.length} entries. Extracting map titles...`);

  const results = [];
  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    const isDoc = entry.imageContentType === 'application/pdf';
    const percent = Math.round(((i + 1) / entries.length) * 100);

    process.stderr.write(`\r[${percent}%] Processing "${entry.title}"`);

    let imageBuffer = null;
    if (entry.imagePath) {
      imageBuffer = await downloadImage(entry.imagePath);
    }

    const actualTitle = await extractMapTitle(entry.title, imageBuffer, isDoc);
    results.push({ current: entry.title, actual: actualTitle });

    // Small delay to avoid rate limits
    await new Promise((r) => setTimeout(r, 100));
  }

  console.error('\n');

  // Output CSV header
  console.log('current_title,actual_title');
  // Output each row, escaping quotes in titles
  for (const result of results) {
    const current = `"${result.current.replace(/"/g, '""')}"`;
    const actual = `"${result.actual.replace(/"/g, '""')}"`;
    console.log(`${current},${actual}`);
  }

  console.error(`Done. Processed ${entries.length} entries.`);
  process.exit(0);
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
