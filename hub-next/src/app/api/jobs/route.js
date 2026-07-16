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

// Lists every currently-running screening job (chat, per-row Run Analysis,
// Attio import, the qualified-deal backlog) -- backs the global jobs tray in
// src/context/JobsContext.jsx. No per-user scoping: this app has one shared
// 'internal' role, same as every other route here.
export async function GET() {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  if (!process.env.PIPELINE_BASE_URL) {
    return NextResponse.json({ error: 'PIPELINE_BASE_URL is not configured' }, { status: 500 });
  }
  const res = await fetch(`${process.env.PIPELINE_BASE_URL}/jobs`, {
    headers: backendHeaders(),
    cache: 'no-store',
  });
  const data = await res.json().catch(() => ({ error: 'invalid response from pipeline service' }));
  return NextResponse.json(data, { status: res.status });
}
