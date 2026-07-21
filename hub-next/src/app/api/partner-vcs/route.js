import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { listPartnerVCs, addPartnerVC, updatePartnerVC, deletePartnerVC } from '@/lib/partnerVCs';

// Same belt-and-suspenders pattern as /api/top-vcs -- middleware already
// restricts this route to role 'internal', but proprietary VC intelligence
// is worth double-checking here too.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

const PATCHABLE_FIELDS = ['trackedBy', 'contact', 'sector', 'website', 'note', 'description', 'attioCategories', 'connectionStrength', 'portfolio', 'news'];

export async function GET() {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const vcs = await listPartnerVCs();
  return NextResponse.json({ vcs });
}

export async function POST(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const body = await request.json();
  const { name, trackedBy, contact, sector, website, note } = body || {};
  if (!name) {
    return NextResponse.json({ error: 'missing-required-field' }, { status: 400 });
  }
  const id = await addPartnerVC({ name, trackedBy, contact, sector, website, note });
  return NextResponse.json({ ok: true, id });
}

export async function PATCH(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const body = await request.json();
  const { id, ...rest } = body || {};
  if (!id) return NextResponse.json({ error: 'missing-id' }, { status: 400 });
  const patch = Object.fromEntries(Object.entries(rest).filter(([k]) => PATCHABLE_FIELDS.includes(k)));
  try {
    await updatePartnerVC(id, patch);
    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err.message === 'vc-not-found' ? 404 : 500;
    return NextResponse.json({ error: err.message || 'update-failed' }, { status });
  }
}

export async function DELETE(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');
  if (!id) return NextResponse.json({ error: 'missing-id' }, { status: 400 });
  await deletePartnerVC(id);
  return NextResponse.json({ ok: true });
}
