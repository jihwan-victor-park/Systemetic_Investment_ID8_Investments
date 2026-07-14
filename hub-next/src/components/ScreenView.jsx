import { H2 } from '@/components/Prose';
import InlineMarkdown from '@/components/InlineMarkdown';
import styles from './ScreenView.module.css';

// Renders one company screen using the exact template every hub/docs/research/
// companies/*.md file shares: a dated H2, a bold fit-score-and-verdict line,
// a dimension-scoring list, a Rationale paragraph, a Confidence line, and a
// numbered Sources list.
export default function ScreenView({ screen }) {
  const heading = `Screen — ${screen.date}${screen.roundStage ? ` · ${screen.roundStage}` : ''}`;
  return (
    <div>
      <H2>{heading}</H2>
      <p>
        <strong>
          Fit score: {screen.fitScore != null ? screen.fitScore.toFixed(1) : '—'} / 4.0
          {screen.rawScore != null && ` (raw ${screen.rawScore.toFixed(1)})`}
        </strong>
        {screen.verdict && ` — ${screen.verdict}`}
      </p>
      {screen.hardAutoPassNote && <p><em>{screen.hardAutoPassNote}</em></p>}

      {/* Click a dimension to expand its evidence/rationale detail. Collapsed
          state still shows every score at a glance. */}
      <div className={styles.dimensions}>
        {screen.dimensions.map((d) => (
          <details key={d.name} className={styles.dim}>
            <summary>
              <span className={styles.summaryLeft}>
                <svg className={styles.chevron} width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                  <path d="M2 0.5 L8 5 L2 9.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
                </svg>
                <span className={styles.dimName}>{d.name}</span>
              </span>
              <span className={styles.dimScore}>{d.score}<em> / 4</em></span>
            </summary>
            <div className={styles.dimEvidence}>
              {/* Dimension-level tier: the synthesis of the point-level findings below. */}
              <InlineMarkdown text={d.evidence} />
              {/* Point-level tier: one grounded finding per rubric checklist item.
                  Empty for AI Score/Terms, which have no checklist. */}
              {d.subcategories?.length > 0 && (
                <ul className={styles.subList}>
                  {d.subcategories.map((s) => (
                    <li key={s.name}>
                      <span className={styles.subName}>{s.name}:</span>{' '}
                      <InlineMarkdown text={s.finding} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </details>
        ))}
      </div>

      <p>
        <strong>Rationale</strong>
        <br />
        <InlineMarkdown text={screen.rationale} />
      </p>

      {screen.confidence && <p><em>Confidence: {screen.confidence}</em></p>}

      {screen.sources?.length > 0 && (
        <>
          <p><strong>Sources</strong></p>
          <ol>
            {screen.sources.map((s) => (
              <li key={s.number}>
                <a href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a>
              </li>
            ))}
          </ol>
        </>
      )}
      <hr />
    </div>
  );
}
