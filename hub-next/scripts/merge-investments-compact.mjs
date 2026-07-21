#!/usr/bin/env node
// Same purpose as merge-pitchbook-investments.mjs, but takes already-parsed
// compact JSON (from a scratch file: [{company, companyPbid, investorStatus,
// investorSince, exitType, exitDate, exitSizeUsdMillions}, ...]) instead of
// raw PitchBook markdown text -- cheaper when the investment list was small
// enough to already be sitting in context rather than needing the overflow-
// to-file path.
//
// Usage: node scripts/merge-investments-compact.mjs <slug> <path-to-json-file>
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SEED_PATH = join(__dirname, 'data', 'partner-vcs-seed.json');

const [, , slug, jsonPath] = process.argv;
if (!slug || !jsonPath) {
  console.error('Usage: node scripts/merge-investments-compact.mjs <slug> <path-to-json-file>');
  process.exit(1);
}

const items = JSON.parse(readFileSync(jsonPath, 'utf-8'));
const portfolio = items.map((it) => ({
  company: it.company,
  industry: '',
  roundInvested: '',
  latestRound: '',
  latestRoundDate: null,
  category: '',
  description: '',
  investorStatus: it.investorStatus || null,
  investorSince: it.investorSince || null,
  exitType: it.exitType || null,
  exitDate: it.exitDate || null,
  exitSizeUsdMillions: it.exitSizeUsdMillions ?? null,
  companyPbid: it.companyPbid || null,
  pitchbookUrl: it.companyPbid ? `https://my.pitchbook.com/profile/${it.companyPbid}/company/profile` : '',
  source: 'pitchbook',
}));

const firms = JSON.parse(readFileSync(SEED_PATH, 'utf-8'));
const firm = firms.find((f) => f.slug === slug);
if (!firm) {
  console.error(`No firm with slug "${slug}" in seed file.`);
  process.exit(1);
}
firm.portfolio = portfolio;
writeFileSync(SEED_PATH, JSON.stringify(firms, null, 2) + '\n');
console.log(`${slug}: merged ${portfolio.length} portfolio companies.`);
