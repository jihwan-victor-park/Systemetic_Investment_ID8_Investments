// ID8 "Latent Order" cover generator — writes one HTML per guide (rendered to PNG by Chrome).
// Each document gets its own constellation, seeded by the document so it is stable but unique.
const fs = require("fs");
const path = require("path");
const A = path.join(__dirname, "assets", "fonts");
const b64 = f => fs.readFileSync(path.join(A, f)).toString("base64");
const face = (fam, file, weight, style = "normal") =>
  `@font-face{font-family:'${fam}';font-weight:${weight};font-style:${style};src:url(data:font/ttf;base64,${b64(file)}) format('truetype');}`;

const PAPER = "#FBFAF7", INK = "#1A1A1A", GREY = "#828282", FAINT = "#E2DDD3", HAIR = "#CFC9BD";
const LOGO = fs.readFileSync(path.join(__dirname, "assets", "id8_charcoal.png")).toString("base64");
const W = 816, H = 1056, ML = 84, MR = 732;
const FX = 84, FY = 168, STEP = 24, COLS = 27, ROWS = 11;
const gx = c => FX + c * STEP, gy = r => FY + r * STEP;

// ── seeded RNG so each document's graph is unique but deterministic ──
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hashStr(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

function genField(seed) {
  const rng = mulberry32(hashStr(seed));
  const count = 8 + Math.floor(rng() * 2);            // 8-9 nodes
  const keys = "abcdefghij".split("");
  const N = {};
  const band = (COLS - 2) / count;
  for (let i = 0; i < count; i++) {
    const col = Math.max(1, Math.min(COLS - 1, 1 + Math.round(i * band + rng() * band * 0.7)));
    const row = 1 + Math.round(rng() * (ROWS - 3));    // keep off the top/bottom edge
    N[keys[i]] = [col, row];
  }
  const order = Object.keys(N).sort((a, b) => N[a][0] - N[b][0]);
  const E = [];
  for (let i = 0; i < order.length - 1; i++) E.push([order[i], order[i + 1]]); // clean left-to-right path
  const branches = 1 + Math.floor(rng() * 2);
  for (let b = 0; b < branches; b++) { const i = Math.floor(rng() * (order.length - 2)); E.push([order[i], order[i + 2]]); }
  // highlight the most-connected nodes (the hubs)
  const deg = {}; Object.keys(N).forEach(k => (deg[k] = 0));
  E.forEach(([a, b]) => { deg[a]++; deg[b]++; });
  const sig = Object.keys(N).sort((a, b) => deg[b] - deg[a]).slice(0, 2);
  const codes = ["VC", "LP", "DL", "ND", "CO"];
  const lab = {};
  order.filter((_, i) => i % 2 === 0).slice(0, 4).forEach((k, i) => {
    lab[k] = [`${codes[i % codes.length]} ${String(1 + Math.floor(rng() * 30)).padStart(2, "0")}`, 12, -9, "start"];
  });
  return { N, E, sig, lab, observed: 150 + (hashStr(seed) % 160) };
}

function fieldSvg(gen) {
  let t = "";
  for (let c = 0; c <= COLS; c++) for (let r = 0; r <= ROWS; r++) {
    const x = gx(c), y = gy(r);
    t += `<path d="M${x-2.2} ${y}H${x+2.2}M${x} ${y-2.2}V${y+2.2}" stroke="${FAINT}" stroke-width="0.8"/>`;
  }
  const { N, E, sig, lab } = gen;
  let s = "";
  for (const k of sig) { const x = gx(N[k][0]), y = gy(N[k][1]);
    s += `<circle cx="${x}" cy="${y}" r="14" fill="none" stroke="${INK}" stroke-width="0.6" opacity="0.26"/><circle cx="${x}" cy="${y}" r="23" fill="none" stroke="${INK}" stroke-width="0.5" opacity="0.14"/>`; }
  for (const [a, b] of E) s += `<line x1="${gx(N[a][0])}" y1="${gy(N[a][1])}" x2="${gx(N[b][0])}" y2="${gy(N[b][1])}" stroke="${INK}" stroke-width="0.9" opacity="0.82"/>`;
  for (const k in N) { const x = gx(N[k][0]), y = gy(N[k][1]); const ss = sig.includes(k);
    s += `<circle cx="${x}" cy="${y}" r="${ss?4.4:3.2}" fill="${ss?INK:PAPER}" stroke="${INK}" stroke-width="${ss?0:1.1}"/>`; }
  for (const k in lab) { const [tx, dx, dy, an] = lab[k]; s += `<text x="${gx(N[k][0])+dx}" y="${gy(N[k][1])+dy}" text-anchor="${an}" font-family="Sora" font-weight="500" font-size="8" letter-spacing="1.2" fill="${GREY}">${tx}</text>`; }
  return t + s;
}

function cover({ titleLines, subtitle, fig, plate, seed }) {
  const t1 = titleLines[0], t2 = titleLines[1] || "";
  const gen = genField(seed || fig);
  const connected = Object.keys(gen.N).length;
  const svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${PAPER}"/>
<image x="${ML}" y="74" width="212" height="21" href="data:image/png;base64,${LOGO}"/>
<text x="${MR}" y="92" text-anchor="end" font-family="Sora" font-weight="400" font-size="11" letter-spacing="3.4" fill="${GREY}">CLOUD INTELLIGENCE</text>
<line x1="${ML}" y1="106" x2="${MR}" y2="106" stroke="${INK}" stroke-width="1"/>
<text x="${ML}" y="128" font-family="Sora" font-weight="400" font-size="8" letter-spacing="2.2" fill="${GREY}">${fig}</text>
<text x="${MR}" y="128" text-anchor="end" font-family="Sora" font-weight="400" font-size="8" letter-spacing="2.2" fill="${GREY}">${plate}</text>
<g>${fieldSvg(gen)}</g>
<text x="${MR}" y="${gy(ROWS)+26}" text-anchor="end" font-family="Sora" font-weight="500" font-size="8" letter-spacing="1.6" fill="${GREY}">N = ${gen.observed} OBSERVED | ${connected} CONNECTED</text>
<line x1="${ML}" y1="${gy(ROWS)+44}" x2="${MR}" y2="${gy(ROWS)+44}" stroke="${HAIR}" stroke-width="0.8"/>
<text x="${ML}" y="556" font-family="Sora" font-weight="500" font-size="10" letter-spacing="3" fill="${GREY}">OPERATING GUIDE</text>
<text x="${ML-3}" y="624" font-family="Roboto Serif" font-weight="300" font-size="56" fill="${INK}">${t1}</text>
${t2 ? `<text x="${ML-3}" y="688" font-family="Roboto Serif" font-weight="300" font-size="56" fill="${INK}">${t2}</text>` : ""}
<foreignObject x="${ML}" y="720" width="520" height="120">
  <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Sora;font-weight:300;font-size:15px;line-height:1.5;color:${INK};">${subtitle}</div>
</foreignObject>
<text x="${ML}" y="912" font-family="Roboto Serif" font-weight="300" font-style="italic" font-size="26" fill="${INK}">Ambitious ideas.</text>
<line x1="${ML}" y1="970" x2="${MR}" y2="970" stroke="${HAIR}" stroke-width="0.8"/>
<text x="${ML}" y="992" font-family="Sora" font-weight="400" font-size="8" letter-spacing="2" fill="${GREY}">INTERNAL | CONFIDENTIAL | JUNE 2026</text>
<text x="${MR}" y="992" text-anchor="end" font-family="Sora" font-weight="500" font-size="8" letter-spacing="2" fill="${INK}">id8investments.com</text>
</svg>`;
  return `<!doctype html><html><head><meta charset="utf-8"><style>
${face("Sora","Sora-Light.ttf",300)}${face("Sora","Sora-Regular.ttf",400)}${face("Sora","Sora-Medium.ttf",500)}${face("Sora","Sora-SemiBold.ttf",600)}
${face("Roboto Serif","RobotoSerif-Light.ttf",300)}${face("Roboto Serif","RobotoSerif-LightItalic.ttf",300,"italic")}
@page{size:8.5in 11in;margin:0}html,body{margin:0;padding:0;background:${PAPER}}svg{display:block;width:8.5in;height:11in}
</style></head><body>${svg}</body></html>`;
}

const builds = [
  { out: "cover_apollo.html", seed: "apollo-reach-out", titleLines: ["Apollo", "Reach Out"],
    subtitle: "Building clean family office and RIA lists, enriching them, then launching outbound sequences.",
    fig: "FIG. 002 | OUTBOUND FIELD", plate: "PLATE | LATENT ORDER" },
  { out: "cover_pitchbook.html", seed: "pitchbook-attio-pipeline", titleLines: ["PitchBook →", "Attio Pipeline"],
    subtitle: "Syncing deal, company, and investor data into Attio with reliable investor linking.",
    fig: "FIG. 003 | PIPELINE FIELD", plate: "PLATE | LATENT ORDER" },
  { out: "cover_investment_memo.html", seed: "investment-memo-generator", titleLines: ["Investment", "Memo Generator"],
    subtitle: "16-agent workflow that writes complete investment memos from raw deal data in 15–20 minutes.",
    fig: "FIG. 004 | MEMO ENGINE", plate: "PLATE | LATENT ORDER" },
  { out: "cover_hub_docs.html", seed: "hub-documentation-system", titleLines: ["Documentation", "System"],
    subtitle: "Building and publishing operating guides to the ID8 hub — cover, DOCX, and web page.",
    fig: "FIG. 005 | GUIDE FIELD", plate: "PLATE | LATENT ORDER" },
];
for (const b of builds) { fs.writeFileSync(path.join(__dirname, b.out), cover(b)); console.log("wrote", b.out); }
