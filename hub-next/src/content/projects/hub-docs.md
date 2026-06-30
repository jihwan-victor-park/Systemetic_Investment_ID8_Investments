---
title: Documentation System
description: How ID8 operating guides are built and published — cover, DOCX, and hub page.
---

import GuideCard from '@site/src/components/GuideCard';

# Documentation System

Every ID8 operating guide follows the same system: a cover image generated from the Latent Order design library, a formatted DOCX built from a JavaScript script using the shared `lib.js` primitives, and a page on this hub with a downloadable card. Adding documentation for a new system takes one script, one hub page, and three commands.

<GuideCard
  title="Documentation System"
  meta="The formatted edition. Cover generation, DOCX library, and hub integration."
  cover="/img/cover_hub_docs.png"
  docx="/guides/ID8_Documentation_System_Guide.docx" />

| | Detail |
| --- | --- |
| Design system | Latent Order — `design/lib.js`, `design/build_cover.js` |
| Output | Cover PNG + DOCX guide + Docusaurus hub page |
| Code | `design/build_*.js`, `hub/docs/projects/*.md` |

## How it works

Each guide is three things: a cover, a DOCX, and a hub page. They are built in order.

### 1. Cover image

Open [`design/build_cover.js`](../../design/build_cover.js) and add an entry to the `builds` array with a unique seed string, title lines, subtitle, and fig number. Run `node build_cover.js` to generate the HTML, then render to PNG via Chrome headless at 816×1056. Copy the PNG to `hub/static/img/`.

The seed determines the constellation — same seed always produces the same graph. The fig number follows the sequence: FIG. 002 Apollo, FIG. 003 PitchBook, FIG. 004 Memo, FIG. 005 Docs, FIG. 006+ next.

### 2. DOCX guide

Create `design/build_my_system.js`. Import from `./lib` and use the primitives — `chapter()`, `h2()`, `p()`, `table()`, `bullet()`, `note()`, `codeBlock()`, `closing()` — to build a `children` array, then call `build()` pointing at the cover PNG and the output path in `hub/static/guides/`. Run `node build_my_system.js`.

### 3. Hub page

Create `hub/docs/projects/my-system.md` with frontmatter, a lead paragraph, the `<GuideCard>` component, and the content. Add the page to `hub/sidebars.js` and add a row to the systems table in `hub/docs/overview.md`.

## lib.js primitives

| Function | What it produces |
| --- | --- |
| `chapter(num, title)` | Section heading — grey number + serif title, hairline rule, added to TOC |
| `h2(text)` | Sub-heading, Sora bold 11pt, added to TOC |
| `h3(text)` | Third-level heading, Sora bold 10pt, muted |
| `p(text \| runs[])` | Body paragraph — pass a string or a `run()` / `bold()` / `code()` array |
| `run(text)` | Inline text run |
| `bold(text)` | Bold inline run |
| `code(text)` | Monospace inline run for filenames, commands, identifiers |
| `bullet(text \| runs[])` | Em-dash bullet item |
| `note(text \| runs[])` | Note callout — bold NOTE lead-in, no box |
| `table(headers, rows, widths)` | Editorial table — no fills, no vertical lines, hairline separators. Widths in DXA, must sum to 9360 |
| `codeBlock(lines[])` | Monospace indented block — spread with `...` |
| `check(text \| runs[])` | Checklist bullet |
| `closing()` | Document close — hairline, logo, tagline. Always last, spread with `...` |
| `contents()` | TOC heading and field. Always first, spread with `...` |

:::note
Table column widths must sum to exactly 9360 DXA (the 6.5-inch content width at 1-inch margins on US Letter). Common splits: 2400+6960 (25/75), 2800+6560 (30/70), 3200+6160 (35/65).
:::

## Design system

The covers and document style are governed by the **Latent Order** design philosophy: a near-white paper ground, an ink approaching black, the grey between them — nothing more. The constellation on each cover is seeded deterministically, so it is unique to the guide but stable across regenerations. Full design philosophy in [`design/DESIGN_PHILOSOPHY_Latent_Order.md`](../../design/DESIGN_PHILOSOPHY_Latent_Order.md).
