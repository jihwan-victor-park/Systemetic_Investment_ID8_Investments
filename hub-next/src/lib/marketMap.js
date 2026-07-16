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
      // imageUpdatedAt busts the image route's far-future cache when a photo is
      // replaced in place (see updateMarketMapEntry) -- without it, browsers
      // that already fetched the old image at this same URL would keep
      // serving it from cache indefinitely.
      image: d.imagePath ? `/api/market-map/image/${doc.id}${d.imageUpdatedAt ? `?v=${d.imageUpdatedAt}` : ''}` : null,
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

// Shared update path for correcting an entry that already exists, without
// touching firm/category/url/dateLabel/note/createdAt. Used server-to-server
// by app/api/admin-market-map/[id]/route.js, and from the browser (signed-in
// internal users only) by the PATCH handler in app/api/market-map/route.js
// for the "replace photo" control on the directory page.
export async function updateMarketMapEntry(id, { title, imageBuffer, imageContentType } = {}) {
  const ref = db().collection('marketMapEntries').doc(id);
  const doc = await ref.get();
  if (!doc.exists) return { ok: false, error: 'not-found' };

  const update = {};
  if (title && title.trim()) update.title = title.trim();

  if (imageBuffer && imageBuffer.length) {
    if (!BUCKET) return { ok: false, error: 'bucket-not-configured' };
    const ext = EXT_FOR_TYPE[imageContentType] || 'png';
    const imagePath = `market-maps/${id}.${ext}`;
    await storage().bucket(BUCKET).file(imagePath).save(imageBuffer, {
      contentType: imageContentType || 'application/octet-stream',
    });
    update.imagePath = imagePath;
    update.imageContentType = imageContentType || 'application/octet-stream';
    // The image route caches responses far into the future assuming the
    // bytes at a given id never change -- they now can, so stamp a version
    // the client appends as a `?v=` query param to bust that cache.
    update.imageUpdatedAt = Date.now();
  }

  if (Object.keys(update).length === 0) return { ok: false, error: 'nothing-to-update' };

  await ref.update(update);
  return {
    ok: true,
    id,
    updated: Object.keys(update),
    title: update.title,
    image: update.imagePath ? `/api/market-map/image/${id}?v=${update.imageUpdatedAt}` : undefined,
    imageIsDoc: update.imageContentType === 'application/pdf' || undefined,
  };
}

// Removes an entry from the directory, cleaning up its stored image (if any)
// alongside the Firestore doc so it doesn't linger as an orphaned blob.
export async function deleteMarketMapEntry(id) {
  const ref = db().collection('marketMapEntries').doc(id);
  const doc = await ref.get();
  if (!doc.exists) return { ok: false, error: 'not-found' };

  const { imagePath } = doc.data();
  if (imagePath && BUCKET) {
    await storage().bucket(BUCKET).file(imagePath).delete({ ignoreNotFound: true });
  }

  await ref.delete();
  return { ok: true };
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
