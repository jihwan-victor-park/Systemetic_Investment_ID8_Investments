import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { createAdditionalRound } from '@/lib/companies';

// Same belt-and-suspenders pattern as /api/companies/[slug]/stage.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

export async function POST(request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { slug } = await params;
  const { round, stage } = await request.json();

  try {
    const result = await createAdditionalRound(slug, { round, stage });
    return NextResponse.json({ ok: true, ...result });
  } catch (err) {
    const status = err.message === 'company-not-found' ? 404
      : err.message === 'duplicate-round' ? 409
      : err.message === 'invalid-stage' || err.message === 'invalid-round' ? 400
      : 500;
    return NextResponse.json({ error: err.message || 'create-failed' }, { status });
  }
}
