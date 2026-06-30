import { loadDoc } from "@/lib/content";
import { stripMdx } from "@/lib/mdxLite";
import { BlockMarkdown } from "@/components/Markdown";
import GuideCard from "@/components/GuideCard";

export const metadata = { title: "Apollo Reach Out" };

export default function Page() {
  const { content } = loadDoc("projects/apollo-reach-out.md");
  const body = stripMdx(content);
  return (
    <main className="container" style={{ paddingTop: "2.5rem", paddingBottom: "2rem" }}>
      <div className="prose">
        <h1>Apollo Reach Out</h1>
        <p>
          Apollo Reach Out turns Apollo's contact database into a short, clean list of real
          family office and RIA decision-makers. It enriches each one and loads them into a
          managed outbound sequence.
        </p>
        <GuideCard
          title="Apollo Reach Out"
          meta="The formatted edition. Filters, enrichment, and sequence setup."
          cover="/img/cover_apollo.png"
          docx="/guides/ID8_Apollo_Reach_Out_Guide.docx"
        />
        <BlockMarkdown>{body.replace(/^# .+\n+/, "")}</BlockMarkdown>
      </div>
    </main>
  );
}
