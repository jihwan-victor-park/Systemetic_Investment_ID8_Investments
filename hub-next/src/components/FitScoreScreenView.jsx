import { H2 } from '@/components/Prose';
import InlineMarkdown from '@/components/InlineMarkdown';
import { TIER_LABEL } from '@/lib/fitTier';
import styles from './ScreenView.module.css';

// Renders the Stage 0 Portfolio Fit read using the exact same template and
// CSS as ScreenView (Stage 1's real screens) -- H2, bold fit-score-and-
// verdict line, a collapsible dimension-scoring list, a Rationale
// paragraph, a Confidence line -- so a company's Stage 0 read looks like
// the same kind of document as its Stage 1 screens instead of a visually
// separate popover-style summary. Read-only: unlike ScreenView's
// subcategories, Stage 0 dimensions aren't editable, so this skips the
// EditableText/patch machinery entirely.
export default function FitScoreScreenView({ fit }) {
  const {
    fitScore, fitTier, fitDimensions, fitRationale, fitConfidence,
    fitCurrentStage, fitCurrentStageEvidence, fitRaiseProbability,
    fitRaiseProbabilityEvidence, fitHardPass, fitHardPassReason,
    fitTooEarly, fitResearchFlag, latestRound,
  } = fit;

  // fitCurrentStage is the round the stage-resolution pass actually
  // researched (more current); latestRound is whatever's on file when that
  // pass hasn't run -- same fallback the old plain summary line used.
  const round = fitCurrentStage || latestRound;
  const heading = `Stage 0 — Portfolio Fit${round ? ` · ${round}` : ''}`;

  return (
    <div>
      <H2>{heading}</H2>
      <p>
        <strong>Fit score: {fitScore.toFixed(1)} / 4.0</strong>
        {` — ${TIER_LABEL[fitTier] || fitTier}`}
      </p>
      {(fitHardPass || fitTooEarly) && (
        <p>
          <em>
            {fitHardPass
              ? `Hard-pass: ${fitHardPassReason}`
              : 'Below Series B — benched, not judged weak on merits'}
          </em>
        </p>
      )}

      {fitDimensions?.length > 0 && (
        <div className={styles.dimensions}>
          {fitDimensions.map((d) => (
            <details key={d.key || d.label} className={styles.dim}>
              <summary>
                <span className={styles.summaryLeft}>
                  <svg className={styles.chevron} width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                    <path d="M2 0.5 L8 5 L2 9.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
                  </svg>
                  <span className={styles.dimName}>{d.label}</span>
                </span>
                <span className={styles.dimScore}>{d.score}<em> / 4</em></span>
              </summary>
              <div className={styles.dimEvidence}>
                <InlineMarkdown text={d.evidence} />
              </div>
            </details>
          ))}
        </div>
      )}

      {fitRationale && (
        <p>
          <strong>Rationale</strong>
          <br />
          <InlineMarkdown text={fitRationale} />
        </p>
      )}

      {fitConfidence && <p><em>Confidence: {fitConfidence}</em></p>}

      {fitCurrentStage && (
        <p>
          <strong>Current stage:</strong> {fitCurrentStage}
          {fitCurrentStageEvidence && <>{' — '}<InlineMarkdown text={fitCurrentStageEvidence} /></>}
        </p>
      )}

      {fitRaiseProbability && (
        <p>
          <strong>Raise probability (3mo):</strong> {fitRaiseProbability}
          {fitRaiseProbabilityEvidence && <>{' — '}<InlineMarkdown text={fitRaiseProbabilityEvidence} /></>}
        </p>
      )}

      {fitResearchFlag && <p><em>⚠ {fitResearchFlag}</em></p>}

      <hr />
    </div>
  );
}
