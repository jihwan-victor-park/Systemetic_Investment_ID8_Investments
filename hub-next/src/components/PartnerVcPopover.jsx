'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import styles from './PartnerVcPopover.module.css';

// Real click-through popover for a deal row that matches more than one
// tracked VC's portfolio (a company like Anduril can legitimately sit in
// several firms' portfolios at once -- see findInvestorSources) -- replaces
// the old native `title` tooltip, which could show the names but never let
// you click through to a firm's page. Fixed-position (not absolute): the
// stage tables render inside SortableTable's .scrollWrap, which sets
// overflow-x: auto (and so implicitly overflow-y: auto too), which would
// clip an absolutely-positioned panel; `position: fixed` escapes that since
// it's anchored to the viewport, not the scrolling ancestor. A short close
// delay (cancelable by re-entering either the trigger or the panel) is what
// lets the pointer actually cross the visual gap between them without the
// panel disappearing first -- CSS-only :hover can't do this because
// `position: fixed` breaks the parent/child hit-testing relationship
// mouseenter/mouseleave would otherwise rely on.
export default function PartnerVcPopover({ matches }) {
  const triggerRef = useRef(null);
  const closeTimer = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  if (!matches || matches.length === 0) return '—';
  if (matches.length === 1) {
    return matches[0].viaHref ? <Link href={matches[0].viaHref}>{matches[0].via}</Link> : matches[0].via;
  }

  function show() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) setCoords({ top: rect.bottom, left: rect.left });
    setOpen(true);
  }

  function scheduleHide() {
    closeTimer.current = setTimeout(() => setOpen(false), 180);
  }

  return (
    <span
      ref={triggerRef}
      className={styles.trigger}
      tabIndex={0}
      onMouseEnter={show}
      onMouseLeave={scheduleHide}
      onFocus={show}
      onBlur={scheduleHide}
    >
      {matches.length} VCs
      {open && (
        <span
          className={styles.panel}
          style={{ top: coords.top, left: coords.left }}
          onMouseEnter={show}
          onMouseLeave={scheduleHide}
        >
          {matches.map((m, i) => (
            m.viaHref ? (
              <Link key={i} href={m.viaHref} className={styles.row}>{m.via}</Link>
            ) : (
              <span key={i} className={styles.row}>{m.via}</span>
            )
          ))}
        </span>
      )}
    </span>
  );
}
