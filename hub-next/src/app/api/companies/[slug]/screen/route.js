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

// "Run Analysis" for one existing company row -- reads the company's own
// stored name/website/origin (round/hq/leadInvestors, when it came in via
// Attio) to build a richer request body, then proxies to the pipeline's
// POST /screen-company/<slug>, which pins this exact slug rather than
// recomputing one from the deal (see that endpoint's docstring for why).
export async function POST(request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  if (!process.env.PIPELINE_BASE_URL) {
    return NextResponse.json({ error: 'PIPELINE_BASE_URL is not configured' }, { status: 500 });
  }
  const { slug } = await params;
  const company = await getCompany(slug);
  if (!company) return NextResponse.json({ error: 'company-not-found' }, { status: 404 });

  const origin = company.origin || {};
  const res = await fetch(`${process.env.PIPELINE_BASE_URL}/screen-company/${encodeURIComponent(slug)}`, {
    method: 'POST',
    headers: backendHeaders(),
    body: JSON.stringify({
      name: company.name,
      domain: company.website || undefined,
      round: origin.round || undefined,
      hq: origin.hq || undefined,
      lead_investors: origin.leadInvestors || undefined,
    }),
  });
  const data = await res.json().catch(() => ({ error: 'invalid response from pipeline service' }));
  return NextResponse.json(data, { status: res.status });
}
