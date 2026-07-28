import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { deleteDealResearchDeck } from '@/lib/dealResearchDecks';

// Same belt-and-suspenders pattern as /api/companies/[slug] -- middleware
// already restricts the whole site to signed-in users and this page to
// 'internal', but a destructive endpoint is worth double-checking here too.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

export async function DELETE(_request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { id } = await params;
  await deleteDealResearchDeck(id);
  return NextResponse.json({ ok: true });
}
