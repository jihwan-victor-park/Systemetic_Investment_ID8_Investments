'use client';

import { useEffect, useState } from 'react';
import { useJobs } from '@/context/JobsContext';
import styles from './JobsTray.module.css';

function elapsed(createdAt) {
  if (!createdAt) return null;
  const ms = Date.now() - new Date(createdAt).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

// Stage 1 scoring (chat, Run Analysis) is one opaque blocking Perplexity
// call with no sub-step signal -- there's nothing to compute a real
// percentage from, so those show elapsed time instead. The Attio bulk
// import is a genuine batch loop (processed/total counters, see
// pipeline/app.py's _run_attio_import) and gets a real progress bar.
function JobRow({ job }) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (job.status !== 'running') return;
    const t = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [job.status]);

  const hasProgress = job.status === 'running' && typeof job.total === 'number' && job.total > 0;
  const pct = hasProgress ? Math.round((100 * (job.processed || 0)) / job.total) : null;

  return (
    <div className={styles.row}>
      <span className={`${styles.dot} ${styles[job.status] || ''}`} />
      <div className={styles.body}>
        <div className={styles.label}>{job.label || job.job_id}</div>
        {job.status === 'running' && (
          <div className={styles.meta}>
            {hasProgress ? `${job.processed}/${job.total} · ${pct}%` : elapsed(job.createdAt) ? `Running · ${elapsed(job.createdAt)}` : 'Running…'}
          </div>
        )}
        {job.status === 'complete' && <div className={styles.meta}>Done{job.verdict ? ` · ${job.verdict}` : ''}</div>}
        {job.status === 'error' && <div className={styles.metaError}>Failed{job.error ? ` · ${job.error}` : ''}</div>}
        {hasProgress && (
          <div className={styles.bar}><div className={styles.barFill} style={{ width: `${pct}%` }} /></div>
        )}
      </div>
    </div>
  );
}

export default function JobsTray() {
  const { jobs, enabled } = useJobs();
  const list = Object.values(jobs).sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''));
  if (!enabled || list.length === 0) return null;

  return (
    <div className={styles.tray}>
      {list.map((job) => <JobRow key={job.job_id} job={job} />)}
    </div>
  );
}
