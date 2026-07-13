'use client';

import { Suspense } from 'react';
import { signIn } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import styles from './page.module.css';

const ERROR_MESSAGES = {
  AccessDenied: 'Only id8investments.com Google accounts can access this hub.',
  Configuration: 'Sign-in is misconfigured — check the server auth setup.',
  Verification: 'That sign-in link is no longer valid.',
};

function SignInCard() {
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get('callbackUrl') || '/';
  const error = searchParams.get('error');

  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <img src="/img/logo_charcoal.png" alt="ID8 Investments" className={styles.logo} />
        <div className={styles.kicker}>ID8 Investments&nbsp;&nbsp;|&nbsp;&nbsp;Applied AI</div>
        <h1 className={styles.headline}>Sign in to<br /><em>continue.</em></h1>
        {error && (
          <div className={styles.error}>{ERROR_MESSAGES[error] || 'Something went wrong signing you in.'}</div>
        )}
        <button
          type="button"
          className={styles.button}
          onClick={() => signIn('google', { callbackUrl })}
        >
          Sign in with Google
        </button>
      </div>
    </main>
  );
}

export default function SignIn() {
  return (
    <Suspense fallback={null}>
      <SignInCard />
    </Suspense>
  );
}
