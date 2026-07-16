'use client';

import { useState } from 'react';
import { useJobs } from '@/context/JobsContext';
import styles from './TopVCsAdmin.module.css';

// Triggers the pipeline's bulk Attio deal pull (every deal, any stage) --
// results land as stage='new' company stubs for Oscar to triage on the New
// Deals tab. Progress (processed/total) shows in the global jobs tray, not
// here; this button just fires the job and hands it off.
export default function AttioImportButton() {
  const { startJob } = useJobs();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);

  const onClick = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const res = await fetch('/api/attio/import', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) throw new Error(data.error || 'import-failed');
      startJob(data.job_id, {
        status: 'running', type: 'attio_import', label: 'Attio import',
        createdAt: new Date().toISOString(), processed: 0, total: 0,
      });
      setMessage('Import started — check the tray for progress.');
    } catch (err) {
      setMessage(`Could not start import: ${err.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <button className={styles.add} type="button" onClick={onClick} disabled={busy}>
        {busy ? 'Starting…' : 'Pull all deals from Attio'}
      </button>
      {message && <div className={styles.itemNote} style={{ marginTop: 8 }}>{message}</div>}
    </div>
  );
}
