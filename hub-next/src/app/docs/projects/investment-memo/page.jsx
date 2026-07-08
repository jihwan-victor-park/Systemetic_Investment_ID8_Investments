import { H2, H3 } from '@/components/Prose';
import { Note } from '@/components/Admonition';
import GuideCard from '@/components/GuideCard';

export const metadata = { title: 'Investment Memo Generator', description: 'Multi-agent system that writes a complete ID8 investment memo from raw deal data.' };

const SECTIONS = [
  ['1', 'Investment Overview', 'Executive summary — thesis bullets, key risks, conviction statement. Reader who only reads this understands the full thesis.'],
  ['2', 'Investment Highlights', '4–5 named thesis pillars, each a bold H2 followed by 2–3 quantified prose paragraphs. No bullets — all analytical narrative.'],
  ['3', 'Business Overview', 'What the company builds, sells, and operates. Product table if hardware or multi-product; "What Trades" table if marketplace.'],
  ['4', 'Revenue Model', 'One H2 per revenue stream: mechanism, current scale, and projected unit economics.'],
  ['5', 'Addressable Market', "TAM methodology, why the market is expanding now, company's current penetration vs. TAM."],
  ['6', 'Founder & Management Team', 'One H2 per founder or key exec: prior companies, exits, domain credentials. Advisory board if notable.'],
  ['7', 'Raise Timeline', 'Full funding history table: Round — Date — Size — Post-Money — Lead Investor(s).'],
  ['8', 'Competitor Overview', 'Competitive landscape narrative + 4–7 row competitor matrix with threat level and rationale per competitor.'],
  ['9', 'Lead Investor', 'Strategic profile, fund performance table, and a section on why this lead chose this company.'],
  ['10', 'Financial Snapshot', 'Key metrics table: revenue, growth, gross margin, EBITDA, valuation, revenue multiple. Footnoted source and date.'],
  ['11', 'Valuation', 'Comps table (5–8 private and public peers), entry multiple analysis, path to multiple re-rate, optional scenario analysis.'],
  ['12', 'Exit & Monetization Considerations', 'IPO path, strategic acquisition (named buyer universe), secondary liquidity. Bear/Base/Bull exit scenario table.'],
  ['13', 'Risk Factors', '5–6 named risks. Each: 2–4 sentence problem citing specific entities → mitigant bullet 3–5× longer, naming partners, dates, and programs.'],
  ['14', 'Key Investment Assumptions', '5–7 numbered, falsifiable assumptions the thesis depends on — specific enough to monitor as the deal ages.'],
];

export default function InvestmentMemoPage() {
  return (
    <>
      <h1>Investment Memo Generator</h1>
      <p>
        The Investment Memo Generator turns raw deal data — a pitch deck, term sheet, PitchBook profile, or just
        a company name and round details — into a complete, formatted DOCX investment memo in the ID8 canonical
        style. A 16-agent workflow handles intake, research, parallel section writing, and editorial assembly.
        The output reads like the Polymarket, Saronic, and Hadrian memos the format was derived from.
      </p>

      <GuideCard
        title="Investment Memo Generator"
        meta="The formatted edition. Workflow, sections, output format, and reference."
        cover="/img/cover_investment_memo.png"
        docx="/guides/ID8_Investment_Memo_Generator_Guide.docx"
      />

      <table>
        <tbody>
          <tr><td>Invoke</td><td><code>/investment-memo</code> in Claude Code</td></tr>
          <tr><td>Output</td><td><code>.docx</code> file, ~4,000–7,000 words across 14 sections</td></tr>
          <tr><td>Data sources</td><td>User documents + PitchBook + web search (auto-filled on gaps)</td></tr>
          <tr><td>Runtime</td><td>15–20 minutes, ~500k tokens</td></tr>
        </tbody>
      </table>

      <H2>How to use it</H2>
      <p>
        Type <code>/investment-memo</code> in Claude Code. Before the workflow runs, Claude will ask for any
        missing inputs. The minimum you need is a company name, deal type, and basic round terms. Everything
        else can be sourced from PitchBook and the web automatically.
      </p>
      <p><strong>Fastest path:</strong> provide the company name and deal description. The intake agent fills the rest.</p>

      <Note>
        The workflow takes 15–20 minutes and consumes roughly 500k tokens across its 16 agents. Run it only on
        deals that have cleared initial review.
      </Note>

      <p>
        <strong>Richest output:</strong> attach a pitch deck, term sheet, and financial model before running.
        The agents prioritize your documents over external sources and flag any conflicts with external data.
      </p>

      <H3>What to provide</H3>
      <table>
        <thead><tr><th>Input</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td>Company name</td><td>Required</td></tr>
          <tr><td>One-line description</td><td>Optional — intake agent will draft one if missing</td></tr>
          <tr><td>Deal type</td><td>e.g. &quot;Series D — Preferred Stock&quot;, &quot;Founder Secondary — Common Stock&quot;</td></tr>
          <tr><td>Round terms</td><td>Security type, round size, pre-money, post-money, lead investor, prior round</td></tr>
          <tr><td>Memo date</td><td>e.g. &quot;June 2026&quot;</td></tr>
          <tr><td>Attached documents</td><td>Pitch deck, financial model, term sheet, IC presentation — all optional but each one adds depth</td></tr>
        </tbody>
      </table>

      <Note>
        If your data conflicts with what PitchBook or web search returns (e.g. a different valuation), Claude
        surfaces the conflict before running and uses your figure unless you say otherwise.
      </Note>

      <H2>The workflow</H2>
      <p>The workflow runs four sequential phases with 16 agents total.</p>
      <pre><code>Intake  →  Brief  →  Write (14 agents in parallel)  →  Edit</code></pre>
      <table>
        <thead><tr><th>Phase</th><th>What happens</th></tr></thead>
        <tbody>
          <tr>
            <td><strong>Intake</strong></td>
            <td>One agent digests all raw input — your documents, PitchBook data, and web research — into a structured company brief. Data gaps are flagged as <code>DATA GAP:</code>. Conflicts are flagged as <code>CONFLICT: user says X, external says Y</code>.</td>
          </tr>
          <tr>
            <td><strong>Brief</strong></td>
            <td>The structured brief is packaged into 14 section-specific data blocks, each containing only the facts relevant to that section.</td>
          </tr>
          <tr>
            <td><strong>Write</strong></td>
            <td>14 agents run in parallel, each writing one section independently from its brief. Agents write to the style guide: institutional voice, no hedging in body text, every paragraph anchored to a specific figure or named entity.</td>
          </tr>
          <tr>
            <td><strong>Edit</strong></td>
            <td>One editorial agent assembles all 14 sections, adds cross-references between sections, verifies internal consistency, and finalizes the complete memo.</td>
          </tr>
        </tbody>
      </table>

      <H2>The 14 sections</H2>
      <table>
        <thead><tr><th>#</th><th>Section</th><th>What it covers</th></tr></thead>
        <tbody>
          {SECTIONS.map(([num, name, desc]) => (
            <tr key={num}><td>{num}</td><td><strong>{name}</strong></td><td>{desc}</td></tr>
          ))}
        </tbody>
      </table>

      <H2>Output format</H2>
      <p>The output is a <code>.docx</code> file built to the ID8 canonical style. Typography, table formatting, color palette, and section spacing all match the reference memos exactly.</p>
      <table>
        <thead><tr><th>Element</th><th>Style</th></tr></thead>
        <tbody>
          <tr><td>Section headings</td><td>Roboto Serif 16pt bold, bottom border rule</td></tr>
          <tr><td>Body text</td><td>Sora 11pt justified, #1a1a1a</td></tr>
          <tr><td>Table headers</td><td>Sora 9pt bold white on #1a1a1a</td></tr>
          <tr><td>Table rows</td><td>Alternating #f5f5f5 / white</td></tr>
          <tr><td>Exit scenario rows</td><td>Bear = amber (#fff6e5), Bull = green (#eaf3de)</td></tr>
          <tr><td>Footer</td><td>Page number, Sora 8.5pt #828282, centered</td></tr>
        </tbody>
      </table>
      <p>The file saves to your Downloads folder by default. You can specify a different path when prompted.</p>

      <H2>Writing voice</H2>
      <p>Agents write in the same institutional style throughout.</p>
      <ul>
        <li><strong>Declarative and third-person.</strong> No first-person. No hedging in body text — hedging belongs only in footnotes.</li>
        <li><strong>Quantitatively dense.</strong> Every paragraph contains at least one specific dollar figure, percentage, date, or named entity.</li>
        <li><strong>No superlatives.</strong> Precise comparative framing: &quot;the only company that simultaneously holds X, Y, and Z&quot; not &quot;the best.&quot;</li>
        <li><strong>Cross-references named explicitly.</strong> Sections refer to each other: &quot;discussed in detail in the Risk Factors section.&quot;</li>
        <li><strong>Data attributed.</strong> Figures cite their source: &quot;per PitchBook&quot;, &quot;per management&quot;, &quot;per Bloomberg&quot;.</li>
      </ul>

      <H2>Data gap behavior</H2>
      <p>
        When the intake agent cannot find data for a required field, it writes a <code>DATA GAP:</code>
        placeholder so the editorial agent and you can see exactly what is missing. It will not invent figures.
        If a section has too many gaps to write substantively, it is flagged for manual review in the final report.
      </p>

      <H2>Technical reference</H2>
      <table>
        <thead><tr><th>File</th><th>Role</th></tr></thead>
        <tbody>
          <tr><td><code>.claude/skills/investment-memo/scripts/workflow.js</code></td><td>Workflow orchestration — 4 phases, 16 agents</td></tr>
          <tr><td><code>.claude/skills/investment-memo/scripts/build_memo.py</code></td><td>DOCX builder — converts JSON memo output to formatted Word file</td></tr>
          <tr><td><code>.claude/skills/investment-memo/references/style-guide.md</code></td><td>Typography, color palette, table system, writing voice</td></tr>
          <tr><td><code>.claude/skills/investment-memo/references/section-guide.md</code></td><td>Per-section structure, length targets, analytical requirements</td></tr>
        </tbody>
      </table>
    </>
  );
}
