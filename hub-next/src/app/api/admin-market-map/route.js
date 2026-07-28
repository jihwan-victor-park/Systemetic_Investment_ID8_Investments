import { NextResponse } from 'next/server';
import { listMarketMapEntries } from '@/lib/marketMap';

// Sibling to [id]/route.js (PATCH) -- same server-to-server, shared-secret
// guard, excluded from the sign-in gate in src/middleware.js. Read-only list
// of every entry so an outside caller can figure out which ones still need
// an image and/or a title correction, without a Firestore console.
export async function GET(request) {
  const configured = process.env.MARKET_MAP_ADMIN_SECRET;
  if (!configured) {
    return NextResponse.json({ error: 'admin-secret-not-configured' }, { status: 500 });
  }
  if (request.headers.get('x-admin-secret') !== configured) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const entries = await listMarketMapEntries();
  return NextResponse.json({ entries });
}
