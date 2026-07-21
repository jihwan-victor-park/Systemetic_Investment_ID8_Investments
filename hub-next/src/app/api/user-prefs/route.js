import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { getUserPrefs, updateUserPrefs } from '@/lib/userPrefs';

// Unlike every other API route here, this one is intentionally open to any
// signed-in user (internal or investor) -- it's each person's own tab
// layout, scoped to their own email server-side (never a client-supplied
// id), so there's nothing proprietary to gate.
export async function GET() {
  const session = await auth();
  if (!session?.user?.email) return NextResponse.json({ tabOrder: [], labels: {} });
  const prefs = await getUserPrefs(session.user.email);
  return NextResponse.json(prefs);
}

export async function PATCH(request) {
  const session = await auth();
  if (!session?.user?.email) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const body = await request.json().catch(() => ({}));
  const patch = {};
  if (Array.isArray(body.tabOrder)) patch.tabOrder = body.tabOrder;
  if (body.labels && typeof body.labels === 'object') patch.labels = body.labels;
  if (!Object.keys(patch).length) return NextResponse.json({ error: 'invalid-request' }, { status: 400 });
  await updateUserPrefs(session.user.email, patch);
  return NextResponse.json({ ok: true });
}
