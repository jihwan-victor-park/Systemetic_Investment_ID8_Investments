import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { listTopVCs, addTopVC, deleteTopVC } from '@/lib/topVCs';

// Same belt-and-suspenders pattern as /api/access-requests -- middleware
// already restricts this route to role 'internal', but proprietary VC
// intelligence is worth double-checking here too.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

export async function GET() {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const vcs = await listTopVCs();
  return NextResponse.json({ vcs });
}

export async function POST(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const body = await request.json();
  const { name, tier, sector, website, note } = body || {};
  if (!name || !tier) {
    return NextResponse.json({ error: 'missing-required-field' }, { status: 400 });
  }
  const id = await addTopVC({ name, tier, sector, website, note });
  return NextResponse.json({ ok: true, id });
}

export async function DELETE(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');
  if (!id) return NextResponse.json({ error: 'missing-id' }, { status: 400 });
  await deleteTopVC(id);
  return NextResponse.json({ ok: true });
}
