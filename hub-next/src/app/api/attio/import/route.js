import { NextResponse } from 'next/server';
import { auth } from '@/auth';

async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

function backendHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.PIPELINE_INTERNAL_SECRET) headers['X-Internal-Secret'] = process.env.PIPELINE_INTERNAL_SECRET;
  return headers;
}

// Kicks off the pipeline's bulk Attio deal pull (POST /import-attio-deals) --
// same proxy shape as /api/research-chat, just no request body.
export async function POST() {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  if (!process.env.PIPELINE_BASE_URL) {
    return NextResponse.json({ error: 'PIPELINE_BASE_URL is not configured' }, { status: 500 });
  }
  const res = await fetch(`${process.env.PIPELINE_BASE_URL}/import-attio-deals`, {
    method: 'POST',
    headers: backendHeaders(),
  });
  const data = await res.json().catch(() => ({ error: 'invalid response from pipeline service' }));
  return NextResponse.json(data, { status: res.status });
}
