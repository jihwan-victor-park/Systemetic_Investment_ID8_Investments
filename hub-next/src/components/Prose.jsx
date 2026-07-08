// Heading helpers for hand-authored docs content — auto-slugs an id from the
// heading text, the same way Docusaurus auto-slugs markdown headings, so the
// DocsShell's client-side TOC scan has something stable to link to.
import { slugify } from '@/lib/slugify';

export function H2({ children }) {
  return <h2 id={slugify(children)}>{children}</h2>;
}

export function H3({ children }) {
  return <h3 id={slugify(children)}>{children}</h3>;
}
