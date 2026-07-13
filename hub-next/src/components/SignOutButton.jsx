'use client';

import { signOut } from 'next-auth/react';

export default function SignOutButton({ className, callbackUrl = '/signin' }) {
  return (
    <button type="button" className={className} onClick={() => signOut({ callbackUrl })}>
      Sign out
    </button>
  );
}
