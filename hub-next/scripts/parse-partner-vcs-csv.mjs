#!/usr/bin/env node
// Phase 1 of the 76-firm Partner VC migration: registers every firm from
// Oscar's real Attio "ID8 Partner VCs" export as a real partnerVCs entry --
// name, trackedBy, contact, website, fund-level description, and the Attio
// "Categories" tag. Deliberately does NOT touch portfolio[] for the 10 firms
// that already have real PitchBook-enriched portfolios (matched by
// normalized name) -- this step is registering fund identities, not pulling
// portfolio companies (that's its own per-VC pass, phase 2).
//
// The CSV has quoted fields containing embedded commas and, in at least one
// row (HUMANS), an embedded newline -- a naive split(',')/split('\n') would
// silently corrupt those rows, so this is a real (if minimal) RFC4180-style
// parser, not string splitting.
//
// Usage: node scripts/parse-partner-vcs-csv.mjs
// Writes scripts/data/partner-vcs-seed.json in place.
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CSV_PATH = join(__dirname, 'data', 'id8-partner-vcs.csv');
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
      // ignore -- \n (possibly preceded by this) is the real row separator
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

function companySlug(name) {
  return (name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

function normalize(name) {
  return (name || '').trim().toLowerCase();
}

// Domain is a far more reliable match key than display name -- Attio's
// "DataPower" and the already-enriched seed's "DataPower Capital" are the
// same real fund (both datapower.vc), a mismatch a name-only match would
// have silently treated as two separate firms, duplicating the one that
// already has 43 real PitchBook-enriched companies.
function normalizeDomain(website) {
  return (website || '').trim().toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/$/, '');
}

const csvText = readFileSync(CSV_PATH, 'utf-8');
const rows = parseCsv(csvText);
const header = rows[0];
const idx = (label) => header.indexOf(label);
const iName = idx('Record');
const iDescription = idx('Parent Record > Description');
const iStrength = idx('Parent Record > Connection strength');
const iTeam = idx('Parent Record > Team > Name');
const iTrackedBy = idx('Parent Record > Strongest connection');
const iCategories = idx('Parent Record > Categories');
const iDomains = idx('Parent Record > Domains');

const csvFirms = rows.slice(1)
  .filter((r) => (r[iName] || '').trim())
  .map((r) => ({
    name: r[iName].trim(),
    description: (r[iDescription] || '').trim() || null,
    connectionStrength: (r[iStrength] || '').trim() || null,
    contact: (r[iTeam] || '').trim(),
    trackedBy: (r[iTrackedBy] || '').trim(),
    attioCategories: (r[iCategories] || '').trim() || null,
    website: (r[iDomains] || '').split(',')[0].trim(),
  }));

// Two Attio records share the exact display name "Manhattan Venture
// Partners" but have different domains (mvp.vc vs.
// manhattanventurepartners.com) -- could be two genuinely different firms
// with an unfortunate name collision, or an Attio data-entry duplicate.
// Disambiguating by domain in the slug avoids silently dropping one of them
// (a bare name-based slug would collide and the second write would
// overwrite the first) -- but this needs a human look, not a silent merge.
const nameCounts = {};
for (const f of csvFirms) nameCounts[normalize(f.name)] = (nameCounts[normalize(f.name)] || 0) + 1;
const duplicateNames = Object.entries(nameCounts).filter(([, n]) => n > 1).map(([n]) => n);
if (duplicateNames.length) {
  console.warn(`\n⚠ ${duplicateNames.length} name(s) appear more than once in the CSV -- disambiguated by domain, but worth a manual look:`);
  for (const f of csvFirms) {
    if (duplicateNames.includes(normalize(f.name))) console.warn(`  - "${f.name}" (${f.website})`);
  }
  console.warn('');
}

const existing = JSON.parse(readFileSync(SEED_PATH, 'utf-8'));
const existingByName = new Map(existing.map((f) => [normalize(f.name), f]));
const existingByDomain = new Map(
  existing.filter((f) => normalizeDomain(f.website)).map((f) => [normalizeDomain(f.website), f]),
);

let added = 0, matched = 0;
const matchedExisting = new Set();
const merged = csvFirms.map((firm) => {
  // Domain match first (see normalizeDomain's comment) -- name match only as
  // a fallback for firms with no domain on one side or the other.
  const already = existingByDomain.get(normalizeDomain(firm.website)) || existingByName.get(normalize(firm.name));
  if (already) {
    matchedExisting.add(already);
    matched++;
    return {
      ...already,
      description: firm.description,
      connectionStrength: firm.connectionStrength,
      attioCategories: firm.attioCategories,
      contact: already.contact || firm.contact,
      trackedBy: already.trackedBy || firm.trackedBy,
      website: already.website || firm.website,
    };
  }
  added++;
  const isDup = duplicateNames.includes(normalize(firm.name));
  const slugBase = companySlug(firm.name);
  const slug = isDup ? `partner-${slugBase}-${companySlug(firm.website || 'unknown')}` : `partner-${slugBase}`;
  return {
    slug,
    name: firm.name,
    trackedBy: firm.trackedBy,
    contact: firm.contact,
    sector: '',
    website: firm.website,
    note: '',
    description: firm.description,
    connectionStrength: firm.connectionStrength,
    attioCategories: firm.attioCategories,
    portfolio: [],
    news: [],
  };
});

// Any existing (already-real, portfolio-enriched) firm not present in this
// CSV export is kept as-is rather than dropped -- the CSV is the source of
// truth for fund identity/metadata, not for whether a firm stays tracked.
// Checked by object identity (matchedExisting), not by re-comparing names --
// that's exactly the check that missed "DataPower" / "DataPower Capital"
// being the same fund in the first place.
for (const f of existing) {
  if (!matchedExisting.has(f)) merged.push(f);
}

writeFileSync(SEED_PATH, JSON.stringify(merged, null, 2) + '\n');
console.log(`Parsed ${csvFirms.length} firms from CSV -- ${matched} matched existing (portfolio preserved), ${added} newly registered.`);
console.log(`Total firms in seed file now: ${merged.length}`);
