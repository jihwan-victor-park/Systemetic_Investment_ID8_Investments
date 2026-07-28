'use client';

import { useState } from 'react';
import { useJobs } from '@/context/JobsContext';
import styles from './RunAnalysisButton.module.css';

// Table-row equivalent of RunAnalysisButton, but for Stage 2 (deep research
// memo) -- shown once a company already has a Stage 1 screen, in place of
// "Run Analysis" (see companyStageColumns.jsx/CompanyDetailPage.jsx's
// `hasScreen` check). Same fire-and-forget pattern: POST, hand the job to
// the shared tray, done -- the tray's own polling (not this component)
// tracks it to completion. The resulting memo is persisted against this
// company's own doc (pipeline/app.py's _run_company_stage2), so it shows up
// under "Deep research" on this same page once the job completes.
export default function StartStage2Button({ slug, name }) {
  const { startJob } = useJobs();
  const [busy, setBusy] = useState(false);
  const [justStarted, setJustStarted] = useState(false);

  const onClick = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setBusy(true);
    try {
      const res = await fetch(`/api/companies/${encodeURIComponent(slug)}/stage2`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) throw new Error(data.error || 'stage2-failed');
      startJob(data.job_id, {
        status: 'running', type: 'stage2', companySlug: slug,
        label: `${name} — Stage 2`, createdAt: new Date().toISOString(),
      });
      setJustStarted(true);
      setTimeout(() => setJustStarted(false), 4000);
    } catch {
      window.alert('Could not start Stage 2 — try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <button type="button" className={styles.btn} onClick={onClick} disabled={busy} title="Start Stage 2 deep research">
      {busy ? 'Starting…' : justStarted ? 'Started ✓' : 'Start Stage 2'}
    </button>
  );
}
