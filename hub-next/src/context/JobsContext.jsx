'use client';

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { TERMINAL_DISMISS_MS, pollDelayMs } from '@/lib/jobsPolling';

const JobsContext = createContext(null);

// Global "what's currently screening" registry, polling the pipeline's
// generic /jobs endpoint (see pipeline/app.py's _list_active_jobs) so the
// tray survives client-side navigation and shows jobs started from anywhere
// in the app -- Research Chat, a per-row Run Analysis, or the Attio import
// button. No per-user scoping: every internal user sees every running job,
// same shared-role model as the rest of this app.
export function JobsProvider({ enabled, children }) {
  const [jobs, setJobs] = useState({}); // job_id -> job
  const timersRef = useRef({}); // job_id -> setTimeout handle, for terminal auto-dismiss

  const clearDismissTimer = useCallback((jobId) => {
    if (timersRef.current[jobId]) {
      clearTimeout(timersRef.current[jobId]);
      delete timersRef.current[jobId];
    }
  }, []);

  const scheduleDismiss = useCallback((jobId) => {
    if (timersRef.current[jobId]) return;
    timersRef.current[jobId] = setTimeout(() => {
      setJobs((prev) => {
        const next = { ...prev };
        delete next[jobId];
        return next;
      });
      delete timersRef.current[jobId];
    }, TERMINAL_DISMISS_MS);
  }, []);

  // Optimistic add, called right after a POST succeeds -- covers the gap
  // before the next server poll would otherwise pick the job up.
  const startJob = useCallback((jobId, job) => {
    clearDismissTimer(jobId);
    setJobs((prev) => ({ ...prev, [jobId]: { ...job, job_id: jobId, status: job.status || 'running' } }));
  }, [clearDismissTimer]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer = null;
    let nextDelay = pollDelayMs([]);

    async function poll() {
      try {
        const res = await fetch('/api/jobs', { cache: 'no-store' });
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        const serverJobs = data.jobs || [];
        nextDelay = pollDelayMs(serverJobs);
        setJobs((prev) => {
          const next = { ...prev };
          const serverIds = new Set();
          for (const j of serverJobs) {
            serverIds.add(j.job_id);
            next[j.job_id] = j;
            clearDismissTimer(j.job_id);
          }
          // A job we know about that the server no longer lists as running
          // either just finished (we'll get its terminal state from the
          // button's own poll / startJob call) or was flagged stale server-side
          // (see pipeline's _list_active_jobs) -- mark it failed rather than
          // leaving the label reading "Running…" for its last few seconds
          // before scheduleDismiss clears it.
          for (const id of Object.keys(prev)) {
            if (!serverIds.has(id) && prev[id].status === 'running') {
              next[id] = { ...prev[id], status: 'error', error: prev[id].error || 'stopped responding' };
              scheduleDismiss(id);
            }
          }
          return next;
        });
      } catch {
        // transient network/poll error -- next tick retries, nothing to show
      }
    }

    async function tick() {
      await poll();
      if (cancelled) return;
      timer = setTimeout(tick, nextDelay);
    }

    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [enabled, clearDismissTimer, scheduleDismiss]);

  // A job that flips to complete/error (reported via startJob from a
  // button's own poll) should still show briefly, then clear itself.
  const reportTerminal = useCallback((jobId, job) => {
    clearDismissTimer(jobId);
    setJobs((prev) => ({ ...prev, [jobId]: { ...prev[jobId], ...job, job_id: jobId } }));
    scheduleDismiss(jobId);
  }, [clearDismissTimer, scheduleDismiss]);

  return (
    <JobsContext.Provider value={{ jobs, startJob, reportTerminal, enabled }}>
      {children}
    </JobsContext.Provider>
  );
}

export function useJobs() {
  const ctx = useContext(JobsContext);
  if (!ctx) throw new Error('useJobs must be used within a JobsProvider');
  return ctx;
}
