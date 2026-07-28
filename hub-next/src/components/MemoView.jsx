import { H2 } from '@/components/Prose';
import BlockMarkdown from '@/components/BlockMarkdown';
import styles from './MemoView.module.css';

// Read-only render of a persisted Stage 2 deep-research memo (see
// firestore_push.push_company_memo_firestore) -- the same content
// ResearchChat's Stage2Result shows inline in a chat bubble, but here on the
// company's own page so it's still reachable after that chat session ends.
export default function MemoView({ memo }) {
  const body = memo.sections?.memo || '(no memo synthesized)';
  return (
    <div className={styles.memo}>
      <H2>Deep research — {memo.date}</H2>
      {memo.finalScore != null && <p className={styles.score}>{memo.finalScore} / 100</p>}
      <BlockMarkdown text={body} />
      {memo.sources?.length > 0 && (
        <>
          <div className={styles.sourcesLabel}>Sources</div>
          <ol className={styles.sourcesList}>
            {memo.sources.map((s) => (
              <li key={s}><a href={s} target="_blank" rel="noopener noreferrer">{s}</a></li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
