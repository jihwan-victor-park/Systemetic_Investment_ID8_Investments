'use client';

import { useRef, useState } from 'react';
import styles from './RaiseProbabilityPopover.module.css';

// Fixed definitions, straight from prompts/portfolio_fit_rubric.md's
// "Probability of next round (3-month band)" section -- the actual
// thresholds the model was instructed to use, not a paraphrase.
const BANDS = [
  { key: 'low', label: 'Low', range: '< 15%' },
  { key: 'medium', label: 'Medium', range: '15–35%' },
  { key: 'high', label: 'High', range: '35–60%' },
  { key: 'imminent', label: 'Imminent', range: '> 60%' },
];

// Same fixed-position hover-panel pattern as DescriptionPopover/
// FitScorePopover. Shows what each band actually means (fixed thresholds,
// same for every company), which one applies here, and -- when this company
// has been through Stage 0 -- the two-layer reasoning behind it: the
// deterministic timing-only starting point (months since last round vs.
// stage-typical cadence, computed in code) and what the model's research
// moved it to and why.
export default function RaiseProbabilityPopover({ company }) {
  const triggerRef = useRef(null);
  const closeTimer = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  const { fitRaiseProbability, fitBaseRateBand, fitRaiseProbabilityEvidence } = company;
  if (!fitRaiseProbability) return <span className={styles.muted}>—</span>;

  function show() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) setCoords({ top: rect.bottom, left: rect.left });
    setOpen(true);
  }
  function scheduleHide() {
    closeTimer.current = setTimeout(() => setOpen(false), 180);
  }

  const moved = fitBaseRateBand && fitBaseRateBand !== fitRaiseProbability;

  return (
    <span
      ref={triggerRef}
      className={styles.trigger}
      data-band={fitRaiseProbability}
      tabIndex={0}
      onMouseEnter={show}
      onMouseLeave={scheduleHide}
      onFocus={show}
      onBlur={scheduleHide}
    >
      {fitRaiseProbability}
      {open && (
        <span
          className={styles.panel}
          style={{ top: coords.top, left: coords.left }}
          onMouseEnter={show}
          onMouseLeave={scheduleHide}
        >
          <span className={styles.title}>Probability of raising again within 3 months</span>
          <span className={styles.bands}>
            {BANDS.map((b) => (
              <span key={b.key} className={styles.bandRow} data-current={b.key === fitRaiseProbability}>
                <span className={styles.bandDot} data-band={b.key} />
                <span className={styles.bandLabel}>{b.label}</span>
                <span className={styles.bandRange}>{b.range}</span>
              </span>
            ))}
          </span>

          {fitBaseRateBand && (
            <span className={styles.reasoning}>
              <span className={styles.reasonLine}>
                Started at <b>{fitBaseRateBand}</b> — deterministic, from months since the last
                round vs. typical stage cadence, computed in code, not researched.
              </span>
              {moved ? (
                <span className={styles.reasonLine}>
                  Moved to <b>{fitRaiseProbability}</b>: {fitRaiseProbabilityEvidence || 'qualitative signal from research.'}
                </span>
              ) : (
                <span className={styles.reasonLine}>
                  Stayed at <b>{fitRaiseProbability}</b>: {fitRaiseProbabilityEvidence || 'no qualitative signal moved it either way.'}
                </span>
              )}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
