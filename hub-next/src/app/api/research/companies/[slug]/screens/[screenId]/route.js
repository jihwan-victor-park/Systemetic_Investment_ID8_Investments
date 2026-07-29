import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { updateScreenField, deleteScreen } from '@/lib/companies';

// Same belt-and-suspenders pattern as /api/top-vcs -- middleware already
// restricts the whole site to signed-in users and this page to 'internal'
// (investors get redirected to /investors/research before they ever reach
// /docs/qualified-deals), but a live-editable scoring endpoint is worth
// double-checking here too.
async function requireInternal() {
  const session = await auth();
  return session?.user?.role === 'internal';
}

const VALID_FIELDS = new Set(['score', 'finding', 'evidence', 'rationale']);

export async function PATCH(request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { slug, screenId } = await params;
  const body = await request.json();
  const { dimensionKey, subcategoryKey, field, value } = body || {};

  if (!VALID_FIELDS.has(field)) {
    return NextResponse.json({ error: 'invalid-field' }, { status: 400 });
  }
  if (field !== 'rationale' && !dimensionKey) {
    return NextResponse.json({ error: 'missing-dimension-key' }, { status: 400 });
  }
  if ((field === 'score' || field === 'finding') && !subcategoryKey) {
    return NextResponse.json({ error: 'missing-subcategory-key' }, { status: 400 });
  }
  if (field === 'score' && (!Number.isInteger(value) || value < 1 || value > 4)) {
    return NextResponse.json({ error: 'invalid-score' }, { status: 400 });
  }

  try {
    const screen = await updateScreenField(slug, screenId, { dimensionKey, subcategoryKey, field, value });
    return NextResponse.json({ ok: true, screen });
  } catch (err) {
    const known = ['screen-not-found', 'dimension-not-found', 'subcategory-not-found', 'missing-subcategory-key', 'invalid-score', 'invalid-field'];
    const status = known.includes(err.message) ? 400 : 500;
    return NextResponse.json({ error: err.message || 'update-failed' }, { status });
  }
}

export async function DELETE(_request, { params }) {
  if (!(await requireInternal())) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { slug, screenId } = await params;
  try {
    await deleteScreen(slug, screenId);
    return NextResponse.json({ ok: true });
  } catch (err) {
    const status = err.message === 'screen-not-found' ? 404 : 500;
    return NextResponse.json({ error: err.message || 'delete-failed' }, { status });
  }
}
