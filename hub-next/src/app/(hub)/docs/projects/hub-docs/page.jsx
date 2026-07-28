import { H2, H3 } from '@/components/Prose';
import { Note } from '@/components/Admonition';
import GuideCard from '@/components/GuideCard';

export const metadata = { title: 'Documentation System', description: 'How ID8 operating guides are built and published — cover, DOCX, and hub page.' };

const PRIMITIVES = [
  ['chapter(num, title)', 'Section heading — grey number + serif title, hairline rule, added to TOC'],
  ['h2(text)', 'Sub-heading, Sora bold 11pt, added to TOC'],
  ['h3(text)', 'Third-level heading, Sora bold 10pt, muted'],
  ['p(text | runs[])', "Body paragraph — pass a string or a run() / bold() / code() array"],
  ['run(text)', 'Inline text run'],
  ['bold(text)', 'Bold inline run'],
  ['code(text)', 'Monospace inline run for filenames, commands, identifiers'],
  ['bullet(text | runs[])', 'Em-dash bullet item'],
  ['note(text | runs[])', 'Note callout — bold NOTE lead-in, no box'],
  ['table(headers, rows, widths)', 'Editorial table — no fills, no vertical lines, hairline separators. Widths in DXA, must sum to 9360'],
  ['codeBlock(lines[])', "Monospace indented block — spread with ..."],
  ['check(text | runs[])', 'Checklist bullet'],
  ['closing()', 'Document close — hairline, logo, tagline. Always last, spread with ...'],
  ['contents()', 'TOC heading and field. Always first, spread with ...'],
];

export default function HubDocsPage() {
  return (
    <>
      <h1>Documentation System</h1>
      <p>
        Every ID8 operating guide follows the same system: a cover image generated from the Latent Order design
        library, a formatted DOCX built from a JavaScript script using the shared <code>lib.js</code> primitives,
        and a page on this hub with a downloadable card. Adding documentation for a new system takes one script,
        one hub page, and three commands.
      </p>

      <GuideCard
        title="Documentation System"
        meta="The formatted edition. Cover generation, DOCX library, and hub integration."
        cover="/img/cover_hub_docs.png"
        docx="/guides/ID8_Documentation_System_Guide.docx"
      />

      <table>
        <tbody>
          <tr><td>Design system</td><td>Latent Order — <code>design/lib.js</code>, <code>design/build_cover.js</code></td></tr>
          <tr><td>Output</td><td>Cover PNG + DOCX guide + hub page</td></tr>
          <tr><td>Code</td><td><code>design/build_*.js</code>, <code>hub-next/src/app/docs/projects/*</code></td></tr>
        </tbody>
      </table>

      <H2>How it works</H2>
      <p>Each guide is three things: a cover, a DOCX, and a hub page. They are built in order.</p>

      <H3>1. Cover image</H3>
      <p>
        Open <code>design/build_cover.js</code> and add an entry to the <code>builds</code> array with a unique
        seed string, title lines, subtitle, and fig number. Run <code>node build_cover.js</code> to generate the
        HTML, then render to PNG via Chrome headless at 816×1056. Copy the PNG to <code>hub-next/public/img/</code>.
      </p>
      <p>
        The seed determines the constellation — same seed always produces the same graph. The fig number follows
        the sequence: FIG. 002 Apollo, FIG. 003 PitchBook, FIG. 004 Memo, FIG. 005 Docs, FIG. 006+ next.
      </p>

      <H3>2. DOCX guide</H3>
      <p>
        Create <code>design/build_my_system.js</code>. Import from <code>./lib</code> and use the primitives —{' '}
        <code>chapter()</code>, <code>h2()</code>, <code>p()</code>, <code>table()</code>, <code>bullet()</code>,{' '}
        <code>note()</code>, <code>codeBlock()</code>, <code>closing()</code> — to build a <code>children</code>{' '}
        array, then call <code>build()</code> pointing at the cover PNG and the output path in{' '}
        <code>hub-next/public/guides/</code>. Run <code>node build_my_system.js</code>.
      </p>

      <H3>3. Hub page</H3>
      <p>
        Create a route under <code>hub-next/src/app/docs/projects/my-system/page.jsx</code> with a lead
        paragraph, the <code>&lt;GuideCard&gt;</code> component, and the content. Add the page to{' '}
        <code>hub-next/src/data/sidebarConfig.js</code> and add a row to the systems table on the AI Capabilities
        page.
      </p>

      <H2>lib.js primitives</H2>
      <table>
        <thead><tr><th>Function</th><th>What it produces</th></tr></thead>
        <tbody>
          {PRIMITIVES.map(([fn, desc]) => (
            <tr key={fn}><td><code>{fn}</code></td><td>{desc}</td></tr>
          ))}
        </tbody>
      </table>

      <Note>
        Table column widths must sum to exactly 9360 DXA (the 6.5-inch content width at 1-inch margins on US
        Letter). Common splits: 2400+6960 (25/75), 2800+6560 (30/70), 3200+6160 (35/65).
      </Note>

      <H2>Design system</H2>
      <p>
        The covers and document style are governed by the <strong>Latent Order</strong> design philosophy: a
        near-white paper ground, an ink approaching black, the grey between them — nothing more. The
        constellation on each cover is seeded deterministically, so it is unique to the guide but stable across
        regenerations. Full design philosophy in <code>design/DESIGN_PHILOSOPHY_Latent_Order.md</code>.
      </p>
    </>
  );
}
