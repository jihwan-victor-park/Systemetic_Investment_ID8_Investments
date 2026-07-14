import { NextResponse } from 'next/server';
import { auth } from '@/auth';

// Belt-and-suspenders: middleware's authorized() callback already restricts
// every non-/investors route to role 'internal', but this route triggers real
// paid Perplexity/Claude API calls on demand, so double-check here too rather
// than trust that alone.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

function backendHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.PIPELINE_INTERNAL_SECRET) headers['X-Internal-Secret'] = process.env.PIPELINE_INTERNAL_SECRET;
  return headers;
}

export async function POST(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  if (!process.env.PIPELINE_BASE_URL) {
    return NextResponse.json({ error: 'PIPELINE_BASE_URL is not configured' }, { status: 500 });
  }

  const body = (await request.json().catch(() => null)) || {};
  const name = (body.name || '').trim();
  const message = (body.message || '').trim();
  const stage = body.stage === 2 ? 2 : 1;
  if (!name && !message) return NextResponse.json({ error: 'name or message is required' }, { status: 400 });

  const res = await fetch(`${process.env.PIPELINE_BASE_URL}/research-chat`, {
    method: 'POST',
    headers: backendHeaders(),
    body: JSON.stringify({
      name: name || undefined,
      message: message || undefined,
      stage,
      domain: body.domain || undefined,
      round: body.round || undefined,
      lead_investors: body.leadInvestors || undefined,
      hq: body.hq || undefined,
    }),
  });
  const data = await res.json().catch(() => ({ error: 'invalid response from pipeline service' }));
  return NextResponse.json(data, { status: res.status });
}
