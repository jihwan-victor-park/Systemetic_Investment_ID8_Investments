import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { createCompanyFromPortfolio } from '@/lib/companies';
import { STAGES } from '@/lib/stages';

// Same belt-and-suspenders pattern as /api/companies/[slug]/stage.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

// Promotes a partner VC's portfolio company into the real pipeline -- the
// opt-in counterpart to the automatic name-match every portfolio table row
// already shows via companyIndex. Only ever called from a portfolio row's
// own "Add..." control; never runs automatically, and never touches
// the pipeline for companies that already match by name (those get a stage
// badge instead of this control).
export async function POST(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { name, stage, sourceVCName, round } = await request.json();
  if (!name || !STAGES.includes(stage)) {
    return NextResponse.json({ error: 'invalid-request' }, { status: 400 });
  }
  try {
    const result = await createCompanyFromPortfolio({ name, stage, sourceVCName, round });
    return NextResponse.json({ ok: true, ...result });
  } catch (err) {
    const status = err.message === 'already-exists' ? 409
      : err.message === 'invalid-stage' || err.message === 'invalid-name' || err.message === 'invalid-round' ? 400
      : 500;
    return NextResponse.json({ error: err.message || 'create-failed' }, { status });
  }
}
