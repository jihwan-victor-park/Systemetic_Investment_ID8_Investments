import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { listAccessRequests, setAccessStatus } from '@/lib/investorAccess';

// Belt-and-suspenders: middleware's authorized() callback already restricts
// every non-/investors route to role 'internal', but this data can approve
// external accounts, so double-check here too rather than trust that alone.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

export async function GET() {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const requests = await listAccessRequests();
  return NextResponse.json({ requests });
}

export async function POST(request) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { email, status } = (await request.json()) || {};
  if (!email || !['approved', 'denied', 'pending'].includes(status)) {
    return NextResponse.json({ error: 'invalid-request' }, { status: 400 });
  }
  await setAccessStatus(email, status);
  return NextResponse.json({ ok: true });
}
