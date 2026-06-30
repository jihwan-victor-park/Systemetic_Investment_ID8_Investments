import "server-only";

/**
 * The source docs are Docusaurus MDX: frontmatter + a JS `import` line + one
 * inline component tag (<GuideCard ... /> or <IdeaBoard />) + Docusaurus
 * `:::note` admonitions + repo-relative links into sibling source folders.
 * Rather than pull in a full MDX compiler for five pages, this strips those
 * MDX-only bits down to plain markdown that BlockMarkdown can render, and
 * the page component renders the one inline tag as a real React element.
 */
export function stripMdx(raw) {
  let body = raw
    .replace(/^import .+\n/m, "")
    .replace(/<(GuideCard|IdeaBoard)\b[^]*?\/>/, "")
    // Docusaurus admonitions -> blockquote, styled to match in globals.css.
    .replace(/:::note\n([^]*?)\n:::/g, (_, inner) => {
      const text = inner.trim().replace(/\n/g, "\n> ");
      return `> **Note:** ${text}`;
    })
    // Repo-relative source links (../../design/..., ../../*.md) don't resolve
    // as app routes — render as plain text instead of a dead link.
    .replace(/\[([^\]]+)\]\(\.\.\/\.\.\/[^)]+\)/g, "$1");
  return body.trim();
}
