'use client';

import { useEffect, useMemo, useRef } from 'react';
import styles from './ConnectGraph.module.css';

// "We connect the dots." Nodes appear, lines draw in, and the most-connected
// nodes light up black (like the hero). Loops seamlessly.
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hashStr(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

const W = 1000, H = 300, M = 80;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function generate(seed) {
  const rng = mulberry32(hashStr(seed));
  const N = 11, nodes = [];
  let tries = 0;
  while (nodes.length < N && tries < 500) {
    tries++;
    const x = M + rng() * (W - 2 * M), y = 40 + rng() * (H - 110);
    if (nodes.every(n => Math.hypot(n.x - x, n.y - y) > 115)) nodes.push({ x, y });
  }
  const set = new Set(), edges = [];
  const add = (a, b) => { const k = a < b ? `${a}-${b}` : `${b}-${a}`; if (!set.has(k)) { set.add(k); edges.push([a, b]); } };
  nodes.forEach((n, i) => {
    const near = nodes.map((m, j) => ({ j, d: Math.hypot(m.x - n.x, m.y - n.y) })).filter(o => o.j !== i).sort((a, b) => a.d - b.d);
    add(i, near[0].j);
    if (rng() < 0.5 && near[1]) add(i, near[1].j);
  });
  const deg = nodes.map(() => 0); edges.forEach(([a, b]) => { deg[a]++; deg[b]++; });
  const hubs = deg.map((d, i) => ({ i, d })).sort((a, b) => b.d - a.d).slice(0, 2).map(o => o.i);
  return { nodes, edges, hubs };
}

export default function ConnectGraph({ seed = 'connect' }) {
  const G = useMemo(() => generate(seed), [seed]);
  const nodeEl = useRef([]); const edgeEl = useRef([]); const ringEl = useRef([]);
  const PAPER = useRef('#FBFAF7'); const INK = useRef('#1A1A1A');

  useEffect(() => {
    const cs = getComputedStyle(document.documentElement);
    PAPER.current = cs.getPropertyValue('--id8-paper').trim() || '#FBFAF7';
    INK.current = cs.getPropertyValue('--id8-ink').trim() || '#1A1A1A';
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      // static: show the finished graph
      G.edges.forEach((_, k) => { const el = edgeEl.current[k]; if (el) { el.setAttribute('x2', G.nodes[G.edges[k][1]].x); el.setAttribute('y2', G.nodes[G.edges[k][1]].y); el.setAttribute('opacity', '0.8'); } });
      G.nodes.forEach((n, i) => { const el = nodeEl.current[i]; if (el) { el.setAttribute('opacity', '1'); el.setAttribute('fill', G.hubs.includes(i) ? INK.current : PAPER.current); } });
      return;
    }
    const D = 9; let t0 = 0, raf;
    const E = G.edges.length;
    const loop = ts => {
      if (!t0) t0 = ts;
      const tau = (((ts - t0) / 1000) % D) / D;
      const tail = tau > 0.86 ? clamp(1 - (tau - 0.86) / 0.14, 0, 1) : 1;

      G.nodes.forEach((n, i) => {
        const el = nodeEl.current[i]; if (!el) return;
        const appear = (i / G.nodes.length) * 0.10;
        const op = clamp((tau - appear) / 0.06, 0, 1) * tail;
        const lit = G.hubs.includes(i) && tau > 0.55;
        el.setAttribute('opacity', op.toFixed(3));
        el.setAttribute('r', G.hubs.includes(i) ? 5.5 : 4);
        el.setAttribute('fill', lit ? INK.current : PAPER.current);
      });

      G.edges.forEach(([a, b], k) => {
        const el = edgeEl.current[k]; if (!el) return;
        const start = 0.16 + (k / E) * 0.30;
        const p = clamp((tau - start) / 0.10, 0, 1);
        const A = G.nodes[a], B = G.nodes[b];
        el.setAttribute('x2', (A.x + (B.x - A.x) * p).toFixed(1));
        el.setAttribute('y2', (A.y + (B.y - A.y) * p).toFixed(1));
        el.setAttribute('opacity', (p > 0 ? 0.82 * tail : 0).toFixed(3));
      });

      G.hubs.forEach((hi, h) => {
        const n = G.nodes[hi];
        const k = clamp((tau - 0.55) / 0.20, 0, 1);
        [0, 1].forEach(r => {
          const el = ringEl.current[h * 2 + r]; if (!el) return;
          el.setAttribute('cx', n.x); el.setAttribute('cy', n.y);
          el.setAttribute('r', (10 + r * 10 + k * 14).toFixed(1));
          el.setAttribute('opacity', (0.32 * (1 - k) * tail).toFixed(3));
        });
      });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [G]);

  const ticks = [];
  for (let x = 24; x <= W - 24; x += 40) for (let y = 24; y <= H - 24; y += 40) {
    ticks.push(<path key={`${x}-${y}`} className={styles.tick} d={`M${x - 2.4} ${y}H${x + 2.4}M${x} ${y - 2.4}V${y + 2.4}`} />);
  }

  return (
    <div className={styles.wrap}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
        <g>{ticks}</g>
        {G.edges.map(([a], k) => (
          <line key={`e${k}`} className={styles.link} ref={el => (edgeEl.current[k] = el)}
            x1={G.nodes[a].x} y1={G.nodes[a].y} x2={G.nodes[a].x} y2={G.nodes[a].y} opacity="0" />
        ))}
        {G.hubs.map((hi, h) => [0, 1].map(r => (
          <circle key={`r${h}-${r}`} className={styles.ring} ref={el => (ringEl.current[h * 2 + r] = el)}
            cx={G.nodes[hi].x} cy={G.nodes[hi].y} r={10} opacity="0" />
        )))}
        {G.nodes.map((n, i) => (
          <circle key={`n${i}`} className={styles.node} ref={el => (nodeEl.current[i] = el)}
            cx={n.x} cy={n.y} r={4} fill="var(--id8-paper)" opacity="0" />
        ))}
      </svg>
    </div>
  );
}
