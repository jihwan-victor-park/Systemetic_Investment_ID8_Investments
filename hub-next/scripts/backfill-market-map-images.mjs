#!/usr/bin/env node
// Backfills marketMapEntries that don't have an image yet: fetches each
// entry's source URL, pulls the article's og:image (the actual map/report
// graphic on every VC-blog page we've checked — not a generic thumbnail),
// downloads it, and uploads it to GCS at market-maps/<id>.<ext>. PDFs are
// stored as themselves (the "image" the lightbox opens is the PDF).
//
// Does NOT touch existing titles — VC-blog article titles don't reliably
// match the map's actual name, and telling the two apart needs a human (or
// an agent) to look at the page, not a regex. Instead this prints the page's
// og:title next to the current title so a human pass can decide what to
// rename, entry by entry.
//
// Can't run from a sandboxed environment (needs real GCP credentials) — run
// this from Cloud Shell or a local machine with `gcloud auth application-
// default login` done and access to the market-map bucket + Firestore.
//
// Usage:
//   GCP_PROJECT_ID=molten-crowbar-498920-q8 MARKET_MAP_BUCKET=<bucket> node scripts/backfill-market-map-images.mjs
//   Add --dry-run to fetch/report without uploading or writing to Firestore.

import { Firestore } from '@google-cloud/firestore';
import { Storage } from '@google-cloud/storage';

const DRY_RUN = process.argv.includes('--dry-run');
const BUCKET = process.env.MARKET_MAP_BUCKET || process.env.DI_DOCX_BUCKET;
const FETCH_TIMEOUT_MS = 15_000;
const UA = 'Mozilla/5.0 (compatible; id8-hub-market-map-backfill/1.0)';

const db = new Firestore({ projectId: process.env.GCP_PROJECT_ID || undefined });
const storage = new Storage({ projectId: process.env.GCP_PROJECT_ID || undefined });

const EXT_FOR_TYPE = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/webp': 'webp',
  'image/gif': 'gif',
  'application/pdf': 'pdf',
};

function withTimeout(ms) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  return { signal: ctrl.signal, done: () => clearTimeout(t) };
}

async function fetchText(url) {
  const { signal, done } = withTimeout(FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { headers: { 'User-Agent': UA }, signal, redirect: 'follow' });
    if (!res.ok) return { ok: false, status: res.status };
    return { ok: true, text: await res.text() };
  } catch (err) {
    return { ok: false, error: err.message };
  } finally {
    done();
  }
}

async function fetchBinary(url) {
  const { signal, done } = withTimeout(FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { headers: { 'User-Agent': UA }, signal, redirect: 'follow' });
    if (!res.ok) return { ok: false, status: res.status };
    const contentType = res.headers.get('content-type')?.split(';')[0].trim() || 'application/octet-stream';
    const buffer = Buffer.from(await res.arrayBuffer());
    return { ok: true, buffer, contentType };
  } catch (err) {
    return { ok: false, error: err.message };
  } finally {
    done();
  }
}

// Raw HTML attribute values still have entities escaped (a literal "&amp;"
// between two query params, "&ndash;" for a real en-dash in a filename,
// etc.) -- passed straight into fetch() as-is, a multi-param image URL turns
// into one malformed request. Decoding here is what actually fixed two of
// the "manual attention" entries from the 2026-07 backfill run: both were
// good, fetchable images, just mangled by this.
function decodeHtmlEntities(str) {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&(?:#0*39|apos);/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&ndash;/g, '–')
    .replace(/&mdash;/g, '—')
    .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(Number(dec)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCodePoint(parseInt(hex, 16)));
}

function metaContent(html, property) {
  const re = new RegExp(`<meta[^>]+property=["']${property}["'][^>]+content=["']([^"']+)["']`, 'i');
  const m = html.match(re) || html.match(new RegExp(`<meta[^>]+content=["']([^"']+)["'][^>]+property=["']${property}["']`, 'i'));
  return m ? decodeHtmlEntities(m[1]) : null;
}

// Specific, human-verified corrections from the 2026-07 backfill review --
// keyed by the entry's CURRENT url so this stays correct even if titles
// change later. Each entry needed one of:
//   imageUrl  -- the page has no extractable og:image at all (interactive
//                embed/mirror site); use this direct image URL instead of
//                scraping the page.
//   newUrl    -- the stored url itself was wrong (dead link, or pointed at a
//                generic homepage instead of the actual sub-page); fetch
//                og:image from here instead, and correct the stored url too.
//   title     -- the stored title was the parent blog post's headline, and a
//                more specific/accurate name for this exact map was found
//                actually printed on the page (never invented).
// Deliberately NOT exhaustive -- most of the 82 entries' titles were already
// fine (og:title differences were just SEO branding cruft, worse than the
// original), so only the ones with real, verified justification are here.
const OVERRIDES = {
  'https://venturemarketmaps.com/m/22-a16z-ai-content-generation-content-editing': {
    imageUrl: 'https://pbs.twimg.com/media/GGJkoWbbYAAKC9N?format=jpg&name=medium',
  },
  'https://venturemarketmaps.com/m/2-a16z-ai-x-productivity-tools': {
    imageUrl: 'https://pbs.twimg.com/media/GGzHOlobkAAzrf5?format=png&name=large',
  },
  'https://www.axc.vc/blog-posts/energy-ai': {
    newUrl: 'https://www.axc.vc/blog/energy-ai',
    title: 'AI for Energy in Europe',
  },
  'https://www.legaltechnologyhub.com/': {
    newUrl: 'https://www.legaltechnologyhub.com/contents/lth-genai-legal-tech-map-june-2026/',
    title: 'LTH GenAI Legal Tech Map: June 2026',
  },
  'https://headline.com/blog-latest/article-latest/the-duality-of-infrastructure-software-investing-i': {
    title: 'The Duality of Infrastructure Software Investing in an AI World',
  },
  'https://www.sierraventures.com/content/voice-ai-market-map': {
    title: 'Transforming Voice: Market Map of 150+ Voice AI Companies',
  },
  'https://sequoiacap.com/article/generative-ai-act-two/': {
    title: "Generative AI's Act Two",
  },
  'https://www.nvp.com/blog/market-map-reimagining-cfo-software-stack/': {
    title: 'Market Map: Reimagining the CFO Software Stack',
  },
  'https://a16z.com/space-a-market-map/': {
    title: 'Space: A Market Map',
  },
  'https://www.bvp.com/atlas/how-data-privacy-engineering-will-prevent-future-data-oil-spills': {
    title: 'Roadmap: Data Privacy Engineering',
  },
  'https://www.a16z.news/p/why-we-need-continual-learning': {
    title: 'The Continual Learning Startup Landscape',
  },
  'https://newsletter.semianalysis.com/p/clustermax-20-the-industry-standard': {
    title: 'ClusterMAX 2.0 Market View, November 2025',
  },
};

async function resolveImageSource(entry) {
  const override = OVERRIDES[entry.url] || {};

  if (override.imageUrl) {
    return { imageUrl: override.imageUrl, suggestedTitle: null, method: 'override' };
  }

  const effectiveUrl = override.newUrl || entry.url;
  if (/\.pdf(\?|$)/i.test(effectiveUrl)) {
    return { imageUrl: effectiveUrl, suggestedTitle: null, method: 'direct-pdf' };
  }
  const page = await fetchText(effectiveUrl);
  if (!page.ok) return { error: `page fetch failed (${page.status || page.error})` };

  const ogImage = metaContent(page.text, 'og:image');
  const ogTitle = metaContent(page.text, 'og:title');
  if (!ogImage) return { error: 'no og:image found on page' };

  return { imageUrl: ogImage, suggestedTitle: ogTitle, method: 'og:image' };
}

async function main() {
  if (!BUCKET) {
    console.error('MARKET_MAP_BUCKET or DI_DOCX_BUCKET must be set.');
    process.exit(1);
  }

  const snap = await db.collection('marketMapEntries').get();
  const entries = snap.docs
    .map((doc) => ({ id: doc.id, ...doc.data() }))
    .filter((d) => !d.imagePath);

  console.log(`${snap.size} total entries, ${entries.length} missing an image.${DRY_RUN ? ' (dry run)' : ''}\n`);

  const results = { ok: [], failed: [], titleSuggestions: [] };

  for (const entry of entries) {
    const override = OVERRIDES[entry.url] || {};
    process.stdout.write(`- ${entry.firm} — "${entry.title}" (${entry.url})\n`);
    const resolved = await resolveImageSource(entry);
    if (resolved.error) {
      console.log(`    ✗ ${resolved.error}`);
      results.failed.push({ id: entry.id, firm: entry.firm, title: entry.title, url: entry.url, reason: resolved.error });
      continue;
    }

    const asset = await fetchBinary(resolved.imageUrl);
    if (!asset.ok) {
      console.log(`    ✗ image download failed (${asset.status || asset.error})`);
      results.failed.push({ id: entry.id, firm: entry.firm, title: entry.title, url: entry.url, reason: 'image download failed' });
      continue;
    }

    const ext = EXT_FOR_TYPE[asset.contentType] || 'png';
    const path = `market-maps/${entry.id}.${ext}`;

    if (!DRY_RUN) {
      await storage.bucket(BUCKET).file(path).save(asset.buffer, { contentType: asset.contentType });
      const update = { imagePath: path, imageContentType: asset.contentType };
      if (override.newUrl) update.url = override.newUrl;
      if (override.title) update.title = override.title;
      await db.collection('marketMapEntries').doc(entry.id).update(update);
    }

    const overrideNote = override.title || override.newUrl ? ' (title/url corrected)' : '';
    console.log(`    ✓ ${resolved.method} → ${path} (${asset.contentType}, ${(asset.buffer.length / 1024).toFixed(0)}KB)${overrideNote}`);
    results.ok.push(entry.id);

    if (resolved.suggestedTitle && resolved.suggestedTitle.trim() !== entry.title.trim()) {
      console.log(`    ↳ page og:title differs — current: "${entry.title}" / page: "${resolved.suggestedTitle}"`);
      results.titleSuggestions.push({ id: entry.id, current: entry.title, suggested: resolved.suggestedTitle });
    }

    // Be polite to the sites we're scraping.
    await new Promise((r) => setTimeout(r, 400));
  }

  console.log(`\n${results.ok.length} succeeded, ${results.failed.length} need manual attention.\n`);
  if (results.failed.length) {
    console.log('Needs a manually-sourced image (interactive embed, PDF viewer, paywall, blocked fetch, etc.):');
    results.failed.forEach((f) => console.log(`  - [${f.id}] ${f.firm} — "${f.title}" — ${f.url}  (${f.reason})`));
  }
  if (results.titleSuggestions.length) {
    console.log('\nTitle mismatches worth a manual look (not auto-applied):');
    results.titleSuggestions.forEach((t) => console.log(`  - [${t.id}] "${t.current}" → "${t.suggested}"`));
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
