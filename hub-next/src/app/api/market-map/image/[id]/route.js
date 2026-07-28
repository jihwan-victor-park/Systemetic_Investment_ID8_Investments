import { NextResponse } from 'next/server';
import { getMarketMapImage } from '@/lib/marketMap';

export async function GET(_request, { params }) {
  const { id } = await params;
  const result = await getMarketMapImage(id);
  if (!result) return NextResponse.json({ error: 'not-found' }, { status: 404 });

  return new NextResponse(result.buffer, {
    headers: {
      'Content-Type': result.contentType,
      // Immutable: each entry's image lives at a fixed id-derived path and is
      // never overwritten in place, so a far-future cache is safe.
      'Cache-Control': 'public, max-age=31536000, immutable',
    },
  });
}
