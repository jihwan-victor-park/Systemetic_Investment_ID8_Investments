import { loadDoc } from "@/lib/content";
import { stripMdx } from "@/lib/mdxLite";
import { BlockMarkdown } from "@/components/Markdown";
import GuideCard from "@/components/GuideCard";

export const metadata = { title: "PitchBook → Attio Pipeline" };

export default function Page() {
  const { content } = loadDoc("projects/pitchbook-attio.md");
  const body = stripMdx(content);
  return (
    <main className="container" style={{ paddingTop: "2.5rem", paddingBottom: "2rem" }}>
      <div className="prose">
        <h1>PitchBook → Attio Pipeline</h1>
        <p>
          This pipeline reads PitchBook exports of deals, companies, and investors and writes
          them into ID8's Attio CRM. It creates and updates Deal and Company records, stages
          deals, and links each deal to the VC firms that invested so the investor graph in
          Attio stays accurate.
        </p>
        <GuideCard
          title="PitchBook → Attio Pipeline"
          meta="The formatted edition. Investor linking, write formats, and backfill."
          cover="/img/cover_pitchbook.png"
          docx="/guides/ID8_PitchBook_Attio_Pipeline_Guide.docx"
        />
        <BlockMarkdown>{body.replace(/^# .+\n+/, "")}</BlockMarkdown>
      </div>
    </main>
  );
}
