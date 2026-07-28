'use client';

import { useEffect, useMemo, useRef } from 'react';
import styles from './SignalField.module.css';

// Latent Order signal field: faint lattice + an emergent, harmonic constellation.
// Draws itself in once on mount; every node can be dragged and its lines follow live.
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hashStr(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

const FX = 16, FY = 16, STEP = 38, COLS = 27;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const MARGIN = 10;

// ROWS is the only thing that varies between the desktop and mobile layouts
// -- ROWS/H taller gives the lattice and its nodes more vertical room to
// spread into, same column grid (and so the same width) either way.
function generate(seed, rows) {
  const rng = mulberry32(hashStr(seed));
  const gx = c => FX + c * STEP, gy = r => FY + r * STEP;
  const count = 8 + Math.floor(rng() * 3);
  const keys = 'abcdefghij'.split('').slice(0, count);
  const band = (COLS - 2) / count;
  let row = 1.5 + rng() * (rows - 3);
  const pos = {};
  keys.forEach((k, i) => {
    const col = clamp(1 + i * band + (rng() - 0.5) * band * 0.7, 1, COLS - 1);
    row = clamp(row + (rng() - 0.5) * 3.0, 1, rows - 1);   // smooth walk = harmonic
    pos[k] = [gx(col), gy(row)];
  });
  const order = [...keys].sort((a, b) => pos[a][0] - pos[b][0]);
  const edges = [];
  for (let i = 0; i < order.length - 1; i++) edges.push([order[i], order[i + 1]]);
  const branches = 1 + Math.floor(rng() * 2);
  for (let b = 0; b < branches; b++) { const i = Math.floor(rng() * (order.length - 2)); edges.push([order[i], order[i + 2]]); }
  // highlight the most-connected nodes
  const deg = {}; keys.forEach(k => (deg[k] = 0));
  edges.forEach(([a, b]) => { deg[a]++; deg[b]++; });
  const sig = [...keys].sort((a, b) => deg[b] - deg[a]).slice(0, 2);
  return { keys, pos, edges, sig };
}

function linePath(A, B) {
  return `M${A[0].toFixed(1)} ${A[1].toFixed(1)} L${B[0].toFixed(1)} ${B[1].toFixed(1)}`;
}

function Field({ seed, rows, wrapClassName }) {
  const W = FX * 2 + COLS * STEP, H = FY * 2 + rows * STEP;
  const G = useMemo(() => generate(seed, rows), [seed, rows]);
  const svgRef = useRef(null);
  const posRef = useRef({});
  const nodeEl = useRef({});
  const edgeEl = useRef({});
  const ringEl = useRef({});
  const adjacency = useRef({});
  const dragKey = useRef(null);
  const dragOffset = useRef([0, 0]);

  useEffect(() => {
    posRef.current = { ...G.pos };
    const map = {};
    G.edges.forEach(([a, b], i) => {
      (map[a] ||= []).push(i);
      (map[b] ||= []).push(i);
    });
    adjacency.current = map;
  }, [G]);

  const redrawEdge = (i) => {
    const el = edgeEl.current[i]; if (!el) return;
    const [a, b] = G.edges[i];
    el.setAttribute('d', linePath(posRef.current[a], posRef.current[b]));
  };

  const toSvgPoint = (clientX, clientY) => {
    const svg = svgRef.current;
    const ctm = svg && svg.getScreenCTM();
    if (!ctm) return [clientX, clientY];
    const pt = svg.createSVGPoint();
    pt.x = clientX; pt.y = clientY;
    const p = pt.matrixTransform(ctm.inverse());
    return [p.x, p.y];
  };

  const onPointerDown = (key) => (e) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    const [sx, sy] = toSvgPoint(e.clientX, e.clientY);
    const [nx, ny] = posRef.current[key];
    dragKey.current = key;
    dragOffset.current = [nx - sx, ny - sy];
  };

  const onPointerMove = (e) => {
    const key = dragKey.current; if (!key) return;
    const [sx, sy] = toSvgPoint(e.clientX, e.clientY);
    const [ox, oy] = dragOffset.current;
    const x = clamp(sx + ox, MARGIN, W - MARGIN);
    const y = clamp(sy + oy, MARGIN, H - MARGIN);
    posRef.current[key] = [x, y];
    const node = nodeEl.current[key];
    if (node) { node.setAttribute('cx', x); node.setAttribute('cy', y); }
    const hit = nodeEl.current[`hit-${key}`];
    if (hit) { hit.setAttribute('cx', x); hit.setAttribute('cy', y); }
    (adjacency.current[key] || []).forEach(redrawEdge);
    (ringEl.current[key] || []).forEach(el => { el.setAttribute('cx', x); el.setAttribute('cy', y); });
  };

  const onPointerUp = (e) => {
    if (dragKey.current) e.currentTarget.releasePointerCapture?.(e.pointerId);
    dragKey.current = null;
  };

  const ticks = [];
  for (let c = 0; c <= COLS; c++) for (let r = 0; r <= rows; r++) {
    const x = FX + c * STEP, y = FY + r * STEP;
    ticks.push(<path key={`${c}-${r}`} d={`M${x - 2.4} ${y}H${x + 2.4}M${x} ${y - 2.4}V${y + 2.4}`} stroke="var(--id8-hair)" strokeWidth="1" />);
  }

  return (
    <div className={wrapClassName}>
      <svg
        ref={svgRef}
        className={styles.field}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        role="img"
        aria-label="A constellation of connected nodes representing ID8's systems. Each point can be dragged."
      >
        <g>{ticks}</g>
        {G.edges.map(([a, b], i) => (
          <path
            key={`e${i}`}
            ref={el => (edgeEl.current[i] = el)}
            className={styles.edge}
            style={{ '--d': `${180 + i * 90}ms` }}
            d={linePath(G.pos[a], G.pos[b])}
            pathLength="100"
          />
        ))}
        {G.sig.map(k => (
          <g key={`s${k}`} ref={el => { if (el) ringEl.current[k] = Array.from(el.children); }}>
            <circle className={styles.ring1} style={{ '--d': '620ms' }} cx={G.pos[k][0]} cy={G.pos[k][1]} r="18" />
            <circle className={styles.ring2} style={{ '--d': '680ms' }} cx={G.pos[k][0]} cy={G.pos[k][1]} r="30" />
          </g>
        ))}
        {G.keys.map((k, idx) => {
          const isHub = G.sig.includes(k);
          return (
            <g key={`n${k}`}>
              <circle
                ref={el => (nodeEl.current[k] = el)}
                className={isHub ? styles.nodeHub : styles.node}
                style={{ '--d': `${idx * 55}ms` }}
                cx={G.pos[k][0]} cy={G.pos[k][1]}
                r={isHub ? 5.5 : 4}
              />
              <circle
                ref={el => (nodeEl.current[`hit-${k}`] = el)}
                className={styles.hit}
                cx={G.pos[k][0]} cy={G.pos[k][1]}
                r={12}
                onPointerDown={onPointerDown(k)}
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// Renders both a desktop and a taller mobile layout and lets a media query
// pick which one is visible/interactive -- same reasoning as QualityFunnel
// and ConnectGraph: no client-side breakpoint check needed, and a
// display:none copy can't receive pointer events, so the hidden instance's
// drag handlers are harmless dead weight, not a real interaction risk.
export default function SignalField({ seed = 'id8' }) {
  return (
    <>
      <Field seed={seed} rows={7} wrapClassName={styles.desktopOnly} />
      <Field seed={seed} rows={13} wrapClassName={styles.mobileOnly} />
    </>
  );
}
