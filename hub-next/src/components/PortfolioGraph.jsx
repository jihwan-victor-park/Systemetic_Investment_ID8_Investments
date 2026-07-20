'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { companyHref, lookupFitScore } from '@/lib/companyIndex';
import styles from './PortfolioGraph.module.css';

const SERIES_ORDER = { seed: 0, 'series a': 1, 'series b': 2, 'series c': 3, 'series d': 4, 'series e': 5 };
function seriesRank(s) {
  if (!s) return null;
  const r = SERIES_ORDER[s.trim().toLowerCase()];
  return r === undefined ? null : r;
}

const SERIES_OPTIONS = ['any', 'seed', 'series a', 'series b', 'series c'];
const SERIES_LABEL = { any: 'Any', seed: 'Seed+', 'series a': 'Series A+', 'series b': 'Series B+', 'series c': 'Series C+' };

// Real hub-and-spoke portfolio graph -- the VC at the center, one line per
// portfolio company, arranged in a full circle (not a one-sided list).
// Line weight + color-mix encode the company's own ID8 Stage 1 fit score
// (1-4 rubric, gate at 3.0) -- cross-referenced live from `companyIndex`
// (built server-side from the real companies/screens collection), never
// invented. A company we haven't screened renders as a thin grey dashed
// line, spanning the full 1-4 range so a 1.0 reads as true grey and a 4.0
// as full electric blue.
export default function PortfolioGraph({ vcName, portfolio, companyIndex }) {
  const router = useRouter();
  const industries = useMemo(
    () => [...new Set(portfolio.map((p) => p.industry).filter(Boolean))].sort(),
    [portfolio],
  );
  const [activeIndustries, setActiveIndustries] = useState(() => new Set(industries));
  const [minSeries, setMinSeries] = useState('any');

  function toggleIndustry(ind) {
    setActiveIndustries((prev) => {
      const next = new Set(prev);
      if (next.has(ind)) next.delete(ind); else next.add(ind);
      return next;
    });
  }

  const enriched = portfolio.map((p) => ({
    ...p,
    fitScore: lookupFitScore(companyIndex, p.company),
    href: companyHref(companyIndex, p.company) || `/docs/vcs/company/${encodeURIComponent(p.company)}`,
  }));

  const minRank = minSeries === 'any' ? -1 : SERIES_ORDER[minSeries];
  const visible = enriched.filter((p) => {
    if (p.industry && !activeIndustries.has(p.industry)) return false;
    if (minRank >= 0) {
      const r = seriesRank(p.series);
      if (r === null || r < minRank) return false;
    }
    return true;
  });

  const n = visible.length;
  const nodeW = 96, nodeH = 36, vcW = 96, vcH = 46;
  const radius = Math.min(210, Math.max(125, 90 + n * 16));
  const pad = Math.max(nodeW, nodeH) / 2 + 24;
  const W = radius * 2 + pad * 2, H = radius * 2 + pad * 2;
  const cx = W / 2, cy = H / 2;

  const nodes = visible.map((p, i) => {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2; // start at top, clockwise
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);
    const hasScore = p.fitScore != null;
    // Maps the rubric's real floor/ceiling (1 -> 4, not 0 -> 4) onto 0-100%
    // so a 1.0 renders as true grey and a 4.0 as full electric blue -- the
    // whole scale is used, not just its top three-quarters.
    const pct = hasScore ? Math.max(0, Math.min(100, ((p.fitScore - 1) / 3) * 100)) : 0;
    const strokeWidth = hasScore ? 1.5 + (pct / 100) * 6 : 1.5;
    const stroke = hasScore
      ? `color-mix(in srgb, var(--id8-accent) ${Math.round(pct)}%, var(--id8-grey) ${100 - Math.round(pct)}%)`
      : 'var(--id8-hair)';
    const len = Math.hypot(x - cx, y - cy);
    return { ...p, x, y, hasScore, strokeWidth, stroke, len, delay: i * 45 };
  });

  return (
    <div className={styles.wrap}>
      <div className={styles.filters}>
        <div className={styles.groupLabel}>Industry</div>
        {industries.length
          ? industries.map((ind) => (
            <label key={ind} className={styles.check}>
              <input type="checkbox" checked={activeIndustries.has(ind)} onChange={() => toggleIndustry(ind)} />
              {ind}
            </label>
          ))
          : <p className={styles.empty}>No industry data</p>}

        <div className={styles.groupLabel} style={{ marginTop: 14 }}>Minimum series</div>
        {SERIES_OPTIONS.map((s) => (
          <label key={s} className={styles.radio}>
            <input type="radio" name="minSeries" checked={minSeries === s} onChange={() => setMinSeries(s)} />
            {SERIES_LABEL[s]}
          </label>
        ))}
      </div>

      <div className={styles.canvas}>
        {n === 0 ? (
          <p className={styles.empty}>No portfolio companies match these filters.</p>
        ) : (
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={Math.min(H, 460)} className={styles.svg}>
            {nodes.map((node) => (
              <line
                key={`edge-${node.company}`}
                className={node.hasScore ? styles.edge : undefined}
                x1={cx} y1={cy} x2={node.x} y2={node.y}
                stroke={node.stroke}
                strokeWidth={node.strokeWidth}
                strokeDasharray={node.hasScore ? undefined : '4 4'}
                strokeLinecap="round"
                style={node.hasScore ? { '--len': `${node.len}px`, animationDelay: `${node.delay}ms` } : undefined}
              />
            ))}

            <g className={`${styles.node} ${styles.vcNode}`}>
              <rect className={styles.nodeShape} x={cx - vcW / 2} y={cy - vcH / 2} width={vcW} height={vcH} rx="2" fill="var(--id8-ink)" />
              <text x={cx} y={cy + 5} textAnchor="middle" className={styles.vcLabel}>{vcName}</text>
            </g>

            {nodes.map((node) => (
              <g
                key={node.company}
                className={styles.node}
                style={{ animationDelay: `${node.delay + 70}ms` }}
                role="link"
                tabIndex={0}
                onClick={() => router.push(node.href)}
                onKeyDown={(e) => { if (e.key === 'Enter') router.push(node.href); }}
              >
                <rect
                  className={styles.nodeShape}
                  x={node.x - nodeW / 2} y={node.y - nodeH / 2} width={nodeW} height={nodeH} rx="2"
                  fill={node.hasScore ? 'var(--id8-accent-bg)' : 'var(--id8-card)'}
                  stroke={node.hasScore ? 'var(--id8-accent)' : 'var(--id8-hair)'}
                />
                <text x={node.x} y={node.y - 3} textAnchor="middle" className={styles.label}>{node.company}</text>
                <text x={node.x} y={node.y + 11} textAnchor="middle" className={styles.sublabel}>
                  {node.series || '—'}{node.hasScore ? ` · ${node.fitScore.toFixed(1)} / 4` : ' · not scored'}
                </text>
                <title>
                  {node.company} — {node.industry || 'unknown industry'}, {node.series || 'stage unknown'}
                  {node.hasScore
                    ? `, fit score ${node.fitScore.toFixed(1)} / 4${node.fitScore >= 3 ? ' (clears gate)' : ''}`
                    : ', not yet screened against our rubric'}
                </title>
              </g>
            ))}
          </svg>
        )}
      </div>
    </div>
  );
}
