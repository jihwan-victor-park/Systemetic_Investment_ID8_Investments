import { NextResponse } from 'next/server';
import { updateMarketMapEntry } from '@/lib/marketMap';

// Server-to-server only: excluded from the session-gate middleware (see
// src/middleware.js) so it can be called without a browser session, guarded
// instead by a shared secret header. Used to backfill an image and/or correct
// a title on an existing marketMapEntries doc from outside the app — see
// hub-next/scripts/backfill-market-map-images.mjs for the sibling script this
// complements (that one only ever sets an image, never a title).
export async function PATCH(request, { params }) {
  const configured = process.env.MARKET_MAP_ADMIN_SECRET;
  if (!configured) {
    return NextResponse.json({ error: 'admin-secret-not-configured' }, { status: 500 });
  }
  if (request.headers.get('x-admin-secret') !== configured) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const { id } = await params;
  const form = await request.formData();
  const title = form.get('title')?.toString().trim() || undefined;
  const photo = form.get('photo');

  let imageBuffer, imageContentType;
  if (photo && typeof photo === 'object' && typeof photo.arrayBuffer === 'function' && photo.size > 0) {
    imageBuffer = Buffer.from(await photo.arrayBuffer());
    imageContentType = photo.type || null;
  }

  const result = await updateMarketMapEntry(id, { title, imageBuffer, imageContentType });
  if (!result.ok) {
    const status = result.error === 'not-found' ? 404 : 400;
    return NextResponse.json(result, { status });
  }
  return NextResponse.json(result);
}
