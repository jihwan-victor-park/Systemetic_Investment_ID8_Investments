// No-op placeholder. Auth is deliberately not wired up yet — this app is
// unauthenticated until the site is built, deployed, and tested end-to-end.
// When it's time to gate this behind Google sign-in again, reuse the pattern
// from the deleted hub-next prototype (commit 2df634d): NextAuth + Google
// provider restricted to the id8investments.com Workspace domain, enforced
// server-side in the signIn callback, with this file exporting
// `{ auth as middleware }` and a matcher excluding /api/auth, static assets,
// and fonts/img.
export const config = { matcher: [] };
