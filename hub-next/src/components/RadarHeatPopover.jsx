'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import styles from './RadarHeatPopover.module.css';
import { SIGNAL_LABELS } from '@/lib/radarSignalLabels';

// Replaces the Radar table's old native `title` tooltip on the Heat badge.
// Opens only on click (Oscar, 2026-08-14: the old hover-to-open behavior
// went away -- hovering the score shouldn't pop anything up, only clicking
// it should) and then STAYS OPEN regardless of the pointer moving away --
// only an outside click/tap, or clicking the badge again, closes it (same
// document-mousedown-listener pattern StageMultiSelect.jsx already uses for
// its own dropdown) -- and shows the next scan date, not just the score
// breakdown. `position: fixed`, same reasoning as PartnerVcPopover: the
// stage tables render inside SortableTable's horizontally-scrolling wrapper,
// which would clip an absolutely-positioned panel.
// Only one of these panels should ever be open at a time -- clicking row 2
// while row 1's panel is still open (by design: it only closes on an
// outside click, never automatically) used to leave BOTH open, and a scroll
// through several rows stacked one panel per row on top of each other
// (Oscar, 2026-08-06 screenshot: three overlapping "HAZARD MODEL" panels).
// A plain DOM CustomEvent is the simplest way to coordinate across sibling
// table-row instances that don't share a parent component to hold shared
// state in -- each instance just closes itself when it hears a DIFFERENT
// instance just opened.
const OPEN_EVENT = 'radar-heat-popover-open';

export default function RadarHeatPopover({ score, hot, signals, scoreSummary, predictedWindow, nextScanDate, nextScanReason, rationaleHref }) {
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  // Same named rows as the full Heat Score Signal Framework breakdown
  // (RadarHeatBreakdown.jsx, on the company page) -- Oscar, 2026-08-14:
  // wants "Raise Probability", "Industry Growth", etc. spelled out here too,
  // not collapsed into one "Signal Framework 88.8 (...)" sentence. Sorted by
  // rubric weight, heaviest signal first, same order the full breakdown uses.
  const signalRows = signals
    ? Object.entries(signals).sort((a, b) => b[1].weight - a[1].weight)
    : [];

  // `position: fixed` is viewport-relative, so it was computed once at open
  // time and then just sat there while the table scrolled underneath it
  // (Oscar, 2026-08-14: "look what happens if I scroll, the thing goes
  // lower") -- it needs to track the trigger's real position on every
  // scroll, not just the position it happened to be at on click. `true`
  // (capture) on the scroll listener because SortableTable's own scroll
  // wrapper fires a scroll event that doesn't bubble to window.
  useEffect(() => {
    if (!open) return undefined;
    function reposition() {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (rect) setCoords({ top: rect.bottom, left: Math.min(rect.left, window.innerWidth - 340 - 12) });
    }
    function onDocClick(e) {
      if (triggerRef.current?.contains(e.target) || panelRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    function onOtherOpen(e) {
      if (e.detail !== triggerRef.current) setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener(OPEN_EVENT, onOtherOpen);
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener(OPEN_EVENT, onOtherOpen);
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
  }, [open]);

  function show() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) setCoords({ top: rect.bottom, left: Math.min(rect.left, window.innerWidth - 340 - 12) });
    document.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: triggerRef.current }));
    setOpen(true);
  }

  function onKeyDown(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    open ? setOpen(false) : show();
  }

  return (
    <span
      ref={triggerRef}
      className={`badge ${hot ? 'badge--radar-hot' : 'badge--cold'} ${styles.trigger}`}
      tabIndex={0}
      onClick={() => (open ? setOpen(false) : show())}
      onKeyDown={onKeyDown}
    >
      {score}
      {open && (
        <span ref={panelRef} className={styles.panel} style={{ top: coords.top, left: coords.left }}>
          {scoreSummary && (
            <span className={styles.scoreLine}>
              Score {scoreSummary.score} / 100
              {scoreSummary.pointsAvailable != null && (
                <span className={styles.muted}> · {scoreSummary.pointsAvailable}/100 pts scored</span>
              )}
              {scoreSummary.roundAnnouncedFlag && <span className={styles.muted}> · round already announced, suppressed</span>}
            </span>
          )}
          {signalRows.length > 0 && (
            <span className={styles.signalList}>
              {signalRows.map(([key, entry]) => (
                <span key={key} className={styles.signalRow}>
                  <span>{SIGNAL_LABELS[key] || key}</span>
                  <span className={entry.computed ? styles.signalScore : styles.muted}>
                    {entry.computed ? `${entry.raw}/10 · ${entry.contribution} pts` : 'not measured'}
                  </span>
                </span>
              ))}
            </span>
          )}
          {predictedWindow && (
            <span className={styles.linesBlock}>
              <span className={styles.line}>Expected next raise: <strong>{predictedWindow}</strong></span>
            </span>
          )}
          {nextScanDate && (
            <span className={styles.nextScan}>
              <span>Next scan: <strong>{nextScanDate}</strong></span>
              {nextScanReason && <span className={styles.nextScanReason}>— {nextScanReason}</span>}
            </span>
          )}
          {rationaleHref && (
            <Link href={rationaleHref} className={styles.rationaleLink}>Full rationale →</Link>
          )}
        </span>
      )}
    </span>
  );
}
