// Rubric v4 scoring math -- mirrors deal_intelligence/rubric.py's
// dimension_score()/weighted_score()/raw_score() exactly (equal-weight mean,
// 1 decimal). Deliberately framework-agnostic (no 'server-only') so both the
// PATCH API route and the client component can call it: the client uses it
// for instant optimistic feedback, the server call is what actually persists.

export function dimensionScore(subcategories) {
  const scores = (subcategories || [])
    .map((s) => s?.score)
    .filter((s) => s != null && s !== '');
  if (!scores.length) return 0;
  const mean = scores.reduce((a, b) => a + Number(b), 0) / scores.length;
  return Math.round(mean * 10) / 10;
}

export function fitScore(dimensions) {
  const scores = (dimensions || [])
    .map((d) => d?.score)
    .filter((s) => s != null && s !== '');
  if (!scores.length) return 0;
  const mean = scores.reduce((a, b) => a + Number(b), 0) / scores.length;
  return Math.round(mean * 10) / 10;
}
