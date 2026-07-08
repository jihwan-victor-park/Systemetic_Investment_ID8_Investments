// Minimal, safe inline-markdown renderer for pipeline-generated text (citation
// links and occasional bold) — no dangerouslySetInnerHTML, just the two
// patterns this content actually uses.
//
// Citation links look like `[[4]](url)` — the visible link text is itself
// "[4]", brackets included — so the text-capture group has to allow one level
// of nested `[...]`, not just "no closing bracket at all".
export default function InlineMarkdown({ text }) {
  if (!text) return null;
  const nodes = [];
  const re = /\[(\[[^\]]*\]|[^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*/g;
  let lastIndex = 0;
  let m;
  let key = 0;
  while ((m = re.exec(text))) {
    if (m.index > lastIndex) nodes.push(text.slice(lastIndex, m.index));
    if (m[1] !== undefined) {
      nodes.push(
        <a key={key++} href={m[2]} target="_blank" rel="noopener noreferrer">
          {m[1]}
        </a>,
      );
    } else {
      nodes.push(<strong key={key++}>{m[3]}</strong>);
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return <>{nodes}</>;
}
