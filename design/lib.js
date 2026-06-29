// ID8 "Latent Order" DOCX library. Tight spacing, no boxes, editorial hairline tables.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  Footer, AlignmentType, LevelFormat, TableOfContents, HeadingLevel, BorderStyle,
  WidthType, VerticalAlign, PageNumber, TabStopType,
} = require("docx");

const C = { CHARCOAL: "1A1A1A", GREY: "828282", WHITE: "FFFFFF", HAIR: "E4DFD5", SOFT: "3C3C3C" };
const HEAD = "Roboto Serif";
const BODY = "Sora";
const MONO = "Roboto Mono, Consolas, Courier New";
const CONTENT_W = 9360;
const ASSETS = path.join(__dirname, "assets");
const logoDims = w => ({ width: w, height: Math.round(w * 223 / 2257) });

function contents() {
  return [
    new Paragraph({ spacing: { after: 100 }, children: [
      new TextRun({ text: "Contents", font: HEAD, size: 30, bold: true, color: C.CHARCOAL })] }),
    new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  ];
}

// Chapter heading: small number + serif title on one line, hairline under it. No page break.
function chapter(num, title) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 90 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.CHARCOAL, space: 6 } },
    children: [
      ...(num != null ? [new TextRun({ text: String(num).padStart(2, "0") + "   ", font: BODY, size: 20, color: C.GREY })] : []),
      new TextRun({ text: title, font: HEAD, size: 28, bold: true, color: C.CHARCOAL })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 180, after: 50 },
    children: [new TextRun({ text, font: BODY, size: 22, bold: true, color: C.CHARCOAL })] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 120, after: 40 },
    children: [new TextRun({ text, font: BODY, size: 20, bold: true, color: C.SOFT })] });
}
function p(text, opts = {}) {
  const runs = Array.isArray(text) ? text : [new TextRun({ text, font: BODY, size: 21, color: C.CHARCOAL })];
  return new Paragraph({ spacing: { after: 80 }, ...opts, children: runs });
}
function run(text, o = {}) { return new TextRun({ text, font: BODY, size: 21, color: C.CHARCOAL, ...o }); }
function bold(text) { return new TextRun({ text, font: BODY, size: 21, bold: true, color: C.CHARCOAL }); }
function code(text) { return new TextRun({ text, font: MONO, size: 19, color: C.CHARCOAL }); }

function bullet(runs) {
  const children = Array.isArray(runs) ? runs : [new TextRun({ text: runs, font: BODY, size: 21, color: C.CHARCOAL })];
  return new Paragraph({ numbering: { reference: "id8-bullets", level: 0 }, spacing: { after: 24 }, children });
}
function num(runs, ref = "id8-numbers") {
  const children = Array.isArray(runs) ? runs : [new TextRun({ text: runs, font: BODY, size: 21, color: C.CHARCOAL })];
  return new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 24 }, children });
}

// Note: bold lead-in, no box, no fill.
function note(runsOrText) {
  const body = Array.isArray(runsOrText) ? runsOrText : [new TextRun({ text: runsOrText, font: BODY, size: 21, color: C.CHARCOAL })];
  return new Paragraph({ spacing: { before: 40, after: 100 }, children: [
    new TextRun({ text: "Note  ", font: BODY, size: 18, bold: true, color: C.CHARCOAL, allCaps: true, characterSpacing: 40 }),
    ...body] });
}

// Code: monospace, indented, no box.
function codeBlock(lines) {
  const arr = Array.isArray(lines) ? lines : [lines];
  return arr.map((l, i) => new Paragraph({ spacing: { before: i === 0 ? 40 : 0, after: i === arr.length - 1 ? 100 : 0 },
    indent: { left: 240 }, children: [new TextRun({ text: l || " ", font: MONO, size: 19, color: C.SOFT })] }));
}

// Editorial table: no fills, no vertical lines, tight padding, small-caps header over one rule.
function table(headers, rows, widths) {
  const none = { style: BorderStyle.NONE };
  const hair = { style: BorderStyle.SINGLE, size: 4, color: C.HAIR };
  const rule = { style: BorderStyle.SINGLE, size: 8, color: C.CHARCOAL };
  const cellB = b => ({ top: none, left: none, right: none, bottom: b });
  const headerRow = new TableRow({ tableHeader: true, children: headers.map((hh, i) =>
    new TableCell({ borders: cellB(rule), width: { size: widths[i], type: WidthType.DXA }, margins: { top: 20, bottom: 50, left: 0, right: 160 },
      children: [new Paragraph({ children: [new TextRun({ text: hh, font: BODY, size: 15, bold: true, color: C.CHARCOAL, allCaps: true, characterSpacing: 50 })] })] })) });
  const bodyRows = rows.map(r => new TableRow({ children: r.map((cell, i) =>
    new TableCell({ borders: cellB(hair), width: { size: widths[i], type: WidthType.DXA }, margins: { top: 50, bottom: 50, left: 0, right: 160 }, verticalAlign: VerticalAlign.TOP,
      children: (Array.isArray(cell) ? cell : [cell]).map(line =>
        new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: line, font: BODY, size: 19, color: i === 0 ? C.CHARCOAL : C.SOFT })] })) })) }));
  return new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths,
    borders: { top: none, bottom: none, left: none, right: none, insideHorizontal: none, insideVertical: none },
    rows: [headerRow, ...bodyRows] });
}

function good(text) { return new Paragraph({ spacing: { after: 24 }, children: [run("Keep   ", { bold: true }), run(text)] }); }
function bad(text) { return new Paragraph({ spacing: { after: 24 }, children: [run("Drop   ", { bold: true, color: C.GREY }), run(text)] }); }
function check(text) { return new Paragraph({ numbering: { reference: "id8-bullets", level: 0 }, spacing: { after: 24 }, children: [run(text)] }); }
function spacer(h = 40) { return new Paragraph({ spacing: { after: h }, children: [] }); }

function closing() {
  return [
    new Paragraph({ spacing: { before: 600 }, border: { top: { style: BorderStyle.SINGLE, size: 4, color: C.HAIR, space: 8 } }, children: [] }),
    new Paragraph({ spacing: { before: 120 }, children: [
      new ImageRun({ type: "png", data: fs.readFileSync(path.join(ASSETS, "id8_charcoal.png")), transformation: logoDims(150),
        altText: { title: "ID8", description: "ID8 logo", name: "logo" } })] }),
    new Paragraph({ spacing: { before: 40 }, children: [
      new TextRun({ text: "Ambitious ideas.", font: HEAD, size: 22, italics: true, color: C.CHARCOAL })] }),
    new Paragraph({ spacing: { before: 20 }, children: [
      new TextRun({ text: "id8investments.com", font: BODY, size: 16, color: C.GREY })] }),
  ];
}

function build(outPath, title, sectionChildren, coverPng) {
  const numbering = { config: [
    { reference: "id8-bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "—", alignment: AlignmentType.LEFT,
      style: { run: { font: BODY, color: C.GREY }, paragraph: { indent: { left: 360, hanging: 220 } } } }] },
    { reference: "id8-numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1", alignment: AlignmentType.LEFT,
      style: { run: { color: C.GREY }, paragraph: { indent: { left: 360, hanging: 220 } } } }] },
  ]};
  const styles = { default: { document: { run: { font: BODY, size: 21, color: C.CHARCOAL } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: HEAD, size: 28, bold: true, color: C.CHARCOAL }, paragraph: { spacing: { before: 320, after: 90 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: BODY, size: 22, bold: true, color: C.CHARCOAL }, paragraph: { spacing: { before: 180, after: 50 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: BODY, size: 20, bold: true, color: C.SOFT }, paragraph: { spacing: { before: 120, after: 40 }, outlineLevel: 2 } },
    ] };
  const footer = new Footer({ children: [ new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: 9360 }],
    border: { top: { style: BorderStyle.SINGLE, size: 4, color: C.HAIR, space: 6 } },
    children: [
      new TextRun({ text: "ID8 Investments  |  Confidential", font: BODY, size: 15, color: C.GREY }),
      new TextRun({ text: "\t", font: BODY, size: 15 }),
      new TextRun({ children: [PageNumber.CURRENT], font: BODY, size: 15, color: C.GREY })] }) ] });
  const coverSection = coverPng ? {
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 0, right: 0, bottom: 0, left: 0 } } },
    children: [ new Paragraph({ spacing: { after: 0 }, children: [ new ImageRun({ type: "png",
      data: fs.readFileSync(coverPng), transformation: { width: 816, height: 1054 },
      altText: { title: "ID8 cover", description: title, name: "cover" } }) ] }) ],
  } : null;
  const contentSection = {
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: footer },
    children: sectionChildren,
  };
  const doc = new Document({ styles, numbering, features: { updateFields: true },
    sections: coverSection ? [coverSection, contentSection] : [contentSection] });
  return Packer.toBuffer(doc).then(buf => fs.writeFileSync(outPath, buf));
}

module.exports = { C, HEAD, BODY, MONO, contents, chapter, h2, h3, p, run, bold, code,
  bullet, num, codeBlock, note, table, good, bad, check, spacer, closing, build };
