// Shared round-ordering helper -- was duplicated inline in PortfolioGraph.jsx
// (its "minimum series" filter) and is now also needed by the Top 10 VC
// Deals list (Series A-or-earlier gate). No 'server-only' import: both a
// Server Component (the Top 10 page) and a Client Component (PortfolioGraph)
// need this.
export const SERIES_ORDER = { seed: 0, 'series a': 1, 'series b': 2, 'series c': 3, 'series d': 4, 'series e': 5 };

export function seriesRank(s) {
  if (!s) return null;
  const r = SERIES_ORDER[s.trim().toLowerCase()];
  return r === undefined ? null : r;
}

// "Series A or less" per Oscar's definition of how Top 10 VC deals arrive
// under a Radar Category -- a blank/unrecognized round is treated as
// included (most companies don't have a round recorded yet, and excluding
// them would hide the whole list until the backfill lands).
export function isSeriesAOrEarlier(round) {
  const r = seriesRank(round);
  return r === null || r <= SERIES_ORDER['series a'];
}
