'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './DeleteButton.module.css';

// Shared by every "remove from the directory" action (companies, deal
// summaries, market map entries) -- confirms, sends the DELETE, then either
// refreshes the route (list pages driven by Server Component data) or calls
// back into the caller's own client state (MarketMap, which holds entries
// in useState instead of re-fetching).
export default function DeleteButton({ url, confirmMessage, onDeleted, label = '×', title = 'Delete', className }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const onClick = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (confirmMessage && !window.confirm(confirmMessage)) return;
    setBusy(true);
    try {
      const res = await fetch(url, { method: 'DELETE' });
      if (!res.ok) throw new Error('delete-failed');
      if (onDeleted) onDeleted();
      else router.refresh();
    } catch {
      window.alert('Delete failed — try again.');
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      className={className || styles.del}
      onClick={onClick}
      disabled={busy}
      title={title}
      aria-label={title}
    >
      {busy ? '…' : label}
    </button>
  );
}
