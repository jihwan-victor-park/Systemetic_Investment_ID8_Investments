import NextAuth from 'next-auth';
import Google from 'next-auth/providers/google';
import { authConfig } from './auth.config';
import { getOrCreateAccessRecord } from './lib/investorAccess';

// id8investments.com accounts are auto-approved internal users. Anyone else
// (investors) gets an investorAccess record created on first sign-in and
// stays gated to /pending until an internal user approves them from /docs/admin.
const ALLOWED_HD = process.env.ALLOWED_HD || 'id8investments.com';

function isInternal(email) {
  return email.endsWith('@' + ALLOWED_HD);
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  trustHost: true,
  providers: [
    // No `hd` restriction here on purpose -- investors sign in with any
    // Google account. Domain/approval enforcement happens below, server-side.
    Google({ authorization: { params: { prompt: 'select_account' } } }),
  ],
  callbacks: {
    ...authConfig.callbacks,
    // Runs on every OAuth callback. Returning a path string redirects there
    // instead of proceeding to a session -- used to bounce brand-new/pending
    // investors to /pending and denied ones to /denied, without ever letting
    // them reach gated content.
    async signIn({ profile }) {
      const email = (profile?.email || '').toLowerCase();
      if (!email) return false;
      if (isInternal(email)) return true;

      const record = await getOrCreateAccessRecord(email, profile?.name);
      if (record.status === 'approved') return true;
      if (record.status === 'denied') return '/denied';
      return '/pending';
    },
    // Only runs the Firestore lookup on the initial sign-in (`user` is only
    // populated then); every later request just carries the token forward,
    // so approval changes take effect the next time someone signs back in.
    async jwt({ token, user, profile }) {
      if (user) {
        const email = (profile?.email || user.email || '').toLowerCase();
        if (isInternal(email)) {
          token.role = 'internal';
        } else {
          const record = await getOrCreateAccessRecord(email, profile?.name);
          token.role = record.status === 'approved' ? 'investor' : 'pending';
        }
      }
      return token;
    },
  },
});
