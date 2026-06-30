import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const linkOut = {
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer">{children}</a>
  ),
};

/** Inline markdown (bold, citation links) with no wrapping <p> — for table cells. */
export function InlineMarkdown({ children }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{ ...linkOut, p: ({ children }) => <>{children}</> }}
    >
      {children || ""}
    </ReactMarkdown>
  );
}

/** Block markdown (paragraphs, lists) — for rationale and prose. */
export function BlockMarkdown({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={linkOut}>
      {children || ""}
    </ReactMarkdown>
  );
}
