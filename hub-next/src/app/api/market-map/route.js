import { NextResponse } from 'next/server';
import { addMarketMapEntry } from '@/lib/marketMap';

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
