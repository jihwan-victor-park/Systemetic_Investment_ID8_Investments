#!/usr/bin/env node
// One-time correction pass for marketMapEntries images. The original scraper
// (and the sibling backfill-market-map-images.mjs, which only ever fills
// entries with NO image) grabbed whatever the page's og:image or first <img>
// happened to be -- usually a generic hero/decorative graphic, not the
// actual market-map chart the report is about. This script overwrites the
// image for every entry below with a human/agent-verified direct URL to the
// real chart, regardless of whether it currently has an image.
//
// Verified 2026-07-16: each URL below was found by fetching the entry's
// source page, identifying the actual market-map graphic (not the hero
// image), and confirming the URL resolves to a real image/PDF. A sample was
// also visually opened and eyeballed to confirm it's a real categorized
// company chart, not decorative art.
//
// 3 entries have no fix -- the source page genuinely has no chart at all
// (just inline text or unrelated diagrams). 1 entry (Morgan Stanley Humanoid
// 100 PDF) couldn't be confirmed because advisor.morganstanley.com blocks
// automated fetches -- worth a manual look in a real browser, not touched
// here. See CORRECTIONS below for both lists.
//
// 10 Hartmann Capital (vcmaps.com) entries render their map as a live
// client-rendered grid of individual company-logo images with no static
// export available (confirmed: the site's own "Download PNG" button runs
// entirely client-side with no fetchable output). For these, the correction
// uses the site's auto-generated OpenGraph card instead -- a real,
// per-page branded title/category-count summary, not the full logo grid,
// but a large improvement over the previous generic/wrong image.
//
// Can't run from a sandboxed environment (needs real GCP credentials) — run
// this from Cloud Shell or a local machine with `gcloud auth application-
// default login` done and access to the market-map bucket + Firestore.
//
// Usage:
//   GCP_PROJECT_ID=<project> MARKET_MAP_BUCKET=<bucket> node scripts/fix-market-map-images.mjs
//   Add --dry-run to fetch/report without uploading or writing to Firestore.

import { Firestore } from '@google-cloud/firestore';
import { Storage } from '@google-cloud/storage';

const DRY_RUN = process.argv.includes('--dry-run');
const BUCKET = process.env.MARKET_MAP_BUCKET || process.env.DI_DOCX_BUCKET;
const FETCH_TIMEOUT_MS = 20_000;
const UA = 'Mozilla/5.0 (compatible; id8-hub-market-map-fix/1.0)';

const db = new Firestore({ projectId: process.env.GCP_PROJECT_ID || undefined });
const storage = new Storage({ projectId: process.env.GCP_PROJECT_ID || undefined });

const EXT_FOR_TYPE = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/webp': 'webp',
  'image/gif': 'gif',
  'image/svg+xml': 'svg',
  'application/pdf': 'pdf',
};

function withTimeout(ms) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  return { signal: ctrl.signal, done: () => clearTimeout(t) };
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

// Keyed by the entry's CURRENT (stored) url. `imageUrl` is the verified
// direct link to the real chart/PDF. `newUrl`/`title` correct the stored
// url/title too, for the handful of entries whose original data was wrong
// (dead link, homepage instead of the real sub-page) -- same convention as
// backfill-market-map-images.mjs's OVERRIDES map.
const CORRECTIONS = {
  'https://www.bvp.com/atlas/defense-tech-roadmap-five-frontiers-for-2026': { imageUrl: 'https://www.bvp.com/assets/uploads/2026/01/v6_0130_defensetechroadmap.png' },
  // Emerging Defense "Defense Tech Market Map" (emergingdefense.xyz/market-map-v2) intentionally
  // omitted -- it's a client-rendered Vite/React SPA that builds the map live in-browser from
  // ~50 individual logo images; no single static chart/export exists to substitute.
  'https://vcmaps.com/maps/defense-tech': { imageUrl: 'https://vcmaps.com/maps/defense-tech/opengraph-image?e01b2a43139dce61' },
  'https://a16z.com/space-a-market-map/': { imageUrl: 'https://a16z.com/wp-content/uploads/2023/03/Launch-1.png', title: 'Space: A Market Map' },
  'https://www.cbinsights.com/research/report/the-fraud-prevention-market-map-for-the-ai-era/': { imageUrl: 'https://research-assets.cbinsights.com/2026/06/02002052/FraudPrevention-MarketMap-052026-1-1-880x1675.png' },
  'https://www.insightpartners.com/ideas/ai-wealth-management/': { imageUrl: 'https://www.insightpartners.com/wp-content/uploads/2026/03/Blog-7-scaled.jpg' },
  'https://www.insightpartners.com/ideas/ai-in-financial-services/': { imageUrl: 'https://www.insightpartners.com/wp-content/uploads/2025/12/blog-image-4-3-min-scaled.jpg' },
  'https://sapphireventures.com/blog/from-spreadsheet-analysts-to-ai-agents-reinventing-the-modern-finance-stack/': { imageUrl: 'https://cdn-ilelafe.nitrocdn.com/pGZmlibOPJzFCLdijfKPWEgWzBTFBnmo/assets/images/optimized/rev-bb62e9c/sapphireventures.com/wp-content/uploads/2025/11/Finance-AI-Landscape_12.2.25_.png' },
  'https://www.qedinvestors.com/blog/finances-back-office-is-entering-its-biggest-upgrade-cycle-in-decades': { imageUrl: 'https://cdn.prod.website-files.com/605f2547102fdbbeff1b21e0/690a85057dbf663abda654c8_20251104_CFO_stack_market_map.png' },

  'https://www.mandalorepartners.com/research/mandalore-fintech-venture-map-2025': { imageUrl: 'https://images.squarespace-cdn.com/content/v1/5da44c892526b10b2132a84d/fdad86b8-3e68-4ea4-a493-1e1402d59232/Capture+d%E2%80%99e%CC%81cran+2025-03-03+a%CC%80+18.25.17.png' },
  'https://www.nvp.com/blog/market-map-reimagining-cfo-software-stack/': { imageUrl: 'https://www.norwest.com/wp-content/uploads/2025/03/PDF-Horizontal-Global-Office-of-the-CFO-Software-Stack.pdf', title: 'Market Map: Reimagining the CFO Software Stack' },
  'https://vcmaps.com/maps/agentic-payments': { imageUrl: 'https://vcmaps.com/maps/agentic-payments/opengraph-image?e01b2a43139dce61' },
  'https://research.contrary.com/report/living-landscape-fintech-infrastructure': { imageUrl: 'https://images.prismic.io/contrary-research/39aebf6d-787d-4892-bae9-3836d98b2924_Living+Landscape_+Fintech.png?auto=compress,format' },
  'https://cloudsecurityalliance.org/artifacts/csa-innovator-market-map': { imageUrl: 'https://cloudsecurityalliance.org/rails/active_storage/blobs/redirect/eyJfcmFpbHMiOnsiZGF0YSI6NjQ0NjMsInB1ciI6ImJsb2JfaWQifX0=--00893c1a25fe3ebfe2502c2d4f333319a2d5a59b/CSA%20Innovator%20Market%20Map%20-%20Thumbnail.png' },
  'https://menlovc.com/perspective/agents-for-security-the-tipping-point-for-offensive-ai/': { imageUrl: 'https://menlovc.com/wp-content/uploads/2026/03/agents_for_offensive_security_market_map-031826-scaled.png' },
  'https://menlovc.com/perspective/agents-for-security-and-the-opportunity-to-disrupt-securitys-giants/': { imageUrl: 'https://menlovc.com/wp-content/uploads/2025/10/security_agents_disruption-120625.webp' },
  'https://sapphireventures.com/blog/state-of-cybersecurity-growth-risk-and-resilience/': { imageUrl: 'https://sapphireventures.com/wp-content/uploads/2025/08/Cybersecurity-market-map_9.12.25_.png' },
  'https://vcmaps.com/maps/ai-cybersecurity': { imageUrl: 'https://vcmaps.com/maps/ai-cybersecurity/opengraph-image?e01b2a43139dce61' },

  'https://www.bvp.com/atlas/how-data-privacy-engineering-will-prevent-future-data-oil-spills': { imageUrl: 'https://www.bvp.com/assets/uploads/2019/09/atlas-data-privacy-diagram-sept-2020-min.jpg', title: 'Roadmap: Data Privacy Engineering' },
  'https://menlovc.com/perspective/software-finally-gets-to-work-the-opportunity-in-vertical-ai/': { imageUrl: 'https://menlovc.com/wp-content/uploads/2026/04/vertical_ai_market_map-041426-scaled.png' },
  'https://menlovc.com/perspective/2025-the-state-of-ai-in-healthcare/': { imageUrl: 'https://menlovc.com/wp-content/uploads/2025/10/15-healthcare_ai_market_map-042726.webp' },
  'https://sapphireventures.com/blog/ai-healthcare-stack-data-automation-10x-provider-2025/': { imageUrl: 'https://sapphireventures.com/wp-content/uploads/2025/09/10.2.2025_Healthcare_AI_market_map.png' },
  'https://www.felicis.com/insight/healthcare-ai-admin': { imageUrl: 'https://cdn.sanity.io/images/ggsokyyr/production/05ce8eda6df0e60b4f4da345b213982257ee249c-3208x2744.png?q=90' },
  'https://vcmaps.com/maps/brain-computer-interface': { imageUrl: 'https://vcmaps.com/maps/brain-computer-interface/opengraph-image?e01b2a43139dce61' },
  'https://menlovc.com/wp-content/uploads/2023/01/benefits_tech_market_map-042121.pdf': { imageUrl: 'https://menlovc.com/wp-content/uploads/2023/01/benefits_tech_market_map-042121.pdf' },
  'https://www.legaltechnologyhub.com/': { imageUrl: 'https://media.legaltechnologyhub.com/Static_shot_June_2026_Gen_AI_map_2355e8a50f.png', newUrl: 'https://www.legaltechnologyhub.com/contents/lth-genai-legal-tech-map-june-2026/', title: 'LTH GenAI Legal Tech Map: June 2026' },
  'https://www.legaltech.com/post/early-stage-transactional-market-map': { imageUrl: 'https://static.wixstatic.com/media/e86ce3_b2f5f451331048669855412aa1d97cd1~mv2.png' },

  'https://vcmaps.com/maps/ai-legal-tech': { imageUrl: 'https://vcmaps.com/maps/ai-legal-tech/opengraph-image?e01b2a43139dce61' },
  'https://www.battery.com/blog/the-new-code-of-law/': { imageUrl: 'https://www.battery.com/wp-content/uploads/2024/06/Legal-AI-Market-Map-Slide.jpg' },
  'https://a16z.com/a-deep-dive-into-mcp-and-the-future-of-ai-tooling/': { imageUrl: 'https://d1lamhf6l6yk6d.cloudfront.net/uploads/2025/03/250319-MCP-Market-Map-v2-x2000.png' },
  'https://www.cbinsights.com/research/ai-software-development-market-map/': { imageUrl: 'https://research-assets.cbinsights.com/2025/10/22144305/The-AI-software-development-market-map-102125-1-1.png' },
  'https://a16z.com/the-trillion-dollar-ai-software-development-stack/': { imageUrl: 'https://d1lamhf6l6yk6d.cloudfront.net/uploads/2025/10/250918-Trillion-Dollar-AI-ILG-5-r9.png' },
  'https://www.bvp.com/atlas/roadmap-developer-tooling-for-software-3-0': { imageUrl: 'https://www.bvp.com/assets/uploads/2025/08/market-map-developer-tooling-ai-v6.png' },
  'https://vcmaps.com/maps/ai-devtools': { imageUrl: 'https://vcmaps.com/maps/ai-devtools/opengraph-image?e01b2a43139dce61' },
  'https://a16z.com/100-gen-ai-apps-6/': { imageUrl: 'https://d1lamhf6l6yk6d.cloudfront.net/uploads/2026/03/Top-Gen-AI-Web-Top-50-List-v2.png' },
  'https://sapphireventures.com/blog/ai-and-the-end-of-the-productivity-bundle/': { imageUrl: 'https://sapphireventures.com/wp-content/uploads/2026/02/2.17.26_AI-productivity-bybdke-market-map-scaled.png' },

  'https://menlovc.com/wp-content/uploads/2025/12/menlo_ventures_enterprise_ai_report-2025-123125.pdf': { imageUrl: 'https://menlovc.com/wp-content/uploads/2025/12/menlo_ventures_enterprise_ai_report-2025-123125.pdf' },
  'https://a16z.com/the-ai-application-spending-report-where-startup-dollars-really-go/': { imageUrl: 'https://d1lamhf6l6yk6d.cloudfront.net/uploads/2025/10/250923-B2B-Top-50-ILG-A-r6.png' },
  'https://lsvp.com/stories/ai-enterprise-market-map-cutting-through-the-hype/': { imageUrl: 'https://lsvp.com/wp-content/uploads/2024/08/AI-Market-Map-Series-Article-I-V3-34.png' },
  'https://sequoiacap.com/article/generative-ai-act-two/': { imageUrl: 'https://sequoiacap.com/wp-content/uploads/sites/6/2023/09/generative-ai-market-map-3.png', title: "Generative AI's Act Two" },
  'https://venturemarketmaps.com/m/2-a16z-ai-x-productivity-tools': { imageUrl: 'https://pbs.twimg.com/media/GGzHOlobkAAzrf5?format=png&name=large' },
  'https://vcmaps.com/maps/computer-vision': { imageUrl: 'https://vcmaps.com/maps/computer-vision/opengraph-image?e01b2a43139dce61' },
  'https://www.bvp.com/atlas/agentic-commerce-the-rise-of-the-delegated-buyer': { imageUrl: 'https://www.bvp.com/assets/uploads/2026/05/v3_Agentic-Commerce-Market-Map_DESIGN_052126_atlas.png' },
  'https://www.norwest.com/blog/agentic-payments/': { imageUrl: 'https://www.norwest.com/wp-content/uploads/2026/03/Norwest-Agentic-Payments-Market-Map-2.jpg' },
  'https://www.insightpartners.com/ideas/iam-ai-agents/': { imageUrl: 'https://www.insightpartners.com/wp-content/uploads/2026/03/TL-Slides-Agent-IAM-1.jpg' },

  'https://www.a16z.news/p/your-data-agents-need-context': { imageUrl: 'https://substack-post-media.s3.amazonaws.com/public/images/2ffc612a-3938-46e8-8ddd-03cbea059cab_2000x1113.png' },
  'https://datawrapper.dwcdn.net/s94df/4/': { imageUrl: 'https://datawrapper.dwcdn.net/s94df/full.png' },
  'https://www.cbinsights.com/research/ai-agent-market-map-2025/': { imageUrl: 'https://research-assets.cbinsights.com/2025/11/10114220/ai-agent-market-map-112025_final.png' },
  'https://www.bvp.com/atlas/ai-infrastructure-roadmap-five-frontiers-for-2026': { imageUrl: 'https://www.bvp.com/assets/uploads/2026/03/AI-Infra-2nd-act_DESIGN-V8.png' },
  'https://www.a16z.news/p/why-we-need-continual-learning': { imageUrl: 'https://substack-post-media.s3.amazonaws.com/public/images/231f5923-48c7-422e-910f-c8bb3859d874_2000x1144.png', title: 'The Continual Learning Startup Landscape' },
  'https://headline.com/blog-latest/article-latest/the-duality-of-infrastructure-software-investing-i': { imageUrl: 'https://headline.cdn.prismic.io/headline/Z9ME2xsAHJWomgYm_Marketmap.svg', title: 'The Duality of Infrastructure Software Investing in an AI World' },
  'https://www.bvp.com/atlas/roadmap-ai-infrastructure': { imageUrl: 'https://www.bvp.com/assets/uploads/2024/06/7.15.24-AI-Infra-market-map-min.png' },
  'https://vcmaps.com/maps/ai-infrastructure': { imageUrl: 'https://vcmaps.com/maps/ai-infrastructure/opengraph-image?e01b2a43139dce61' },

  'https://www.madrona.com/the-rise-of-ai-agent-infrastructure/': { imageUrl: 'https://www.madrona.com/wp-content/uploads/2024/06/Madrona-2024-04-AIAgentsMarketMapCurrent_v9-0-HiRes.png' },
  'https://www.bvp.com/atlas/roadmap-the-ai-data-center-stack': { imageUrl: 'https://www.bvp.com/assets/uploads/2026/05/Data-Center_Market-map_DESIGN-V8.png' },
  'https://www.redpoint.com/reports/the-infrared-report-2026/': { imageUrl: 'https://cdn.sanity.io/files/22xmfoma/production/d69b99e5f145c435c45d432cc5aab41b0dc99431.pdf' },
  'https://www.scalevp.com/blog/the-big-data-center-squeeze-getting-more-compute-from-existing-infrastructure': { imageUrl: 'https://cdn.prod.website-files.com/692f28f1d17b8ec4f8005e36/69b1ec4a5ccaa6935fd48079_0370d9c5a62c919e81c31a497bace81c_ai_datacenter.svg' },
  'https://activantcapital.com/research/ai-infra-compute': { imageUrl: 'https://www.activantcapital.com/research-media/ai-infra-compute-cover.png' },
  'https://www.cbinsights.com/research/report/data-center-value-chain-market-map/': { imageUrl: 'https://research-assets.cbinsights.com/2025/12/04120627/DataCenter-ValueChainMarketMap-122025-1.png' },
  'https://newsletter.semianalysis.com/p/clustermax-20-the-industry-standard': { imageUrl: 'https://substack-post-media.s3.amazonaws.com/public/images/4a4defe4-d5db-4916-869d-cf635d58c218_2044x1390.png', title: 'ClusterMAX 2.0 Market View, November 2025' },
  'https://newmarketpitch.com/blogs/news/semiconductor-funding-analysis': { imageUrl: 'https://cdn.shopify.com/s/files/1/0871/5413/1219/files/semiconductor-market-grid.png?v=1771226698' },

  'https://benhamouglobalventures.com/energy-management-market/': { imageUrl: 'https://benhamouglobalventures.com/wp-content/uploads/2025/12/image.png' },
  'https://www.axc.vc/blog-posts/energy-ai': { imageUrl: 'https://cdn.prod.website-files.com/61bb0e97fc835555e722904c/69172fadd9f015da9a294aeb_248b463b.png', newUrl: 'https://www.axc.vc/blog/energy-ai', title: 'AI for Energy in Europe' },
  'https://www.bvp.com/atlas/bessemer-predicts-robotics-and-physical-ai': { imageUrl: 'https://www.bvp.com/assets/uploads/2026/04/Slide-8-Bessemer_Predicts_robotics_report.png' },
  'https://www.bvp.com/atlas/50-startups-transforming-industries-with-physical-ai': { imageUrl: 'https://www.bvp.com/assets/uploads/2026/03/Physical-AI-50-Market-map_1600x900_DESIGN_031226-1.jpg' },
  'https://viewpoints.fov.ventures/p/fov-robotics-market-map-2026': { imageUrl: 'https://beehiiv-images-production.s3.amazonaws.com/uploads/asset/file/9f4a240c-20bc-461f-98c1-626d87f1887a/Full_HD_Resolution.png' },
  'https://www.cbinsights.com/research/the-physical-ai-models-market-map/': { imageUrl: 'https://research-assets.cbinsights.com/2026/01/27114202/The-physical-AI-models-market-map-9-e1769532161569.png' },
  'https://www.insightpartners.com/ideas/the-state-of-the-robotics-ecosystem/': { imageUrl: 'https://www.insightpartners.com/wp-content/uploads/2025/10/Vertical-Robotics-as-a-Service-Market-Map-V3.jpg' },
  'https://avpcap.com/the-global-robotics-race-and-how-robots-actually-work/': { imageUrl: 'https://avpcap.com/wp-content/uploads/2025/10/Robots-2-8.png' },
  // Morgan Stanley "The Humanoid 100" PDF intentionally omitted -- advisor.morganstanley.com
  // blocked every automated fetch attempt (Akamai bot protection), so the existing link
  // could not be confirmed either way. Worth a manual check in a real browser.

  'https://www.madrona.com/voice-is-going-vertical-how-verticalized-voice-ai-is-becoming-the-next-killer-app/': { imageUrl: 'https://www.madrona.com/wp-content/uploads/2025/06/New-version-with-Ultravox.png' },
  'https://www.sierraventures.com/content/voice-ai-market-map': { imageUrl: 'https://www.sierraventures.com/hs-fs/hubfs/Screenshot%202026-01-22%20at%201.49.06%20PM.png', title: 'Transforming Voice: Market Map of 150+ Voice AI Companies' },
  'https://a16z.com/ai-voice-agents-2025-update/': { imageUrl: 'https://d1lamhf6l6yk6d.cloudfront.net/uploads/2025/01/2025-AI-Voice-Agents-INLINE-12-NEW-FINAL-0307.png' },
  'https://lsvp.com/stories/the-future-of-voice-our-thoughts-on-how-it-will-transform-conversational-ai/': { imageUrl: 'https://lsvp.com/wp-content/uploads/2024/09/Voice-AI-market-map-5.png' },
  // NFX "Voice AI Is Working" intentionally omitted -- page has no company-grid market map,
  // just two unrelated conceptual diagrams (timeline, framework circles).

  'https://text.machinecinema.ai/p/ai-creative-market-map-the-tools': { imageUrl: 'https://substack-post-media.s3.amazonaws.com/public/images/e00a0e6f-a1f9-490e-8803-5a68a4a5bd5a_6000x3374.png' },
  'https://a16z.substack.com/p/there-is-no-god-tier-video-model': { imageUrl: 'https://substack-post-media.s3.amazonaws.com/public/images/041c9c1d-006f-493c-9e70-ea2f8f6b31e4_730x827.png' },
  'https://venturemarketmaps.com/m/22-a16z-ai-content-generation-content-editing': { imageUrl: 'https://pbs.twimg.com/media/GGJkoWbbYAAKC9N?format=jpg&name=medium' },
  'https://vcmaps.com/maps/ai-video-generation': { imageUrl: 'https://vcmaps.com/maps/ai-video-generation/opengraph-image?e01b2a43139dce61' },
  'https://vcmaps.com/maps/ai-image-generation': { imageUrl: 'https://vcmaps.com/maps/ai-image-generation/opengraph-image?e01b2a43139dce61' },

  // Foundation Capital "Context Graphs" and Semiconductor Engineering "Startup Funding Q1 2026"
  // intentionally omitted -- both pages confirmed to have no chart/infographic at all, only
  // text/tables and decorative/author images. Nothing to substitute in.
};

async function main() {
  if (!BUCKET) {
    console.error('MARKET_MAP_BUCKET or DI_DOCX_BUCKET must be set.');
    process.exit(1);
  }

  const snap = await db.collection('marketMapEntries').get();
  const entries = snap.docs
    .map((doc) => ({ id: doc.id, ...doc.data() }))
    .filter((d) => CORRECTIONS[d.url]);

  const unmatched = Object.keys(CORRECTIONS).filter((url) => !snap.docs.some((doc) => doc.data().url === url));

  console.log(`${snap.size} total entries, ${entries.length} matched to a correction.${DRY_RUN ? ' (dry run)' : ''}\n`);
  if (unmatched.length) {
    console.log(`WARNING: ${unmatched.length} correction(s) had no matching entry (url changed since this script was written?):`);
    unmatched.forEach((u) => console.log(`  - ${u}`));
    console.log('');
  }

  const results = { ok: [], failed: [] };

  for (const entry of entries) {
    const fix = CORRECTIONS[entry.url];
    process.stdout.write(`- ${entry.firm} — "${entry.title}" (${entry.url})\n`);

    const asset = await fetchBinary(fix.imageUrl);
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
      if (fix.newUrl) update.url = fix.newUrl;
      if (fix.title) update.title = fix.title;
      await db.collection('marketMapEntries').doc(entry.id).update(update);
    }

    const note = fix.newUrl || fix.title ? ' (title/url corrected too)' : '';
    console.log(`    ✓ → ${path} (${asset.contentType}, ${(asset.buffer.length / 1024).toFixed(0)}KB)${note}`);
    results.ok.push(entry.id);

    // Be polite to the sites we're fetching from.
    await new Promise((r) => setTimeout(r, 300));
  }

  console.log(`\n${results.ok.length} succeeded, ${results.failed.length} failed.\n`);
  if (results.failed.length) {
    results.failed.forEach((f) => console.log(`  - [${f.id}] ${f.firm} — "${f.title}" — ${f.url}  (${f.reason})`));
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
