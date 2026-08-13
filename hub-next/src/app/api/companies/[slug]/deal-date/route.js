import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { updateCompanyRoundDate } from '@/lib/companies';

// Same belt-and-suspenders pattern as /api/companies/[slug]/round and /stage.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

export async function PATCH(request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { slug } = await params;
  const { roundDate } = await request.json();

  try {
    const result = await updateCompanyRoundDate(slug, roundDate);
    return NextResponse.json({ ok: true, ...result });
  } catch (err) {
    const status = err.message === 'company-not-found' ? 404 : err.message === 'invalid-date' ? 400 : 500;
    return NextResponse.json({ error: err.message || 'update-failed' }, { status });
  }
}
