/**
 * Prints computeDealStats' numbers for a companies snapshot, so a figure on the
 * dashboard can be checked against the data without signing in or reading it off
 * a screenshot. Same harness as preview-dashboard.jsx (vitest resolves the `@/`
 * alias and JSX; see that file's header for why).
 *
 *     COMPANIES=path/to/companies.json npm run preview:stats
 *
 * Asserts the internal consistency that a reader will check by eye: the series
 * table's MANDATE / PIPELINE columns must sum to the same totals the headline
 * tiles show, or one of the two is lying.
 */
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { expect, it } from 'vitest';
import { computeDealStats } from '../src/lib/dealStats.js';
import { STAGES } from '../src/lib/stages.js';

it('reports and cross-checks the dashboard figures', async () => {
  const file = process.env.COMPANIES;
  if (!file) throw new Error('set COMPANIES=path/to/companies.json');
  const raw = JSON.parse(await readFile(resolve(process.cwd(), file), 'utf8'));
  const docs = Array.isArray(raw) ? raw : raw.companies || Object.values(raw);
  const companies = docs.map((d) => ({
    slug: d.slug || d.id,
    stage: STAGES.includes(d.stage) ? d.stage : 'qualified',
    tags: Array.isArray(d.tags) ? d.tags : [],
    round: d.round ?? null,
  }));

  const { total, byStage, bySeries, mandate } = computeDealStats(companies);
  const sum = (k) => bySeries.reduce((s, r) => s + r[k], 0);

  const lines = [
    '',
    `  deals tracked        ${total}`,
    `  qualified            ${mandate.qualifiedCount}`,
    `  in pipeline          ${mandate.pipelineCount}`,
    `  mandate (q u p)      ${mandate.mandateTotal}`,
    `  access rate          ${Math.round(mandate.pct)}%`,
    `  qualified + pipeline ${mandate.converted.both} (${Math.round(mandate.converted.pct)}%)`,
    `  untriaged            ${mandate.needsTriageCount}`,
    '',
    '  by stage:',
    ...byStage.map((r) => `    ${r.label.padEnd(16)} ${r.count}`),
    '',
    '  by series:            count  mandate  qualified  pipeline',
    ...bySeries.map((r) => `    ${r.label.padEnd(16)} ${String(r.count).padStart(6)}`
      + `${String(r.mandate).padStart(9)}${String(r.qualified).padStart(11)}${String(r.pipeline).padStart(10)}`),
    '',
    `  series count   sums to ${sum('count')}   (deals tracked ${total})`,
    `  series mandate sums to ${sum('mandate')}   (mandate ${mandate.mandateTotal})`,
    `  series pipeline sums to ${sum('pipeline')}  (in pipeline ${mandate.pipelineCount})`,
    '',
  ];
  console.log(lines.join('\n'));

  // Every company lands in exactly one series bucket, so each column must sum
  // to its headline. A mismatch means the fold is dropping or double-counting a
  // bucket -- which is invisible on the page itself, since the reader has no
  // reason to add up a column.
  expect(sum('count')).toBe(total);
  expect(sum('mandate')).toBe(mandate.mandateTotal);
  expect(sum('pipeline')).toBe(mandate.pipelineCount);
  expect(sum('qualified')).toBe(mandate.qualifiedCount);
});
