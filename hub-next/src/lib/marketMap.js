import 'server-only';
import { Storage } from '@google-cloud/storage';
import { db } from './firestore';

// Reuses the docx bucket by default so a fresh market-map feature doesn't need
// its own bucket + IAM grant provisioned before it can store images — set
// MARKET_MAP_BUCKET explicitly if it should live somewhere else.
const BUCKET = process.env.MARKET_MAP_BUCKET || process.env.DI_DOCX_BUCKET;

let _storage;
function storage() {
  if (!_storage) _storage = new Storage({ projectId: process.env.GCP_PROJECT_ID || undefined });
  return _storage;
}

const EXT_FOR_TYPE = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/webp': 'webp',
  'image/gif': 'gif',
  'application/pdf': 'pdf',
};

export async function listMarketMapEntries() {
  const snap = await db().collection('marketMapEntries').orderBy('createdAt', 'desc').get();
  return snap.docs.map((doc) => {
    const d = doc.data();
    return {
      id: doc.id,
      firm: d.firm,
      title: d.title,
      cat: d.category,
      url: d.url,
      ym: d.ym ?? null,
      date: d.dateLabel,
      note: d.note || undefined,
      image: d.imagePath ? `/api/market-map/image/${doc.id}` : null,
      imageIsDoc: d.imageContentType === 'application/pdf',
    };
  });
}

export async function addMarketMapEntry({ firm, title, category, url, ym, dateLabel, note, imageBuffer, imageContentType }) {
  const ref = db().collection('marketMapEntries').doc();

  let imagePath = null;
  if (imageBuffer && imageBuffer.length) {
    if (BUCKET) {
      const ext = EXT_FOR_TYPE[imageContentType] || 'png';
      imagePath = `market-maps/${ref.id}.${ext}`;
      await storage().bucket(BUCKET).file(imagePath).save(imageBuffer, {
        contentType: imageContentType || 'application/octet-stream',
      });
    } else {
      console.warn('MARKET_MAP_BUCKET/DI_DOCX_BUCKET not configured — saving entry without an image');
    }
  }

  await ref.set({
    firm,
    title,
    category,
    url,
    ym: ym ?? null,
    dateLabel,
    note: note || null,
    imagePath,
    imageContentType: imagePath ? imageContentType : null,
    createdAt: new Date(),
  });
  return { id: ref.id, hasImage: !!imagePath };
}

export async function getMarketMapImage(id) {
  if (!BUCKET) return null;
  const doc = await db().collection('marketMapEntries').doc(id).get();
  if (!doc.exists) return null;
  const d = doc.data();
  if (!d.imagePath) return null;

  const file = storage().bucket(BUCKET).file(d.imagePath);
  const [exists] = await file.exists();
  if (!exists) return null;

  const [buffer] = await file.download();
  return { buffer, contentType: d.imageContentType || 'application/octet-stream' };
}
