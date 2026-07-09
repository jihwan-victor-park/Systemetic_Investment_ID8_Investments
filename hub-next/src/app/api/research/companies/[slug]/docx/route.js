import { NextResponse } from 'next/server';
import { Storage } from '@google-cloud/storage';

// Streams the latest screen's .docx straight from Cloud Storage -- the file
// is uploaded there by deal_intelligence/firestore_push.py on every screen,
// so this route always serves the current version with no rebuild/redeploy.
const BUCKET = process.env.DI_DOCX_BUCKET;

let _storage;
function storage() {
  if (!_storage) _storage = new Storage({ projectId: process.env.GCP_PROJECT_ID || undefined });
  return _storage;
}

export async function GET(_request, { params }) {
  const { slug } = await params;
  if (!BUCKET) return NextResponse.json({ error: 'docx-bucket-not-configured' }, { status: 404 });

  const file = storage().bucket(BUCKET).file(`research/companies/${slug}.docx`);
  const [exists] = await file.exists();
  if (!exists) return NextResponse.json({ error: 'not-found' }, { status: 404 });

  const [buffer] = await file.download();
  return new NextResponse(buffer, {
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'Content-Disposition': `attachment; filename="${slug}.docx"`,
    },
  });
}
