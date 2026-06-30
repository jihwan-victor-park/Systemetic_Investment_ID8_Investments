import { loadDoc } from "@/lib/content";
import { stripMdx } from "@/lib/mdxLite";
import { BlockMarkdown } from "@/components/Markdown";
import GuideCard from "@/components/GuideCard";

export const metadata = { title: "Investment Memo Generator" };

export default function Page() {
  const { content } = loadDoc("projects/investment-memo.md");
  const body = stripMdx(content);
  return (
    <main className="container" style={{ paddingTop: "2.5rem", paddingBottom: "2rem" }}>
      <div className="prose">
        <h1>Investment Memo Generator</h1>
        <p>
          The Investment Memo Generator turns raw deal data — a pitch deck, term sheet,
          PitchBook profile, or just a company name and round details — into a complete,
          formatted DOCX investment memo in the ID8 canonical style. A 16-agent workflow
          handles intake, research, parallel section writing, and editorial assembly. The
          output reads like the Polymarket, Saronic, and Hadrian memos the format was
          derived from.
        </p>
        <GuideCard
          title="Investment Memo Generator"
          meta="The formatted edition. Workflow, sections, output format, and reference."
          cover="/img/cover_investment_memo.png"
          docx="/guides/ID8_Investment_Memo_Generator_Guide.docx"
        />
        <BlockMarkdown>{body.replace(/^# .+\n+/, "")}</BlockMarkdown>
      </div>
    </main>
  );
}
