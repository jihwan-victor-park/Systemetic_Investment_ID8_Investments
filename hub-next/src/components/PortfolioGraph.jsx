'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
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

// Fixed viewport in local SVG units -- panning/zooming only ever moves the
// inner <g> transform, never this. That's what lets the map hold 100+
// companies without cramming: the world can be arbitrarily large, the
// window onto it stays constant.
const VIEW_W = 880, VIEW_H = 520;
const MIN_SCALE = 0.28, MAX_SCALE = 3.2;

// Concentric-ring layout: each ring's node capacity is however many fit at
// `spacing` along its own circumference, so density never causes overlap
// regardless of portfolio size -- 3 companies and 300 both just place
// correctly, the canvas grows outward (panned/zoomed into) instead of the
// per-node size shrinking to fit a fixed box. Alternate rings are rotated
// half a step so nodes don't line up in radial spokes.
function layoutRings(list, startRadius, spacing = 90, ringGap = 100) {
  const out = [];
  let idx = 0, radius = startRadius, ring = 0;
  while (idx < list.length) {
    const capacity = Math.max(1, Math.floor((2 * Math.PI * radius) / spacing));
    const count = Math.min(capacity, list.length - idx);
    const offset = ring % 2 === 1 ? Math.PI / count : 0;
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2 - Math.PI / 2 + offset;
      out.push({ ...list[idx + i], x: radius * Math.cos(angle), y: radius * Math.sin(angle) });
    }
    idx += count;
    radius += ringGap;
    ring += 1;
  }
  return out;
}

function clientToLocal(svgEl, clientX, clientY) {
  const rect = svgEl.getBoundingClientRect();
  return {
    x: ((clientX - rect.left) / rect.width) * VIEW_W,
    y: ((clientY - rect.top) / rect.height) * VIEW_H,
  };
}

// Real hub-and-spoke portfolio map -- the VC at the center, one line per
// portfolio company, laid out in rings so it scales from a handful of
// companies to hundreds without redesign. Drag to pan, scroll/pinch or the
// +/- controls to zoom, click a company to select it (a detail card opens;
// nothing navigates until you actually choose "View company") -- clicking
// while mid-drag is suppressed so panning across a node never yanks you
// away. Line weight + color-mix encode the company's own ID8 Stage 1 fit
// score (1-4 rubric, gate at 3.0), cross-referenced live from `companyIndex`
// (built server-side from the real companies/screens collection) -- never
// invented. Not yet screened renders as a thin grey dashed line.
export default function PortfolioGraph({ vcName, portfolio, companyIndex }) {
  const svgRef = useRef(null);
  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, startViewX: 0, startViewY: 0, moved: 0 });
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const [selectedName, setSelectedName] = useState(null);
  const [hoveredName, setHoveredName] = useState(null);

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

  const vcSize = useMemo(() => {
    const w = Math.min(240, Math.max(120, vcName.length * 7.8 + 40));
    return { w, h: 56 };
  }, [vcName]);

  const nodes = useMemo(() => {
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
    const startRadius = Math.max(150, vcSize.w / 2 + 100);
    return layoutRings(visible, startRadius).map((p, i) => {
      const hasScore = p.fitScore != null;
      // Maps the rubric's real floor/ceiling (1 -> 4, not 0 -> 4) onto
      // 0-100% so a 1.0 renders as true grey and a 4.0 as full electric
      // blue -- the whole scale is used, not just its top three-quarters.
      const pct = hasScore ? Math.max(0, Math.min(100, ((p.fitScore - 1) / 3) * 100)) : 0;
      return {
        ...p,
        hasScore,
        w: Math.min(170, Math.max(64, p.company.length * 6.3 + 22)),
        h: 28,
        // Color is the primary signal; width only thickens a little (1.75px
        // -> 4px) so a crowded map doesn't turn into a tangle of fat lines
        // that drown out everything else.
        strokeWidth: hasScore ? 1.75 + (pct / 100) * 2.25 : 1.5,
        stroke: hasScore
          ? `color-mix(in srgb, var(--id8-accent) ${Math.round(pct)}%, var(--id8-grey) ${100 - Math.round(pct)}%)`
          : 'var(--id8-hair)',
        len: Math.hypot(p.x, p.y),
        angleDeg: Math.atan2(p.y, p.x) * (180 / Math.PI),
        delay: Math.min(i, 20) * 22,
      };
    });
  }, [portfolio, companyIndex, activeIndustries, minSeries, vcSize.w]);

  // Hover shows the card transiently (updates live as you move between
  // nodes); a click pins it (setSelectedName), which is what keeps it open
  // once the pointer leaves -- useful on touch, or to keep looking at one
  // company's detail while your cursor wanders elsewhere on the map.
  const shownName = hoveredName || selectedName;
  const shown = shownName ? nodes.find((node) => node.company === shownName) || null : null;

  // Wheel-zoom needs a non-passive listener to preventDefault (stop the
  // page itself from scrolling) -- React's onWheel can't reliably do that,
  // so this attaches directly to the DOM node.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    function onWheel(e) {
      e.preventDefault();
      const local = clientToLocal(el, e.clientX, e.clientY);
      setView((v) => {
        const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
        const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor));
        const worldX = (local.x - VIEW_W / 2 - v.x) / v.scale;
        const worldY = (local.y - VIEW_H / 2 - v.y) / v.scale;
        return {
          scale: nextScale,
          x: local.x - VIEW_W / 2 - worldX * nextScale,
          y: local.y - VIEW_H / 2 - worldY * nextScale,
        };
      });
    }
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  function handlePointerDown(e) {
    dragRef.current = { dragging: true, startX: e.clientX, startY: e.clientY, startViewX: view.x, startViewY: view.y, moved: 0 };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function handlePointerMove(e) {
    const d = dragRef.current;
    if (!d.dragging) return;
    const rect = svgRef.current.getBoundingClientRect();
    const dxScreen = e.clientX - d.startX;
    const dyScreen = e.clientY - d.startY;
    d.moved = Math.max(d.moved, Math.hypot(dxScreen, dyScreen));
    setView((v) => ({
      ...v,
      x: d.startViewX + (dxScreen / rect.width) * VIEW_W,
      y: d.startViewY + (dyScreen / rect.height) * VIEW_H,
    }));
  }
  function handlePointerUp() {
    dragRef.current.dragging = false;
  }
  function zoomBy(factor) {
    setView((v) => ({ ...v, scale: Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor)) }));
  }
  function resetView() {
    setView({ x: 0, y: 0, scale: 1 });
  }

  function selectNode(node) {
    if (dragRef.current.moved > 6) return; // a drag that happened to end on a node isn't a click
    setSelectedName(node.company);
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.filters}>
        <div className={styles.groupLabel}>Industry</div>
        {industries.length ? (
          <div className={styles.chips}>
            {industries.map((ind) => (
              <button
                key={ind}
                type="button"
                className={`${styles.chip} ${activeIndustries.has(ind) ? styles.chipActive : ''}`}
                onClick={() => toggleIndustry(ind)}
              >
                {ind}
              </button>
            ))}
          </div>
        ) : <p className={styles.empty}>No industry data</p>}

        <div className={styles.groupLabel} style={{ marginTop: 16 }}>Minimum series</div>
        <div className={styles.seriesList}>
          {SERIES_OPTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className={`${styles.seriesBtn} ${minSeries === s ? styles.seriesActive : ''}`}
              onClick={() => setMinSeries(s)}
            >
              {SERIES_LABEL[s]}
            </button>
          ))}
        </div>

        <div className={styles.groupLabel} style={{ marginTop: 16 }}>Fit score</div>
        <div className={styles.legend}>
          <div className={styles.legendBar}><div className={styles.legendGate} /></div>
          <div className={styles.legendScale}><span>1.0</span><span>4.0</span></div>
          <div className={styles.legendCaption}>Gate at 3.0 · grey = not yet screened</div>
        </div>
      </div>

      {/* Hover-clear lives on the whole canvas, not on each node -- the node
          and the detail card are two disjoint elements, so moving the mouse
          from one to the other briefly passes over neither. Clearing
          per-node closes the card before the pointer can ever reach its
          "View company" link; clearing only once the pointer leaves the
          entire canvas (which the card sits inside) fixes that gap. */}
      <div className={styles.canvasWrap} onMouseLeave={() => setHoveredName(null)}>
        {nodes.length === 0 ? (
          <p className={styles.empty}>No portfolio companies match these filters.</p>
        ) : (
          <>
            <svg
              ref={svgRef}
              viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
              className={styles.svg}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onPointerCancel={handlePointerUp}
            >
              <defs>
                <radialGradient id="vcHalo" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="var(--id8-accent)" stopOpacity="0.16" />
                  <stop offset="100%" stopColor="var(--id8-accent)" stopOpacity="0" />
                </radialGradient>
              </defs>
              <g transform={`translate(${VIEW_W / 2 + view.x} ${VIEW_H / 2 + view.y}) scale(${view.scale})`}>
                <circle r={vcSize.w * 1.1} fill="url(#vcHalo)" />

                {nodes.map((node) => (
                  // Same reasoning as the node <g>s below: <line> doesn't
                  // reliably transition x2/y2 either, which is why the edge
                  // was arriving at its new angle instantly while the box
                  // was still gliding there. Keeping the line's own geometry
                  // fixed (always horizontal, from the VC out to `len`) and
                  // rotating a wrapping <g> instead means the one thing that
                  // actually changes on a re-layout -- the angle -- moves
                  // through an ordinary `transform`, which does transition
                  // reliably, so the edge and its node now move in lockstep.
                  <g key={`edge-${node.company}`} className={styles.edgeWrap} style={{ transform: `rotate(${node.angleDeg}deg)` }}>
                    <line
                      className={node.hasScore ? styles.edge : undefined}
                      x1={0} y1={0} x2={node.len} y2={0}
                      stroke={node.stroke}
                      strokeWidth={node.strokeWidth}
                      strokeDasharray={node.hasScore ? undefined : '4 4'}
                      strokeLinecap="round"
                      style={node.hasScore ? { '--len': `${node.len}px`, animationDelay: `${node.delay}ms` } : undefined}
                    />
                  </g>
                ))}

                <g className={`${styles.node} ${styles.vcNode}`}>
                  <rect className={styles.nodeShape} x={-vcSize.w / 2} y={-vcSize.h / 2} width={vcSize.w} height={vcSize.h} rx="3" fill="var(--id8-ink)" />
                  <text x={0} y={5} textAnchor="middle" className={styles.vcLabel}>{vcName}</text>
                </g>

                {nodes.map((node) => (
                  <g
                    key={node.company}
                    className={styles.nodeWrap}
                    style={{ transform: `translate(${node.x}px, ${node.y}px)` }}
                    role="button"
                    aria-label={`View details for ${node.company}`}
                    aria-pressed={selectedName === node.company}
                    tabIndex={0}
                    onClick={() => selectNode(node)}
                    onKeyDown={(e) => { if (e.key === 'Enter') setSelectedName(node.company); }}
                    onMouseEnter={() => setHoveredName(node.company)}
                    onFocus={() => setHoveredName(node.company)}
                    onBlur={() => setHoveredName(null)}
                  >
                    {/* Position lives on this wrapping <g> alone (a single
                        `transform: translate()`, transitioned via CSS) --
                        SVG <text> doesn't reliably animate its own x/y
                        attributes the way <rect> does, so the box would glide
                        while the label snapped. One transform driving both
                        children at once means there's nothing left to
                        desync. The entrance pop (scale/opacity) lives on this
                        inner <g> instead, so it doesn't fight the position
                        transform for the same CSS property. */}
                    <g className={`${styles.node} ${selectedName === node.company ? styles.nodeSelected : ''}`} style={{ animationDelay: `${node.delay + 70}ms` }}>
                      <rect
                        className={styles.nodeShape}
                        x={-node.w / 2} y={-node.h / 2} width={node.w} height={node.h} rx="2"
                        fill={node.hasScore ? 'var(--id8-accent-bg)' : 'var(--id8-card)'}
                        stroke={node.hasScore ? 'var(--id8-accent)' : 'var(--id8-hair)'}
                      />
                      <text x={0} y={4} textAnchor="middle" className={styles.label}>{node.company}</text>
                    </g>
                  </g>
                ))}
              </g>
            </svg>

            <div className={styles.hint}>Drag to pan · Scroll to zoom</div>

            <div className={styles.controls}>
              <button type="button" onClick={() => zoomBy(1 / 1.3)} aria-label="Zoom out">–</button>
              <button type="button" onClick={resetView} aria-label="Reset view">Reset</button>
              <button type="button" onClick={() => zoomBy(1.3)} aria-label="Zoom in">+</button>
            </div>

            {shown && (
              <div className={styles.detailCard}>
                {selectedName && (
                  <button type="button" className={styles.detailClose} onClick={() => setSelectedName(null)} aria-label="Close">×</button>
                )}
                <div className={styles.detailName}>{shown.company}</div>
                <div className={styles.detailMeta}>{[shown.industry, shown.series].filter(Boolean).join(' · ') || 'No detail recorded'}</div>
                <div className={styles.detailScore}>
                  {shown.hasScore ? (
                    <>
                      <span className={`badge ${shown.fitScore >= 3 ? 'badge--gate' : 'badge--below'}`}>
                        {shown.fitScore >= 3 ? 'Clears gate' : 'Below gate'}
                      </span>{' '}
                      {shown.fitScore.toFixed(1)} / 4
                    </>
                  ) : (
                    <span className={styles.notScored}>Not yet screened against our rubric</span>
                  )}
                </div>
                <Link href={shown.href} className={styles.detailLink}>View company →</Link>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
