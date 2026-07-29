import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { getRadarKeywords, addKeywordRule, removeKeywordRule } from '@/lib/radarRules';
import { MIN_KEYWORD_LENGTH } from '@/lib/radarRuleMatch';

// Same belt-and-suspenders pattern as /api/partner-vcs -- middleware already
// restricts /docs/* to signed-in users, editing the shared keyword list is
// worth double-checking here too.
export async function GET() {
  const session = await auth();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const keywords = await getRadarKeywords();
  return NextResponse.json({ keywords });
}

export async function POST(request) {
  const session = await auth();
  if (session?.user?.role !== 'internal') return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const body = await request.json();
  if (body?.action !== 'addKeyword' || !body.term || body.term.trim().length < MIN_KEYWORD_LENGTH) {
    return NextResponse.json({ error: 'term-too-short' }, { status: 400 });
  }
  const addedBy = session.user.email || session.user.name || null;
  await addKeywordRule(body.term, addedBy);
  return NextResponse.json({ ok: true });
}

export async function DELETE(request) {
  const session = await auth();
  if (session?.user?.role !== 'internal') return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const { searchParams } = new URL(request.url);
  const term = searchParams.get('term');
  if (!term) return NextResponse.json({ error: 'missing-term' }, { status: 400 });
  await removeKeywordRule(term);
  return NextResponse.json({ ok: true });
}
