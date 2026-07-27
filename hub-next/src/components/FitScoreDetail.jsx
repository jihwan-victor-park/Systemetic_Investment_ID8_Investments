import styles from './FitScoreDetail.module.css';

const TIER_LABEL = {
  track_priority: 'Track — priority', track: 'Track', monitor: 'Monitor',
  too_early: 'Too early', drop: 'Drop', error: 'Scoring error',
};

// The full Stage 0 Portfolio Fit breakdown -- per-dimension score + evidence,
// overall rationale, confidence, current-stage research, raise-probability
// read. Shared by FitScorePopover (hover, inside portfolio/pipeline tables)
// and the company detail pages (static, once a company already has a fit
// score but no live Stage 1 screen yet) -- same data, same depth, just two
// different shells around it. `bordered` adds the top divider/spacing the
// static page placement needs to separate it from the page's own summary
// line; the popover panel supplies its own box chrome instead, so it omits it.
export default function FitScoreDetail({ fit, bordered }) {
  const {
    fitTier, fitDimensions, fitRationale, fitConfidence,
    fitCurrentStage, fitCurrentStageEvidence, fitRaiseProbability,
    fitRaiseProbabilityEvidence, fitHardPass, fitHardPassReason,
    fitTooEarly, fitResearchFlag,
  } = fit;

  return (
    <div className={bordered ? `${styles.root} ${styles.bordered}` : styles.root}>
      <div className={styles.header}>
        <span className={styles.tierBadge} data-tier={fitTier}>{TIER_LABEL[fitTier] || fitTier}</span>
        {fitConfidence && <span className={styles.confidence}>confidence: {fitConfidence}</span>}
      </div>

      {(fitHardPass || fitTooEarly) && (
        <div className={styles.flagLine} data-kind={fitHardPass ? 'hardpass' : 'early'}>
          {fitHardPass ? `Hard-pass: ${fitHardPassReason}` : 'Below Series B — benched, not judged weak on merits'}
        </div>
      )}

      {fitDimensions?.length > 0 && (
        <div className={styles.dims}>
          {fitDimensions.map((d) => (
            <div key={d.key} className={styles.dimRow}>
              <div className={styles.dimHead}>
                <span className={styles.dimLabel}>{d.label}</span>
                <span className={styles.dimScore}>{d.score.toFixed(0)}/4</span>
              </div>
              <div className={styles.dimEvidence}>{d.evidence}</div>
            </div>
          ))}
        </div>
      )}

      {fitRationale && <p className={styles.rationale}>{fitRationale}</p>}

      {fitCurrentStage && (
        <div className={styles.subBlock}>
          <span className={styles.subLabel}>Current stage: {fitCurrentStage}</span>
          {fitCurrentStageEvidence && <span className={styles.subEvidence}>{fitCurrentStageEvidence}</span>}
        </div>
      )}

      {fitRaiseProbability && (
        <div className={styles.subBlock}>
          <span className={styles.subLabel}>Raise probability (3mo): {fitRaiseProbability}</span>
          {fitRaiseProbabilityEvidence && <span className={styles.subEvidence}>{fitRaiseProbabilityEvidence}</span>}
        </div>
      )}

      {fitResearchFlag && (
        <div className={styles.researchFlag}>⚠ {fitResearchFlag}</div>
      )}
    </div>
  );
}
