#!/usr/bin/env node
// Adds attioId + contactEmails to the existing partner-vcs-seed.json entries
// (registered by parse-partner-vcs-csv.mjs) from a second Attio export that
// carries the "Record ID" (the Attio company record's real UUID) and each
// firm's "Team > Email addresses" -- neither of which the original export
// included. Deliberately does NOT touch `contact`, `trackedBy`, or anything
// else: several `contact` values already carry manual edits/curation not
// present in either CSV (see hub-next's ContactChip redesign) and must
// survive re-running this.
//
// `contact` and `contactEmails` are two independently-ordered multi-value
// Attio fields -- matching a given name to *its* email is done at render
// time (src/lib/contactMatch.js), not here.
//
// One real wrinkle: two distinct Attio company records share the display
// name "Manhattan Venture Partners" (mvp.vc and manhattanventurepartners.com)
// but the seed only ever registered one doc for it (see parse-partner-vcs-
// csv.mjs's own comment on this) -- its `contact` already merges people from
// both. Both CSV rows resolve to that one seed doc here; their email lists
// are concatenated so every merged contact still gets a shot at a match,
// and the attioId is taken from whichever row's domain matches the seed's
// stored `website` (the one already treated as canonical).
//
// Usage: node scripts/parse-partner-vc-contacts-csv.mjs
// Writes scripts/data/partner-vcs-seed.json in place.
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CSV_PATH = join(__dirname, 'data', 'id8-partner-vc-contacts.csv');
const SEED_PATH = join(__dirname, 'data', 'partner-vcs-seed.json');

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; } else { inQuotes = false; }
      } else {
        field += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ',') {
      row.push(field);
      field = '';
    } else if (c === '\r') {
      // ignore
    } else if (c === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else {
      field += c;
    }
  }
  if (field.length || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.length > 1 || r[0] !== '');
}

function normalize(name) {
  return (name || '').trim().toLowerCase();
}

function normalizeDomain(website) {
  return (website || '').trim().toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/$/, '');
}

const csvText = readFileSync(CSV_PATH, 'utf-8');
const rows = parseCsv(csvText);
const header = rows[0];
const idx = (label) => header.indexOf(label);
const iName = idx('Record');
const iRecordId = idx('Parent Record > Record ID');
const iEmails = idx('Parent Record > Team > Email addresses');
const iDomains = idx('Parent Record > Domains');

const csvRows = rows.slice(1)
  .filter((r) => (r[iName] || '').trim())
  .map((r) => ({
    name: (r[iName] || '').trim(),
    recordId: (r[iRecordId] || '').trim(),
    emails: (r[iEmails] || '').trim(),
    domain: normalizeDomain((r[iDomains] || '').split(',')[0]),
  }));

const seed = JSON.parse(readFileSync(SEED_PATH, 'utf-8'));
const seedByDomain = new Map(seed.filter((f) => normalizeDomain(f.website)).map((f) => [normalizeDomain(f.website), f]));
const seedByName = new Map(seed.map((f) => [normalize(f.name), f]));

const matchedRowsByFirm = new Map(); // seed entry -> csv rows matched to it
const unmatched = [];
for (const row of csvRows) {
  const firm = seedByDomain.get(row.domain) || seedByName.get(normalize(row.name));
  if (!firm) { unmatched.push(row.name); continue; }
  if (!matchedRowsByFirm.has(firm)) matchedRowsByFirm.set(firm, []);
  matchedRowsByFirm.get(firm).push(row);
}

if (unmatched.length) {
  console.warn(`⚠ ${unmatched.length} CSV row(s) matched no existing seed firm (not touched): ${unmatched.join(', ')}`);
}

let updated = 0;
for (const [firm, csvMatches] of matchedRowsByFirm) {
  // Prefer the row whose domain matches this firm's own stored website for
  // attioId -- see the Manhattan Venture Partners note above for why there
  // can be more than one candidate row.
  const canonical = csvMatches.find((r) => r.domain && r.domain === normalizeDomain(firm.website)) || csvMatches[0];
  firm.attioId = canonical.recordId;
  firm.contactEmails = csvMatches.map((r) => r.emails).filter(Boolean).join(',');
  updated++;
}

writeFileSync(SEED_PATH, JSON.stringify(seed, null, 2) + '\n');
console.log(`Matched ${matchedRowsByFirm.size} firm(s) from ${csvRows.length} CSV rows, updated ${updated} seed entries with attioId + contactEmails.`);
