import { NextResponse } from 'next/server';
import { auth } from '@/auth';

async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

function backendHeaders() {
  const headers = {};
  if (process.env.PIPELINE_INTERNAL_SECRET) headers['X-Internal-Secret'] = process.env.PIPELINE_INTERNAL_SECRET;
  return headers;
}

// Generic single-job status fetch, type-agnostic (chat, rerun, Attio import,
// backlog) -- used by RunAnalysisButton/AttioImportButton right after a POST
// succeeds, ahead of the tray's next 5s poll.
export async function GET(request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  if (!process.env.PIPELINE_BASE_URL) {
    return NextResponse.json({ error: 'PIPELINE_BASE_URL is not configured' }, { status: 500 });
  }
  const { jobId } = await params;
  const res = await fetch(`${process.env.PIPELINE_BASE_URL}/jobs/${encodeURIComponent(jobId)}`, {
    headers: backendHeaders(),
    cache: 'no-store',
  });
  const data = await res.json().catch(() => ({ error: 'invalid response from pipeline service' }));
  return NextResponse.json(data, { status: res.status });
}
