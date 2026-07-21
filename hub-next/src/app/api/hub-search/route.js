import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { searchHub } from '@/lib/hubSearch';

async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

export async function GET(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { searchParams } = new URL(request.url);
  const results = await searchHub({
    vc: searchParams.get('vc') || undefined,
    round: searchParams.get('round') || undefined,
    radarCategory: searchParams.get('radarCategory') || undefined,
    stage: searchParams.get('stage') || undefined,
    minFitScore: searchParams.get('minFitScore') || undefined,
  });
  return NextResponse.json({ results });
}
