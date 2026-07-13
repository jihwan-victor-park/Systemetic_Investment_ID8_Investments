import NextAuth from 'next-auth';
import { authConfig } from './auth.config';

// Deliberately built from auth.config.js, NOT auth.js -- auth.js pulls in
// Firestore (via investorAccess.js), which isn't Edge-runtime compatible.
// This instance only ever decodes an already-issued session cookie; it never
// needs to run the sign-in/DB-touching callbacks.
export const { auth: middleware } = NextAuth(authConfig);

// Gate the whole site behind sign-in, EXCEPT: the auth endpoints themselves,
// static assets, and the public /investors marketing page (exact match only --
// /investors/research, the gated investor view, still goes through the gate).
export const config = {
  matcher: ['/((?!api/auth|investors$|_next/static|_next/image|favicon.ico|fonts|img).*)'],
};
