'use client';

import { useLayoutEffect, useRef, useState } from 'react';
import FitScoreDetail from './FitScoreDetail';
import styles from './FitScorePopover.module.css';

const PANEL_MARGIN = 8;

// Same fixed-position hover-panel pattern as DescriptionPopover (escapes
// SortableTable's .scrollWrap overflow-x: auto) -- shows the full Stage 0
// Portfolio Fit breakdown (FitScoreDetail: per-dimension score + evidence,
// overall rationale, confidence, current-stage research, raise-probability
// read) on hovering the fit score, the same depth of analysis a Stage 1
// screen shows on its own page, without leaving the portfolio table.
export default function FitScorePopover({ company }) {
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const closeTimer = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0, maxHeight: null });

  if (company.fitScore == null) return <span className={styles.muted}>—</span>;

  function show() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    const rect = triggerRef.current?.getBoundingClientRect();
    // Rough first guess (below + left-aligned) -- corrected against the
    // panel's real measured size once it's actually in the DOM, below.
    if (rect) setCoords({ top: rect.bottom + 4, left: rect.left, maxHeight: null });
    setOpen(true);
  }
  function scheduleHide() {
    closeTimer.current = setTimeout(() => setOpen(false), 180);
  }

  // Re-measure against the panel's *actual* rendered size and clamp to the
  // viewport -- the plain "below + left-aligned" guess above regularly ran
  // the panel (up to 70vh tall) off the bottom or right edge of the screen,
  // with no way to scroll it back into view since `position: fixed` doesn't
  // respond to page scroll. Flips above the trigger when there's more room
  // there, and caps max-height to whatever space is actually available on
  // whichever side gets used, so the panel's own scrollbar kicks in instead
  // of the browser window clipping it.
  useLayoutEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    const panel = panelRef.current;
    if (!trigger || !panel) return;

    const triggerRect = trigger.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    // scrollHeight, not the rect -- the rect reflects whatever max-height
    // constrained a *previous* render (the CSS 70vh default on first open),
    // not how tall the panel will actually be once the max-height computed
    // below is applied. Anchoring the flip-up case against the stale rect
    // height under-anchored the panel, letting it grow past the viewport's
    // top edge once it expanded to fill the real (larger) budget.
    const naturalHeight = panel.scrollHeight;

    const spaceBelow = window.innerHeight - triggerRect.bottom - PANEL_MARGIN;
    const spaceAbove = triggerRect.top - PANEL_MARGIN;
    const flipUp = naturalHeight > spaceBelow && spaceAbove > spaceBelow;
    const maxHeight = Math.max(120, flipUp ? spaceAbove : spaceBelow);

    const top = flipUp
      ? Math.max(PANEL_MARGIN, triggerRect.top - Math.min(naturalHeight, maxHeight) - 4)
      : triggerRect.bottom + 4;

    let left = triggerRect.left;
    left = Math.min(left, window.innerWidth - panelRect.width - PANEL_MARGIN);
    left = Math.max(left, PANEL_MARGIN);

    setCoords({ top, left, maxHeight });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

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
      {company.fitScore.toFixed(1)} / 4
      {open && (
        <span
          ref={panelRef}
          className={styles.panel}
          style={{
            top: coords.top,
            left: coords.left,
            maxHeight: coords.maxHeight ? `${coords.maxHeight}px` : undefined,
          }}
          onMouseEnter={show}
          onMouseLeave={scheduleHide}
        >
          <FitScoreDetail fit={company} />
        </span>
      )}
    </span>
  );
}
