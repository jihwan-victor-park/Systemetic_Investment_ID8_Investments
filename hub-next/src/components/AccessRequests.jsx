'use client';

import { useState, useEffect } from 'react';
import styles from './AccessRequests.module.css';

export default function AccessRequests() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    fetch('/api/access-requests')
      .then((r) => r.json())
      .then((d) => setRequests(d.requests || []))
      .finally(() => setLoading(false));
  }, []);

  const decide = async (email, status) => {
    setBusy(email);
    const res = await fetch('/api/access-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, status }),
    });
    if (res.ok) {
      setRequests(requests.map((r) => (r.email === email ? { ...r, status } : r)));
    }
    setBusy(null);
  };

  if (loading) return null;
  if (requests.length === 0) return <p className={styles.empty}>No investor access requests yet.</p>;

  return (
    <div className={styles.list}>
      {requests.map((r) => (
        <div className={styles.item} key={r.email}>
          <div>
            <div className={styles.email}>{r.email}</div>
            {r.name && <div className={styles.name}>{r.name}</div>}
            <div className={styles.meta}>Requested {(r.requestedAt || '').slice(0, 10)}</div>
          </div>
          <div className={styles.actions}>
            <span className={styles.status} data-status={r.status}>{r.status}</span>
            <button
              className={styles.approve}
              disabled={busy === r.email || r.status === 'approved'}
              onClick={() => decide(r.email, 'approved')}
            >
              Approve
            </button>
            <button
              className={styles.deny}
              disabled={busy === r.email || r.status === 'denied'}
              onClick={() => decide(r.email, 'denied')}
            >
              Deny
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
