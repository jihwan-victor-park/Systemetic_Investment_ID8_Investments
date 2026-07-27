import { describe, expect, it } from 'vitest';
import { ACTIVE_POLL_MS, IDLE_POLL_MS, hasActiveJobs, pollDelayMs } from './jobsPolling';

describe('hasActiveJobs', () => {
  it('is true when any job is running', () => {
    expect(hasActiveJobs([{ status: 'complete' }, { status: 'running' }])).toBe(true);
  });

  it('is false when no job is running', () => {
    expect(hasActiveJobs([{ status: 'complete' }, { status: 'error' }])).toBe(false);
  });

  it('is false for an empty or missing job list', () => {
    expect(hasActiveJobs([])).toBe(false);
    expect(hasActiveJobs(undefined)).toBe(false);
  });
});

describe('pollDelayMs', () => {
  it('polls fast while a job is active', () => {
    expect(pollDelayMs([{ status: 'running' }])).toBe(ACTIVE_POLL_MS);
  });

  it('falls back to the slow idle cadence otherwise', () => {
    expect(pollDelayMs([])).toBe(IDLE_POLL_MS);
    expect(pollDelayMs([{ status: 'complete' }])).toBe(IDLE_POLL_MS);
  });

  it('active cadence is faster than idle -- the whole point of the backoff', () => {
    expect(ACTIVE_POLL_MS).toBeLessThan(IDLE_POLL_MS);
  });
});
