import { loadDoc } from "@/lib/content";
import { stripMdx } from "@/lib/mdxLite";
import { BlockMarkdown } from "@/components/Markdown";
import IdeaBoard from "@/components/IdeaBoard";

export const metadata = { title: "Admin" };

export default function Page() {
  const { content } = loadDoc("admin/index.md");
  const body = stripMdx(content);
  return (
    <main className="container" style={{ paddingTop: "2.5rem", paddingBottom: "2rem" }}>
      <div className="prose">
        <h1>Admin</h1>
        <p>
          Capture ideas, suggestions, and requests as they come up. Working notes that do not
          belong on a project page also live here.
        </p>
        <h2>Capture</h2>
        <IdeaBoard />
        <BlockMarkdown>{body.replace(/^# .+\n+## Capture\n+/, "")}</BlockMarkdown>
      </div>
    </main>
  );
}
