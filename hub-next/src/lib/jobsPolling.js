// Pulled out of JobsContext.jsx so the poll-cadence decision is unit-testable
// without mounting the React context (timers/fetch/provider tree). No
// framework dependency -- pure functions over plain data.

// Polling the pipeline's /jobs endpoint costs a real Cloud Run invocation +
// Firestore read every tick, for as long as any internal user has a hub-next
// tab open -- even with nothing running. Poll fast only while a job is
// actually active; fall back to a much slower idle cadence otherwise (still
// enough to notice a job someone else started within ~20s).
export const ACTIVE_POLL_MS = 5000;
export const IDLE_POLL_MS = 20000;
// Terminal jobs (complete/error) stay visible this long after they finish so
// Oscar actually sees the result instead of it vanishing on the next poll.
export const TERMINAL_DISMISS_MS = 10000;

export function hasActiveJobs(serverJobs) {
  return (serverJobs || []).some((j) => j.status === 'running');
}

export function pollDelayMs(serverJobs) {
  return hasActiveJobs(serverJobs) ? ACTIVE_POLL_MS : IDLE_POLL_MS;
}
