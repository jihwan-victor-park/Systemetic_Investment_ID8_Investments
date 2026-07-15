import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { deleteCompany } from '@/lib/companies';

// Same belt-and-suspenders pattern as /api/companies/[slug]/stage -- middleware
// already restricts the whole site to signed-in users and these pages to
// 'internal', but a destructive endpoint is worth double-checking here too.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

export async function DELETE(_request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { slug } = await params;
  try {
    await deleteCompany(slug);
    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err.message === 'company-not-found' ? 404 : 500;
    return NextResponse.json({ error: err.message || 'delete-failed' }, { status });
  }
}
