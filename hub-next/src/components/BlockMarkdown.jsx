import InlineMarkdown from './InlineMarkdown';
import styles from './BlockMarkdown.module.css';

// Small hand-rolled BLOCK markdown parser (headings, bullet lists,
// paragraphs) for content that has real structure -- unlike InlineMarkdown
// (bold + links only), this is for a full memo body (deal_intelligence's
// Stage 2 synthesis, prompts/memo_template.md). Deliberately not a real <h2>/
// <h3> -- this renders inside chat messages, and DocsShell's TOC scan picks
// up every h2/h3[id] on the page, which would pollute the page TOC with
// per-message section headers and risk id collisions across messages.
function parseBlocks(text) {
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n');
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i += 1; continue; }

    const heading = line.match(/^(#{1,4})\s+(.*)/);
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2].trim() });
      i += 1;
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, '').trim());
        i += 1;
      }
      blocks.push({ type: 'list', items });
      continue;
    }

    const paraLines = [];
    while (i < lines.length && lines[i].trim() && !/^#{1,4}\s+/.test(lines[i]) && !/^[-*]\s+/.test(lines[i])) {
      paraLines.push(lines[i]);
      i += 1;
    }
    blocks.push({ type: 'para', text: paraLines.join(' ').trim() });
  }
  return blocks;
}

export default function BlockMarkdown({ text }) {
  const blocks = parseBlocks(text);
  return (
    <div className={styles.block}>
      {blocks.map((b, idx) => {
        if (b.type === 'heading') {
          return (
            <div key={idx} className={styles.heading} data-level={b.level}>
              <InlineMarkdown text={b.text} />
            </div>
          );
        }
        if (b.type === 'list') {
          return (
            <ul key={idx} className={styles.list}>
              {b.items.map((item, j) => (
                <li key={j}><InlineMarkdown text={item} /></li>
              ))}
            </ul>
          );
        }
        return (
          <p key={idx} className={styles.para}>
            <InlineMarkdown text={b.text} />
          </p>
        );
      })}
    </div>
  );
}
