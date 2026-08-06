'use client';

import { useEffect, useRef, useState } from 'react';
import styles from './RadarHeatPopover.module.css';

// Replaces the Radar table's old native `title` tooltip on the Heat badge
// (Oscar, 2026-08-06: "the heat score should be so that you hover it and
// you see the full explanation of the score, and it doesn't go off unless
// you press it. as well when you hover it... you should be able to see the
// date of the following screen"). Two behaviors a native `title` attribute
// can't do at all: opens on hover (mouseenter/focus, same trigger as
// PartnerVcPopover.jsx) but then STAYS OPEN regardless of the pointer
// moving away -- only an outside click/tap closes it (same
// document-mousedown-listener pattern StageMultiSelect.jsx already uses for
// its own dropdown) -- and shows the next scan date, not just the score
// breakdown. `position: fixed`, same reasoning as PartnerVcPopover: the
// stage tables render inside SortableTable's horizontally-scrolling wrapper,
// which would clip an absolutely-positioned panel.
// Only one of these panels should ever be open at a time -- hovering row 2
// while row 1's panel is still open (by design: it only closes on an
// outside click, never on mouseleave) used to leave BOTH open, and a scroll
// through several rows stacked one panel per row on top of each other
// (Oscar, 2026-08-06 screenshot: three overlapping "HAZARD MODEL" panels).
// A plain DOM CustomEvent is the simplest way to coordinate across sibling
// table-row instances that don't share a parent component to hold shared
// state in -- each instance just closes itself when it hears a DIFFERENT
// instance just opened.
const OPEN_EVENT = 'radar-heat-popover-open';

export default function RadarHeatPopover({ score, hot, lines, nextScanDate, nextScanReason }) {
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  useEffect(() => {
    if (!open) return undefined;
    function onDocClick(e) {
      if (triggerRef.current?.contains(e.target) || panelRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    function onOtherOpen(e) {
      if (e.detail !== triggerRef.current) setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener(OPEN_EVENT, onOtherOpen);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener(OPEN_EVENT, onOtherOpen);
    };
  }, [open]);

  function show() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) setCoords({ top: rect.bottom, left: Math.min(rect.left, window.innerWidth - 320 - 12) });
    document.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: triggerRef.current }));
    setOpen(true);
  }

  return (
    <span
      ref={triggerRef}
      className={`badge ${hot ? 'badge--radar-hot' : 'badge--cold'} ${styles.trigger}`}
      tabIndex={0}
      onMouseEnter={show}
      onFocus={show}
      onClick={() => (open ? setOpen(false) : show())}
    >
      {score}
      {open && (
        <span ref={panelRef} className={styles.panel} style={{ top: coords.top, left: coords.left }}>
          {lines.map((line, i) => <span key={i} className={styles.line}>{line}</span>)}
          {nextScanDate && (
            <span className={styles.nextScan}>
              Next scan: <strong>{nextScanDate}</strong>{nextScanReason && ` — ${nextScanReason}`}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
