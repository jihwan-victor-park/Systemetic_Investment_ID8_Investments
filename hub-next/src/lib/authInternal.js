// Pulled out of auth.js so the gating decision is unit-testable without
// booting NextAuth/the Google provider (which needs live OAuth env vars).
// No 'server-only' import -- pure, framework-agnostic string logic.

// id8investments.com accounts are auto-approved internal users. Anyone else
// (investors) gets an investorAccess record created on first sign-in and
// stays gated to /pending until an internal user approves them from /docs/admin.
export const ALLOWED_HD = process.env.ALLOWED_HD || 'id8investments.com';

// Explicit safety-net allowlist, in case ALLOWED_HD ever drifts from the
// deployed env var or an email needs internal access outside the domain check.
export const EXPLICIT_INTERNAL_EMAILS = new Set([
  'mussadiq@id8investments.com',
  'hannah@id8investments.com',
]);

export function isInternal(email) {
  return email.endsWith('@' + ALLOWED_HD) || EXPLICIT_INTERNAL_EMAILS.has(email);
}
