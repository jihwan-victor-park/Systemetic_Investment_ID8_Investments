import { H2 } from '@/components/Prose';
import InlineMarkdown from '@/components/InlineMarkdown';

// Renders one company screen using the exact template every hub/docs/research/
// companies/*.md file shares: a dated H2, a bold fit-score-and-verdict line,
// a dimension-scoring table, a Rationale paragraph, a Confidence line, and a
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

      <table>
        <thead>
          <tr>
            <th>Dimension</th>
            <th>Score</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {screen.dimensions.map((d) => (
            <tr key={d.name}>
              <td>{d.name}</td>
              <td>{d.score}</td>
              <td><InlineMarkdown text={d.evidence} /></td>
            </tr>
          ))}
        </tbody>
      </table>

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
