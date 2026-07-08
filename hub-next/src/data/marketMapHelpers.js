// Pure helpers ported from hub/src/data/marketMapData.js. The MARKET_MAPS
// array itself is gone — entries now live in Firestore (marketMapEntries) —
// but everything derived from a list of entries stays exactly as it was,
// just parameterized to take that list as an argument instead of a module-
// level constant.

export const CAT_CODE = {
  'AI Agents': 'AG', 'Cross-Industry Apps': 'XA', 'AI Compute & Data Centers': 'CP', 'AI Infrastructure': 'AI',
  'Content Generation': 'CG', 'Cybersecurity': 'CY', 'Defense Tech': 'DF', 'Developer Tools': 'DV',
  'Energy AI': 'EN', 'Fintech': 'FT', 'Healthcare': 'HC',
  'Legal': 'LG', 'Robotics & Physical AI': 'RB', 'Semiconductors & Photonics': 'SP', 'Voice AI': 'VO',
};

export const CATEGORIES = Object.keys(CAT_CODE);

function ymNow() {
  const d = new Date();
  return d.getFullYear() * 100 + (d.getMonth() + 1);
}

// Months between a published ym and a reference ym (defaults to the real current month) —
// checked against the clock every call, so "fresh" keeps rolling forward instead of going
// stale itself once the hardcoded cutoffs are in the past.
function monthsAgo(ym, ref) {
  const y1 = Math.floor(ym / 100), m1 = ym % 100;
  const y2 = Math.floor(ref / 100), m2 = ref % 100;
  return (y2 - y1) * 12 + (m2 - m1);
}

export function freshness(ym, ref = ymNow()) {
  if (ym == null) return 'undated';
  const age = monthsAgo(ym, ref);
  if (age <= 6) return 'fresh';
  if (age <= 12) return 'aging';
  return 'stale';
}

export function firmCode(f) {
  const p = f.split(/\s+/);
  return p.length === 1 ? f.slice(0, 2).toUpperCase() : (p[0][0] + p[1][0]).toUpperCase();
}

export function domainOf(u) {
  try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; }
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Turns a "2026-07" <input type="month"> value into the { ym, date } pair the data rows use.
export function ymFromMonthInput(value) {
  const [y, m] = value.split('-').map(Number);
  return { ym: y * 100 + m, date: `${MONTHS[m - 1]} ${y}` };
}

export function firmsList(entries) {
  return [...new Set(entries.map((m) => m.firm))].sort((a, b) => a.localeCompare(b));
}

// If this domain already appears in the directory, suggest the firm that published it.
export function firmForDomain(entries, url) {
  const domain = domainOf(url);
  if (!domain) return '';
  const hit = entries.find((m) => domainOf(m.url) === domain);
  return hit ? hit.firm : '';
}
