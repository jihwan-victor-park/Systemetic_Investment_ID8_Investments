import { NextResponse } from 'next/server';
import { listIdeas, addIdea, deleteIdea } from '@/lib/ideas';

export async function GET() {
  const ideas = await listIdeas();
  return NextResponse.json({ ideas });
}

export async function POST(request) {
  const body = await request.json();
  const { type, title, note } = body || {};
  if (!type || !title) {
    return NextResponse.json({ error: 'missing-required-field' }, { status: 400 });
  }
  const id = await addIdea({ type, title, note });
  return NextResponse.json({ ok: true, id });
}

export async function DELETE(request) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');
  if (!id) return NextResponse.json({ error: 'missing-id' }, { status: 400 });
  await deleteIdea(id);
  return NextResponse.json({ ok: true });
}
