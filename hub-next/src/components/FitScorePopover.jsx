'use client';

import { useRef, useState } from 'react';
import styles from './FitScorePopover.module.css';

const TIER_LABEL = {
  track_priority: 'Track — priority', track: 'Track', monitor: 'Monitor',
  too_early: 'Too early', drop: 'Drop', error: 'Scoring error',
};

// Same fixed-position hover-panel pattern as DescriptionPopover (escapes
// SortableTable's .scrollWrap overflow-x: auto) -- shows the full Stage 0
// Portfolio Fit breakdown (per-dimension score + evidence, overall rationale,
// confidence, current-stage research, raise-probability read) on hovering the
// fit score, the same depth of analysis a Stage 1 screen shows on its own
// page, without leaving the portfolio table.
export default function FitScorePopover({ company }) {
  const triggerRef = useRef(null);
  const closeTimer = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  const {
    fitScore, fitTier, fitDimensions, fitRationale, fitConfidence,
    fitCurrentStage, fitCurrentStageEvidence, fitRaiseProbability,
    fitRaiseProbabilityEvidence, fitHardPass, fitHardPassReason,
    fitTooEarly, fitResearchFlag,
  } = company;

  if (fitScore == null) return <span className={styles.muted}>—</span>;

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
      {fitScore.toFixed(1)} / 4
      {open && (
        <span
          className={styles.panel}
          style={{ top: coords.top, left: coords.left }}
          onMouseEnter={show}
          onMouseLeave={scheduleHide}
        >
          <span className={styles.header}>
            <span className={styles.tierBadge} data-tier={fitTier}>{TIER_LABEL[fitTier] || fitTier}</span>
            {fitConfidence && <span className={styles.confidence}>confidence: {fitConfidence}</span>}
          </span>

          {(fitHardPass || fitTooEarly) && (
            <span className={styles.flagLine} data-kind={fitHardPass ? 'hardpass' : 'early'}>
              {fitHardPass ? `Hard-pass: ${fitHardPassReason}` : 'Below Series B — benched, not judged weak on merits'}
            </span>
          )}

          {fitDimensions?.length > 0 && (
            <span className={styles.dims}>
              {fitDimensions.map((d) => (
                <span key={d.key} className={styles.dimRow}>
                  <span className={styles.dimHead}>
                    <span className={styles.dimLabel}>{d.label}</span>
                    <span className={styles.dimScore}>{d.score.toFixed(0)}/4</span>
                  </span>
                  <span className={styles.dimEvidence}>{d.evidence}</span>
                </span>
              ))}
            </span>
          )}

          {fitRationale && <span className={styles.rationale}>{fitRationale}</span>}

          {fitCurrentStage && (
            <span className={styles.subBlock}>
              <span className={styles.subLabel}>Current stage: {fitCurrentStage}</span>
              {fitCurrentStageEvidence && <span className={styles.subEvidence}>{fitCurrentStageEvidence}</span>}
            </span>
          )}

          {fitRaiseProbability && (
            <span className={styles.subBlock}>
              <span className={styles.subLabel}>Raise probability (3mo): {fitRaiseProbability}</span>
              {fitRaiseProbabilityEvidence && <span className={styles.subEvidence}>{fitRaiseProbabilityEvidence}</span>}
            </span>
          )}

          {fitResearchFlag && (
            <span className={styles.researchFlag}>⚠ {fitResearchFlag}</span>
          )}
        </span>
      )}
    </span>
  );
}
