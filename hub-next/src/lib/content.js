import "server-only";
import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";

const ROOT = path.join(process.cwd(), "src", "content");

/** Load a markdown doc under src/content; returns { data (frontmatter), content }. */
export function loadDoc(relPath) {
  const raw = fs.readFileSync(path.join(ROOT, relPath), "utf8");
  return matter(raw);
}
