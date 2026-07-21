'use client';

import { useMemo } from 'react';
import { STAGE_LABELS } from '@/lib/stages';
import styles from './StageCategoryGraph.module.css';

const VIEW_W = 720;
const VIEW_H = 440;
const NODE_W = 150;
const PAD = 24;
const GAP = 8;

// Stroke color per source stage -- there are only ever 4 of these, so a
// fixed map (rather than a generated palette) keeps every render's colors
// stable and legible, same reasoning as PortfolioGraph's fixed fit-score
// gradient.
const STAGE_COLOR = {
  new: 'var(--id8-grey)',
  watchlist: 'var(--id8-soft)',
  pipeline: 'var(--id8-accent)',
  qualified: 'var(--id8-ink)',
};

// Two-column flow diagram: stage on the left, Radar Category on the right,
// one ribbon per non-empty (stage, category) pair. Ribbon thickness and node
// height both encode company count. Drawn as stroked bezier curves (not
// filled Sankey ribbons) -- same "line weight is the signal" language
// PortfolioGraph already uses for fit score, just simpler geometry, since a
// full filled-ribbon Sankey isn't needed to read the flow at this node count.
export default function StageCategoryGraph({ flows, stages, categories }) {
  const totalByStage = useMemo(() => {
    const m = {};
    for (const s of stages) m[s] = flows.filter((f) => f.stage === s).reduce((a, f) => a + f.count, 0);
    return m;
  }, [flows, stages]);

  const totalByCategory = useMemo(() => {
    const m = {};
    for (const c of categories) m[c] = flows.filter((f) => f.category === c).reduce((a, f) => a + f.count, 0);
    return m;
  }, [flows, categories]);

  const grandTotal = flows.reduce((a, f) => a + f.count, 0) || 1;
  const availableH = Math.max(1, VIEW_H - PAD * 2 - GAP * Math.max(0, stages.length - 1));
  const availableHCat = Math.max(1, VIEW_H - PAD * 2 - GAP * Math.max(0, categories.length - 1));
  const scale = availableH / grandTotal;
  const scaleCat = availableHCat / grandTotal;

  const stageLayout = {};
  let y = PAD;
  for (const s of stages) {
    const h = Math.max(3, totalByStage[s] * scale);
    stageLayout[s] = { y, h };
    y += h + GAP;
  }

  const catLayout = {};
  let yc = PAD;
  for (const c of categories) {
    const h = Math.max(3, totalByCategory[c] * scaleCat);
    catLayout[c] = { y: yc, h };
    yc += h + GAP;
  }

  const stageOffset = Object.fromEntries(stages.map((s) => [s, 0]));
  const catOffset = Object.fromEntries(categories.map((c) => [c, 0]));

  const ribbons = flows
    .filter((f) => f.count > 0)
    .map((f) => {
      const sLayout = stageLayout[f.stage];
      const cLayout = catLayout[f.category];
      const thickness = Math.max(1.5, f.count * scale);
      const cThickness = Math.max(1.5, f.count * scaleCat);
      const sY = sLayout.y + stageOffset[f.stage] + thickness / 2;
      const cY = cLayout.y + catOffset[f.category] + cThickness / 2;
      stageOffset[f.stage] += thickness;
      catOffset[f.category] += cThickness;
      const x1 = NODE_W;
      const x2 = VIEW_W - NODE_W;
      const midX = (x1 + x2) / 2;
      return {
        key: `${f.stage}__${f.category}`,
        d: `M ${x1} ${sY} C ${midX} ${sY} ${midX} ${cY} ${x2} ${cY}`,
        thickness: Math.max(thickness, cThickness),
        color: STAGE_COLOR[f.stage] || 'var(--id8-grey)',
      };
    });

  return (
    <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className={styles.svg}>
      {ribbons.map((r) => (
        <path key={r.key} d={r.d} fill="none" stroke={r.color} strokeWidth={r.thickness} strokeLinecap="round" opacity={0.45} />
      ))}
      {stages.map((s) => (
        <g key={s}>
          <rect x={0} y={stageLayout[s].y} width={NODE_W - 12} height={stageLayout[s].h} rx="2" fill="var(--id8-card)" stroke="var(--id8-hair)" />
          <text x={(NODE_W - 12) / 2} y={stageLayout[s].y + stageLayout[s].h / 2 + 4} textAnchor="middle" className={styles.label}>
            {STAGE_LABELS[s] || s} ({totalByStage[s]})
          </text>
        </g>
      ))}
      {categories.map((c) => (
        <g key={c}>
          <rect x={VIEW_W - NODE_W + 12} y={catLayout[c].y} width={NODE_W - 12} height={catLayout[c].h} rx="2" fill="var(--id8-accent-bg)" stroke="var(--id8-accent)" />
          <text x={VIEW_W - NODE_W + 12 + (NODE_W - 12) / 2} y={catLayout[c].y + catLayout[c].h / 2 + 4} textAnchor="middle" className={styles.label}>
            {c} ({totalByCategory[c]})
          </text>
        </g>
      ))}
    </svg>
  );
}
