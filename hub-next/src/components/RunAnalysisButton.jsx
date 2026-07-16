'use client';

import { useState } from 'react';
import { useJobs } from '@/context/JobsContext';
import styles from './RunAnalysisButton.module.css';

// Kicks off Stage 1 screening for one specific company row -- posts, hands
// the returned job off to the shared jobs tray (src/context/JobsContext.jsx)
// for progress, and flips back to idle. No local polling here; the tray
// (and, if this page is Research Chat, that component's own poll) owns
// tracking the job to completion.
export default function RunAnalysisButton({ slug, name }) {
  const { startJob } = useJobs();
  const [busy, setBusy] = useState(false);
  const [justStarted, setJustStarted] = useState(false);

  const onClick = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setBusy(true);
    try {
      const res = await fetch(`/api/companies/${encodeURIComponent(slug)}/screen`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) throw new Error(data.error || 'run-analysis-failed');
      startJob(data.job_id, {
        status: 'running', type: 'stage1_rerun', companySlug: slug,
        label: `${name} — Run Analysis`, createdAt: new Date().toISOString(),
      });
      setJustStarted(true);
      setTimeout(() => setJustStarted(false), 4000);
    } catch {
      window.alert('Could not start analysis — try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <button type="button" className={styles.btn} onClick={onClick} disabled={busy} title="Run Stage 1 analysis">
      {busy ? 'Starting…' : justStarted ? 'Started ✓' : 'Run Analysis'}
    </button>
  );
}
