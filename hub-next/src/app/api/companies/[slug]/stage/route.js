import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { updateCompanyStage } from '@/lib/companies';
import { STAGES } from '@/lib/stages';

// Same belt-and-suspenders pattern as /api/top-vcs and the screens PATCH
// route -- middleware already restricts the whole site to signed-in users
// and these pages to 'internal', but a live-editable endpoint is worth
// double-checking here too.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

export async function PATCH(request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { slug } = await params;
  const { stage } = await request.json();
  if (!STAGES.includes(stage)) return NextResponse.json({ error: 'invalid-stage' }, { status: 400 });

  try {
    const result = await updateCompanyStage(slug, stage);
    return NextResponse.json({ ok: true, ...result });
  } catch (err) {
    const status = err.message === 'company-not-found' ? 404 : err.message === 'invalid-stage' ? 400 : 500;
    return NextResponse.json({ error: err.message || 'update-failed' }, { status });
  }
}
