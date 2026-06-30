import { loadDoc } from "@/lib/content";
import { BlockMarkdown } from "@/components/Markdown";

export const metadata = { title: "AI Capabilities" };

export default function OverviewPage() {
  const { content } = loadDoc("overview.md");
  return (
    <main className="container" style={{ paddingTop: "2.5rem", paddingBottom: "2rem" }}>
      <div className="prose"><BlockMarkdown>{content}</BlockMarkdown></div>
    </main>
  );
}
