// Mirrors deal_intelligence/fit_note.py's slugify() exactly (NOT the
// same as lib/slugify.js, which is used for prose heading anchors and
// has different rules) -- so a company created from here collides into
// the same doc id if it's later picked up by the normal intake pipeline
// instead of creating a duplicate.
export function companySlug(name) {
  return (name || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}
