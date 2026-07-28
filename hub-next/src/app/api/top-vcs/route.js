import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { listTopVCs, addTopVC, updateTopVC, deleteTopVC } from '@/lib/topVCs';

// Same belt-and-suspenders pattern as /api/access-requests -- middleware
// already restricts this route to role 'internal', but proprietary VC
// intelligence is worth double-checking here too.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

// Everything beyond the original add-form fields (fund characteristics, the
// Attio-relationship placeholder, deals/news lists) is edited from the firm
// detail page via PATCH -- whitelisted so the route can't be used to write
// arbitrary fields onto a topVCs doc.
const PATCHABLE_FIELDS = ['tier', 'sector', 'website', 'note', 'fund', 'attio', 'deals', 'totalInvestments', 'news'];

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

export async function PATCH(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const body = await request.json();
  const { id, ...rest } = body || {};
  if (!id) return NextResponse.json({ error: 'missing-id' }, { status: 400 });
  const patch = Object.fromEntries(Object.entries(rest).filter(([k]) => PATCHABLE_FIELDS.includes(k)));
  // totalInvestments is a plain count typed into an InlineTextField (which
  // only ever sends strings) -- store it as a number so downstream `>`
  // comparisons (companyToRow-style "no data yet" checks) behave correctly.
  if ('totalInvestments' in patch) {
    const n = Number(patch.totalInvestments);
    patch.totalInvestments = Number.isFinite(n) && patch.totalInvestments !== '' ? n : null;
  }
  try {
    await updateTopVC(id, patch);
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
  await deleteTopVC(id);
  return NextResponse.json({ ok: true });
}
