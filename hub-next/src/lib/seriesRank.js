// Shared round-ordering helper for PortfolioGraph's "minimum series" filter.
// No 'server-only' import: PortfolioGraph is a Client Component.
export const SERIES_ORDER = { seed: 0, 'series a': 1, 'series b': 2, 'series c': 3, 'series d': 4, 'series e': 5 };

export function seriesRank(s) {
  if (!s) return null;
  const r = SERIES_ORDER[s.trim().toLowerCase()];
  return r === undefined ? null : r;
}
