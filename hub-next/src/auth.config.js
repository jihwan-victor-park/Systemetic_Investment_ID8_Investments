// Edge-safe half of the NextAuth config. No Firestore/DB imports here — this
// is the config middleware.js uses to decode the already-issued session cookie
// on the Edge runtime, which can't load @google-cloud/firestore. The full
// config (providers, Firestore-backed signIn/jwt callbacks) lives in auth.js
// and only ever runs in the Node.js runtime (the /api/auth route handler).
export const authConfig = {
  pages: {
    signIn: '/signin',
  },
  providers: [],
  callbacks: {
    // Copies the role stamped onto the token (by auth.js's jwt callback, at
    // sign-in time) onto session.user — NextAuth doesn't do this by default
    // for custom token fields. No DB access, so safe to share with Edge.
    session({ session, token }) {
      if (token?.role) session.user.role = token.role;
      return session;
    },
    // Gate every matched route. `auth` here is the decoded session (already
    // has .role from the session callback above).
    authorized({ auth, request }) {
      const { pathname, origin } = request.nextUrl;
      if (pathname === '/pending' || pathname === '/denied') return true;
      if (!auth?.user) return false; // no session -> redirect to pages.signIn

      if (auth.user.role === 'internal') return true;

      if (auth.user.role === 'investor') {
        if (pathname.startsWith('/investors/research') || pathname.startsWith('/investors/materials')) return true;
        return Response.redirect(new URL('/investors/research', origin));
      }

      // Signed in, but not yet approved (role === 'pending' or unset).
      return Response.redirect(new URL('/pending', origin));
    },
  },
};
