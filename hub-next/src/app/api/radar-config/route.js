import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { getRadarConfig, updateRadarConfig } from '@/lib/radarConfig';

export async function GET() {
  const session = await auth();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const config = await getRadarConfig();
  return NextResponse.json({ config });
}

export async function PATCH(request) {
  const session = await auth();
  if (session?.user?.role !== 'internal') return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const body = await request.json();
  const updatedBy = session.user.email || session.user.name || null;
  try {
    const config = await updateRadarConfig(body, updatedBy);
    return NextResponse.json({ config });
  } catch (err) {
    return NextResponse.json({ error: err.message || 'save-failed' }, { status: 400 });
  }
}
