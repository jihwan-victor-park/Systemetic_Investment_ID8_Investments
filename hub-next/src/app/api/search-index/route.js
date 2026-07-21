import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { buildSearchIndex } from '@/lib/searchIndex';

// Internal-only, same as every other route that touches deal/VC data --
// investors never see this control (Navbar only renders it outside investor
// view), but the route itself double-checks too.
export async function GET() {
  const session = await auth();
  if (session?.user?.role !== 'internal') return NextResponse.json({ entries: [] });
  const entries = await buildSearchIndex();
  return NextResponse.json({ entries });
}
