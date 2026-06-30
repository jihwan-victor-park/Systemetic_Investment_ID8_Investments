import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Only this Google Workspace domain may sign in. Confidential deal data, so the
// check is enforced server-side in the signIn callback (the `hd` auth param is
// only a UI hint and can be bypassed).
const ALLOWED_HD = process.env.ALLOWED_HD || "id8investments.com";

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  providers: [
    Google({
      authorization: { params: { hd: ALLOWED_HD, prompt: "select_account" } },
    }),
  ],
  callbacks: {
    // Hard gate: reject any account whose email isn't on the allowed domain.
    async signIn({ profile }) {
      const email = (profile?.email || "").toLowerCase();
      return email.endsWith("@" + ALLOWED_HD);
    },
    // Used by middleware (`export { auth as middleware }`): every matched route
    // requires a signed-in session, otherwise NextAuth redirects to sign-in.
    authorized({ auth }) {
      return !!auth?.user;
    },
  },
});
