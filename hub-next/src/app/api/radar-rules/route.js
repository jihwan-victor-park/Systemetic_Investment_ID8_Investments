import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import {
  getRadarRules,
  addKeywordRule,
  removeKeywordRule,
  addCompanyExclusion,
  removeCompanyExclusion,
  setKeepAnyway,
} from '@/lib/radarRules';

// Same belt-and-suspenders pattern as /api/partner-vcs -- middleware already
// restricts /docs/* to signed-in users, but editing what's hidden from the
// whole team is worth double-checking here too.
async function requireInternal() {
  const session = await auth();
  return session;
}

export async function GET() {
  const session = await requireInternal();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const rules = await getRadarRules();
  return NextResponse.json({ rules });
}

export async function POST(request) {
  const session = await requireInternal();
  if (session?.user?.role !== 'internal') return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const body = await request.json();
  const addedBy = session.user.email || session.user.name || null;

  if (body?.action === 'addKeyword') {
    if (!body.term || body.term.trim().length < 3) {
      return NextResponse.json({ error: 'term-too-short' }, { status: 400 });
    }
    await addKeywordRule(body.term, addedBy);
    return NextResponse.json({ ok: true });
  }
  if (body?.action === 'excludeCompany') {
    if (!body.slug) return NextResponse.json({ error: 'missing-slug' }, { status: 400 });
    await addCompanyExclusion(body.slug, body.name, body.reason, addedBy);
    return NextResponse.json({ ok: true });
  }
  if (body?.action === 'keepAnyway') {
    if (!body.slug) return NextResponse.json({ error: 'missing-slug' }, { status: 400 });
    await setKeepAnyway(body.slug, body.name, body.keep !== false, addedBy);
    return NextResponse.json({ ok: true });
  }
  return NextResponse.json({ error: 'unknown-action' }, { status: 400 });
}

export async function DELETE(request) {
  const session = await requireInternal();
  if (session?.user?.role !== 'internal') return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { searchParams } = new URL(request.url);
  const action = searchParams.get('action');

  if (action === 'keyword') {
    const term = searchParams.get('term');
    if (!term) return NextResponse.json({ error: 'missing-term' }, { status: 400 });
    await removeKeywordRule(term);
    return NextResponse.json({ ok: true });
  }
  if (action === 'company') {
    const slug = searchParams.get('slug');
    if (!slug) return NextResponse.json({ error: 'missing-slug' }, { status: 400 });
    await removeCompanyExclusion(slug);
    return NextResponse.json({ ok: true });
  }
  if (action === 'keepAnyway') {
    const slug = searchParams.get('slug');
    if (!slug) return NextResponse.json({ error: 'missing-slug' }, { status: 400 });
    await setKeepAnyway(slug, null, false, null);
    return NextResponse.json({ ok: true });
  }
  return NextResponse.json({ error: 'unknown-action' }, { status: 400 });
}
