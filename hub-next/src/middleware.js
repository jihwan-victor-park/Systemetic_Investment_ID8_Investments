import NextAuth from 'next-auth';
import { authConfig } from './auth.config';

// Deliberately built from auth.config.js, NOT auth.js -- auth.js pulls in
// Firestore (via investorAccess.js), which isn't Edge-runtime compatible.
// This instance only ever decodes an already-issued session cookie; it never
// needs to run the sign-in/DB-touching callbacks.
export const { auth: middleware } = NextAuth(authConfig);

// Gate the whole site behind sign-in, EXCEPT: the auth endpoints themselves,
// static assets, the public /investors marketing page (exact match only --
// /investors/research, the gated investor view, still goes through the gate),
// the Growth Opportunities Fund I overview (a public LP-facing page; the
// navbar hides its own link to it for signed-out visitors, see Navbar.jsx),
// and api/admin-market-map -- that route has no browser session to check
// (called server-to-server) and enforces its own shared-secret header instead,
// see app/api/admin-market-map/[id]/route.js.
export const config = {
  matcher: [
    '/((?!api/auth|api/admin-market-map|investors$|investors/materials/fund-overview(?:/|$)|_next/static|_next/image|favicon.ico|fonts|img).*)',
  ],
};
