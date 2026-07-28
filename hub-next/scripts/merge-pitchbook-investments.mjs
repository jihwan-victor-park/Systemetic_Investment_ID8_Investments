#!/usr/bin/env node
// Parses pitchbook_get_investor_investments' raw markdown-ish text output
// into portfolio entries and merges them into one VC's `portfolio` array in
// partner-vcs-seed.json. Used per-VC, batch by batch, while pulling real
// PitchBook data for the 66 firms that were only registered as fund
// identities (no companies) in the CSV import pass.
//
// This is company-name/date/status/exit-info only -- NOT the richer
// per-company description/category/vertical enrichment the original 10
// firms have (that needs a separate pitchbook_get_profile call per company,
// deliberately deferred -- "without researching each company individually
// yet", per Oscar).
//
// Dedup: PitchBook's investment-list text repeats every exited deal twice
// (once as the "## Investment:" entry with investor_status/investor_since,
// once as a bare "## Investment:" + "Deal ID" entry with only exit info) --
// keep the first (fuller) occurrence per company name, never both.
//
// Usage: node scripts/merge-pitchbook-investments.mjs <slug> <path-to-raw-text-file>
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SEED_PATH = join(__dirname, 'data', 'partner-vcs-seed.json');

const [, , slug, rawPath] = process.argv;
if (!slug || !rawPath) {
  console.error('Usage: node scripts/merge-pitchbook-investments.mjs <slug> <path-to-raw-text-file>');
  process.exit(1);
}

const raw = readFileSync(rawPath, 'utf-8');
const blocks = raw.split(/^## Investment: /m).slice(1);

const byCompany = new Map();
for (const block of blocks) {
  const get = (label) => {
    const m = block.match(new RegExp(`\\*\\*${label}\\*\\*:\\s*(.+)`));
    return m ? m[1].trim() : null;
  };
  const name = get('Company Name') || block.split('\n')[0].trim();
  const hasDealId = /\*\*Deal ID\*\*/.test(block);
  const entry = {
    company: name,
    industry: '',
    roundInvested: '',
    latestRound: '',
    latestRoundDate: null,
    category: '',
    description: '',
    investorStatus: get('Investor Status'),
    investorSince: get('Investor Since'),
    exitType: get('Exit Type'),
    exitDate: get('Exit Date'),
    exitSizeUsdMillions: get('Exit Size') ? Number(get('Exit Size')) : null,
    companyPbid: get('Company ID'),
    pitchbookUrl: (block.match(/\[https:\/\/my\.pitchbook\.com[^\]]+\]/) || [''])[0].replace(/[[\]]/g, ''),
    source: 'pitchbook',
  };
  // Prefer the fuller (non-Deal-ID) occurrence; only take the Deal-ID
  // duplicate if we haven't seen this company any other way yet.
  if (!byCompany.has(name) || (byCompany.get(name).__hasDealId && !hasDealId)) {
    entry.__hasDealId = hasDealId;
    byCompany.set(name, entry);
  }
}

const portfolio = [...byCompany.values()].map(({ __hasDealId, ...rest }) => rest);

const firms = JSON.parse(readFileSync(SEED_PATH, 'utf-8'));
const firm = firms.find((f) => f.slug === slug);
if (!firm) {
  console.error(`No firm with slug "${slug}" in seed file.`);
  process.exit(1);
}
firm.portfolio = portfolio;
writeFileSync(SEED_PATH, JSON.stringify(firms, null, 2) + '\n');
console.log(`${slug}: merged ${portfolio.length} unique portfolio companies.`);
