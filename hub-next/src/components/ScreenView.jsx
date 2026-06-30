import { InlineMarkdown, BlockMarkdown } from "@/components/Markdown";

function badge(screen) {
  if (screen.gate) {
    return { cls: "badge badge--gate", text: `Clears gate · ${screen.tier_label || ""}`.trim() };
  }
  if (screen.quality_tier === "borderline") {
    return { cls: "badge badge--borderline", text: "Borderline — review" };
  }
  return { cls: "badge badge--below", text: "Below threshold" };
}

/** One dated Stage-1 screen: score, rubric table, rationale, sources. */
export default function ScreenView({ screen }) {
  const b = badge(screen);
  return (
    <section style={{ marginTop: "2.5rem" }}>
      <h2 style={{ borderBottom: "1px solid var(--id8-hair)", paddingBottom: "0.3rem" }}>
        Screen — {screen.date}{screen.round ? ` · ${screen.round}` : ""}
      </h2>

      <div style={{ display: "flex", alignItems: "baseline", gap: "1rem", margin: "0.9rem 0 1.2rem", flexWrap: "wrap" }}>
        <span style={{ fontFamily: "'Roboto Serif', serif", fontSize: "1.7rem", fontWeight: 500 }}>
          {Number(screen.fit_score).toFixed(1)} / 4.0
        </span>
        <span className={b.cls}>{b.text}</span>
      </div>

      <table className="htable">
        <thead>
          <tr><th>Dimension</th><th>Score</th><th>Evidence</th></tr>
        </thead>
        <tbody>
          {(screen.params || []).map((p) => (
            <tr key={p.key}>
              <td style={{ whiteSpace: "nowrap" }}>{p.label || p.key}</td>
              <td><strong>{Number(p.score).toFixed(0)}</strong>{" "}
                <span style={{ color: "var(--id8-grey)" }}>/ 4</span></td>
              <td><InlineMarkdown>{p.evidence}</InlineMarkdown></td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Rationale</h3>
      <div className="prose"><BlockMarkdown>{screen.rationale}</BlockMarkdown></div>
      <p style={{ color: "var(--id8-grey)", fontSize: "0.85rem" }}>Confidence: {screen.confidence}</p>

      {Array.isArray(screen.citations) && screen.citations.length > 0 && (
        <>
          <h3>Sources</h3>
          <ol style={{ color: "var(--id8-soft)", fontSize: "0.82rem", lineHeight: 1.7 }}>
            {screen.citations.map((url, i) => (
              <li key={i}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
