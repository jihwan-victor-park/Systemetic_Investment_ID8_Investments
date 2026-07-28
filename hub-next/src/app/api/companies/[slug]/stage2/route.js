import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { getCompany } from '@/lib/companies';

async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

function backendHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.PIPELINE_INTERNAL_SECRET) headers['X-Internal-Secret'] = process.env.PIPELINE_INTERNAL_SECRET;
  return headers;
}

// "Start Stage 2" for one existing, already-Stage-1-screened company row --
// same shape as the sibling screen/route.js (Stage 1's "Run Analysis"), but
// proxies to POST /company-stage2/<slug>, which persists the resulting memo
// against this company's own doc (see firestore_push.push_company_memo_firestore)
// instead of only Research Chat's ephemeral chat-job record.
export async function POST(request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  if (!process.env.PIPELINE_BASE_URL) {
    return NextResponse.json({ error: 'PIPELINE_BASE_URL is not configured' }, { status: 500 });
  }
  const { slug } = await params;
  const company = await getCompany(slug);
  if (!company) return NextResponse.json({ error: 'company-not-found' }, { status: 404 });

  const origin = company.origin || {};
  const res = await fetch(`${process.env.PIPELINE_BASE_URL}/company-stage2/${encodeURIComponent(slug)}`, {
    method: 'POST',
    headers: backendHeaders(),
    body: JSON.stringify({
      name: company.name,
      domain: company.website || undefined,
      round: company.round || origin.round || undefined,
      hq: origin.hq || undefined,
      lead_investors: origin.leadInvestors || undefined,
    }),
  });
  const data = await res.json().catch(() => ({ error: 'invalid response from pipeline service' }));
  return NextResponse.json(data, { status: res.status });
}
