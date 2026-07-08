import { NextResponse } from 'next/server';
import { addMarketMapEntry } from '@/lib/marketMap';

export async function POST(request) {
  const body = await request.json();
  const { firm, title, category, url, ym, dateLabel, note } = body || {};
  if (!firm || !title || !category || !url || !dateLabel) {
    return NextResponse.json({ error: 'missing-required-field' }, { status: 400 });
  }
  const id = await addMarketMapEntry({ firm, title, category, url, ym: ym ?? null, dateLabel, note });
  return NextResponse.json({ ok: true, id });
}
