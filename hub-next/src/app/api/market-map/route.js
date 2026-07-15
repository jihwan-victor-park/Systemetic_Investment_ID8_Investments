import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { addMarketMapEntry, deleteMarketMapEntry } from '@/lib/marketMap';

// Same belt-and-suspenders pattern as /api/companies/[slug] -- middleware
// already restricts the whole site to signed-in users and this page to
// 'internal' (the Market Map directory lives under /docs, which redirects
// investors away before they ever reach it), but a destructive endpoint is
// worth double-checking here too.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

export async function POST(request) {
  const form = await request.formData();
  const firm = form.get('firm')?.toString().trim();
  const title = form.get('title')?.toString().trim();
  const category = form.get('category')?.toString().trim();
  const url = form.get('url')?.toString().trim();
  const dateLabel = form.get('dateLabel')?.toString().trim();
  const note = form.get('note')?.toString().trim();
  const ymRaw = form.get('ym');
  const photo = form.get('photo');

  if (!firm || !title || !category || !url || !dateLabel) {
    return NextResponse.json({ error: 'missing-required-field' }, { status: 400 });
  }

  let imageBuffer = null;
  let imageContentType = null;
  if (photo && typeof photo === 'object' && typeof photo.arrayBuffer === 'function' && photo.size > 0) {
    imageBuffer = Buffer.from(await photo.arrayBuffer());
    imageContentType = photo.type || null;
  }

  const { id, hasImage } = await addMarketMapEntry({
    firm, title, category, url,
    ym: ymRaw ? Number(ymRaw) : null,
    dateLabel,
    note,
    imageBuffer,
    imageContentType,
  });
  return NextResponse.json({ ok: true, id, hasImage });
}

export async function DELETE(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');
  if (!id) return NextResponse.json({ error: 'missing-id' }, { status: 400 });

  const result = await deleteMarketMapEntry(id);
  if (!result.ok) return NextResponse.json(result, { status: result.error === 'not-found' ? 404 : 400 });
  return NextResponse.json(result);
}
