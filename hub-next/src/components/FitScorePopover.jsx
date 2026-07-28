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
  // respond to page scroll.
  //
  // This used to pick a side (above/below the trigger) and cap max-height to
  // ONLY the sliver of room on that one side -- but FitScoreDetail's content
  // (4 dimensions + evidence + rationale + stage/raise-probability reads) is
  // routinely 500-600px tall, and on a normal laptop viewport that sliver is
  // smaller than that for almost every row except the very first/last on
  // screen (measured: on a 550px-tall viewport, every row but the top/bottom
  // edge got clamped to a fraction of its real height). The result was a
  // near-empty, barely-scrollable little box for most hovers -- "illegible"
  // was the accurate word for it, not a bug in a few edge cases.
  //
  // Fix: don't measure the sliver directly above/below the trigger at all.
  // Try to place the whole panel, at its full natural height, ANYWHERE it
  // fits in the viewport -- prefer just below the trigger (normal reading
  // direction), but slide it up as far as needed to keep its bottom edge
  // on-screen. Only when the panel is taller than the entire viewport does
  // it fall back to a clamped height with its own internal scrollbar.
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
    // below is applied.
    const naturalHeight = panel.scrollHeight;

    const viewportSpace = window.innerHeight - 2 * PANEL_MARGIN;
    const fits = naturalHeight <= viewportSpace;
    const maxHeight = fits ? naturalHeight : viewportSpace;

    let top;
    if (fits) {
      const preferredTop = triggerRect.bottom + 4;
      top = Math.min(preferredTop, window.innerHeight - PANEL_MARGIN - naturalHeight);
      top = Math.max(PANEL_MARGIN, top);
    } else {
      top = PANEL_MARGIN;
    }

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
