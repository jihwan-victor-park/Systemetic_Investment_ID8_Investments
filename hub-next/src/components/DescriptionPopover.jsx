'use client';

import { useRef, useState } from 'react';
import styles from './DescriptionPopover.module.css';

const PREVIEW_LENGTH = 40;

// Same fixed-position hover-panel pattern as PartnerVcPopover -- `position:
// fixed` escapes SortableTable's .scrollWrap (overflow-x: auto), and the
// close delay lets the pointer cross the gap between trigger and panel.
export default function DescriptionPopover({ text }) {
  const triggerRef = useRef(null);
  const closeTimer = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  if (!text) return '—';

  const preview = text.length > PREVIEW_LENGTH ? `${text.slice(0, PREVIEW_LENGTH)}…` : text;

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
      {preview}
      {open && (
        <span
          className={styles.panel}
          style={{ top: coords.top, left: coords.left }}
          onMouseEnter={show}
          onMouseLeave={scheduleHide}
        >
          {text}
        </span>
      )}
    </span>
  );
}
