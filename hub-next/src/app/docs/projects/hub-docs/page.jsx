import { loadDoc } from "@/lib/content";
import { stripMdx } from "@/lib/mdxLite";
import { BlockMarkdown } from "@/components/Markdown";
import GuideCard from "@/components/GuideCard";

export const metadata = { title: "Documentation System" };

export default function Page() {
  const { content } = loadDoc("projects/hub-docs.md");
  const body = stripMdx(content);
  return (
    <main className="container" style={{ paddingTop: "2.5rem", paddingBottom: "2rem" }}>
      <div className="prose">
        <h1>Documentation System</h1>
        <p>
          Every ID8 operating guide follows the same system: a cover image generated from
          the Latent Order design library, a formatted DOCX built from a JavaScript script
          using the shared <code>lib.js</code> primitives, and a page on this hub with a
          downloadable card. Adding documentation for a new system takes one script, one
          hub page, and three commands.
        </p>
        <GuideCard
          title="Documentation System"
          meta="The formatted edition. Cover generation, DOCX library, and hub integration."
          cover="/img/cover_hub_docs.png"
          docx="/guides/ID8_Documentation_System_Guide.docx"
        />
        <BlockMarkdown>{body.replace(/^# .+\n+/, "")}</BlockMarkdown>
      </div>
    </main>
  );
}
