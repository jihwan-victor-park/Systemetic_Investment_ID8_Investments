/**
 * Renders DealStatsDashboard to a standalone HTML file so the dashboard can be
 * LOOKED AT without signing in.
 *
 * Every /docs/* page sits behind real Google sign-in even locally (see
 * middleware.js), and forging a session cookie to peek at a layout is not a
 * trade worth making. This renders the REAL component -- same JSX, same CSS
 * module, same computeDealStats math -- so a layout regression is visible in a
 * browser rather than argued about from source.
 *
 * Run through vitest, which already resolves JSX, CSS modules and the `@/`
 * alias (vitest.config.js) -- no build step, no new dependency:
 *
 *     npm run preview:dashboard                      # built-in fixture data
 *     COMPANIES=path/to/snapshot.json npm run preview:dashboard
 *
 * Writes .preview/dashboard.html (gitignored). A dev tool, not part of the app
 * or the build -- same spirit as scripts/backfill-*.mjs.
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToStaticMarkup } from 'react-dom/server';
import { it } from 'vitest';
import DealStatsDashboard from '../src/components/DealStatsDashboard.jsx';
import { STAGES } from '../src/lib/stages.js';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

// Shaped like a plausible real book: multi-stage membership (so the additive
// stage counts and the pipeline-AND-qualified intersection are both non-trivial),
// a spread across rounds including deliberately messy Series spellings, and a
// chunk with no Series at all -- that bucket is real (48 Attio deals have no
// Deal Date; plenty have no Series either) and the layout has to survive it.
function fixtureCompanies() {
  const mk = (n, stage, tags, round) =>
    Array.from({ length: n }, (_, i) => ({ slug: `${stage}-${round || 'none'}-${i}`, stage, tags, round }));
  return [
    ...mk(14, 'pipeline', ['qualified'], 'Series C'),
    ...mk(9, 'pipeline', ['qualified'], 'Series B'),
    ...mk(6, 'pipeline', ['qualified'], 'Series D'),
    ...mk(11, 'pipeline', [], 'Series B'),
    ...mk(7, 'pipeline', [], null),
    ...mk(21, 'qualified', [], 'Series C'),
    ...mk(16, 'qualified', [], 'series b'),
    ...mk(12, 'qualified', [], 'Series D'),
    ...mk(5, 'qualified', [], 'Series E'),
    ...mk(3, 'qualified', [], 'Growth'),
    ...mk(48, 'watchlist', [], 'Series A'),
    ...mk(37, 'watchlist', [], null),
    ...mk(29, 'radar', [], 'Seed'),
    ...mk(24, 'radar', [], 'B'),
    ...mk(4, 'invested', ['qualified'], 'Series F'),
    ...mk(2, 'invested', [], 'Series H'),
    ...mk(31, 'passed', ['pipeline'], 'Series C'),
    ...mk(18, 'passed', ['pipeline'], null),
    ...mk(6, 'new', [], null),
  ];
}

async function loadCompanies() {
  const file = process.env.COMPANIES;
  if (!file) return fixtureCompanies();
  const raw = JSON.parse(await readFile(resolve(process.cwd(), file), 'utf8'));
  const docs = Array.isArray(raw) ? raw : raw.companies || Object.values(raw);
  // Mirrors the fields lib/companies.js's listCompanies() maps, including its
  // "a doc with no recognized stage reads as qualified" default -- otherwise the
  // preview's totals silently disagree with the real page's for the 20 stage-less
  // docs in production.
  return docs.map((d) => ({
    slug: d.slug || d.id,
    stage: STAGES.includes(d.stage) ? d.stage : 'qualified',
    tags: Array.isArray(d.tags) ? d.tags : [],
    round: d.round ?? null,
    access: d.access === 'access' || d.access === 'no_access' ? d.access : null,
  }));
}

// The tokens the component's CSS references, copied from globals.css rather than
// parsed out of it so this never breaks on an unrelated edit to that file.
const TOKENS = `
  :root {
    --id8-paper: #FBFAF7; --id8-ink: #1A1A1A; --id8-grey: #828282; --id8-soft: #3C3C3C;
    --id8-hair: #E4DFD5; --id8-card: #FFFFFF; --id8-accent: #112ED4; --id8-fresh-dot: #00D95C;
    --id8-shadow: 0 1px 2px rgba(26,26,26,.04), 0 6px 16px rgba(26,26,26,.05);
    --id8-shadow-hover: 0 2px 4px rgba(26,26,26,.05), 0 10px 22px rgba(26,26,26,.08);
  }
  body { margin: 0; background: var(--id8-paper); color: var(--id8-ink);
         font-family: 'Roboto Serif', Georgia, serif; -webkit-font-smoothing: antialiased; }
  /* Matches the real docs content column so the preview's line lengths and card
     widths are the ones a user actually sees. */
  .previewShell { max-width: 1100px; margin: 0 auto; padding: 32px 28px 64px; }
  a { color: inherit; text-decoration: none; }
`;

// Wrapped in it() purely so vitest runs it -- this is a generator, not a test,
// and it asserts nothing beyond "the component renders without throwing", which
// is itself worth catching.
it('writes .preview/dashboard.html', async () => {
  const companies = await loadCompanies();
  const body = renderToStaticMarkup(<DealStatsDashboard companies={companies} />);
  const css = await readFile(resolve(ROOT, 'src/components/DealStatsDashboard.module.css'), 'utf8');
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard preview — ID8 hub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600&family=Roboto+Serif:wght@400;600&display=swap">
<style>${TOKENS}${css}</style>
</head><body><div class="previewShell">${body}</div></body></html>`;

  await mkdir(resolve(ROOT, '.preview'), { recursive: true });
  const out = resolve(ROOT, '.preview/dashboard.html');
  await writeFile(out, html);
  console.log(`\n  ${companies.length} companies -> ${out}\n`);
});
