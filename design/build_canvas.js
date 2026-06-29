// ID8 — "Latent Order" canvas. Renders a portrait Letter HTML for Chrome → PDF.
const fs = require("fs");
const path = require("path");
const A = path.join(__dirname, "assets", "fonts");
const b64 = f => fs.readFileSync(path.join(A, f)).toString("base64");
const face = (fam, file, weight, style = "normal") =>
  `@font-face{font-family:'${fam}';font-weight:${weight};font-style:${style};src:url(data:font/ttf;base64,${b64(file)}) format('truetype');}`;

// ---- palette ----
const PAPER = "#FBFAF7", INK = "#1A1A1A", GREY = "#828282", FAINT = "#E2DDD3", HAIR = "#CFC9BD";

// ---- geometry (816 x 1056 = 8.5x11in @96dpi) ----
const W = 816, H = 1056, ML = 84, MR = 732;
const FX = 84, FY = 174, STEP = 27, COLS = 24, ROWS = 20; // field origin + lattice
const gx = c => FX + c * STEP, gy = r => FY + r * STEP;

// ---- lattice of faint ticks ----
let ticks = "";
for (let c = 0; c <= COLS; c++) for (let r = 0; r <= ROWS; r++) {
  const x = gx(c), y = gy(r);
  ticks += `<path d="M${x-2.4} ${y}H${x+2.4}M${x} ${y-2.4}V${y+2.4}" stroke="${FAINT}" stroke-width="0.9"/>`;
}

// ---- the constellation (hand-placed nodes; an intentional, asymmetric figure) ----
const N = { A:[3,4], B:[7,2], C:[10,6], D:[6,9], E:[13,11], F:[17,7], G:[20,3], H:[15,15], I:[9,17], J:[21,14], K:[4,13] };
const E = [["A","B"],["B","C"],["C","D"],["C","F"],["F","G"],["F","E"],["E","H"],["D","I"],["H","J"],["E","J"],["D","K"]];
const signal = ["C","E"]; // nodes that radiate concentric rings
const labels = { B:["VC · 07", 10, -10, "start"], C:["LP · 01", 20, 4, "start"], E:["DL · 12", 20, 4, "start"], I:["ND · 04", -12, 16, "end"], G:["SIG", 11, 4, "start"] };

let edges = "";
for (const [a, b] of E) edges += `<line x1="${gx(N[a][0])}" y1="${gy(N[a][1])}" x2="${gx(N[b][0])}" y2="${gy(N[b][1])}" stroke="${INK}" stroke-width="0.9" opacity="0.82"/>`;

let rings = "";
for (const k of signal) { const x = gx(N[k][0]), y = gy(N[k][1]);
  rings += `<circle cx="${x}" cy="${y}" r="15" fill="none" stroke="${INK}" stroke-width="0.6" opacity="0.28"/>`;
  rings += `<circle cx="${x}" cy="${y}" r="25" fill="none" stroke="${INK}" stroke-width="0.5" opacity="0.16"/>`;
}

let nodes = "";
for (const k in N) { const x = gx(N[k][0]), y = gy(N[k][1]); const sig = signal.includes(k);
  nodes += `<circle cx="${x}" cy="${y}" r="${sig ? 4.6 : 3.4}" fill="${sig ? INK : PAPER}" stroke="${INK}" stroke-width="${sig ? 0 : 1.1}"/>`;
}
let labtext = "";
for (const k in labels) { const [t, dx, dy, anc] = labels[k]; const x = gx(N[k][0]) + dx, y = gy(N[k][1]) + dy;
  labtext += `<text x="${x}" y="${y}" text-anchor="${anc}" font-family="Sora" font-weight="500" font-size="8" letter-spacing="1.2" fill="${GREY}">${t}</text>`;
}

// ---- subtle axis numerals (engineering-plate cue) ----
let axis = "";
for (const c of [0,5,10,15,20]) axis += `<text x="${gx(c)}" y="${gy(ROWS)+22}" text-anchor="middle" font-family="Sora" font-weight="400" font-size="7" letter-spacing="1" fill="${HAIR}">${String(c).padStart(2,"0")}</text>`;
for (const r of [0,5,10,15,20]) axis += `<text x="${FX-16}" y="${gy(r)+2.5}" text-anchor="end" font-family="Sora" font-weight="400" font-size="7" letter-spacing="1" fill="${HAIR}">${String(r).padStart(2,"0")}</text>`;

const svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${PAPER}"/>

<!-- header -->
<text x="${ML}" y="92" font-family="Sora" font-weight="600" font-size="11" letter-spacing="3.4" fill="${INK}">ID8 INVESTMENTS</text>
<text x="${MR}" y="92" text-anchor="end" font-family="Sora" font-weight="400" font-size="11" letter-spacing="3.4" fill="${GREY}">CLOUD INTELLIGENCE</text>
<line x1="${ML}" y1="106" x2="${MR}" y2="106" stroke="${INK}" stroke-width="1"/>
<text x="${ML}" y="128" font-family="Sora" font-weight="400" font-size="8" letter-spacing="2.2" fill="${GREY}">FIG. 001 — SIGNAL FIELD</text>
<text x="${MR}" y="128" text-anchor="end" font-family="Sora" font-weight="400" font-size="8" letter-spacing="2.2" fill="${GREY}">PLATE · LATENT ORDER</text>

<!-- field -->
<g>${ticks}</g>
<g>${rings}</g>
<g>${edges}</g>
<g>${nodes}</g>
<g>${labtext}</g>
<g>${axis}</g>
<text x="${MR}" y="${gy(ROWS)+22}" text-anchor="end" font-family="Sora" font-weight="500" font-size="8" letter-spacing="1.6" fill="${GREY}">N = 247 OBSERVED · 11 CONNECTED</text>

<!-- hero -->
<text x="${ML}" y="812" font-family="Sora" font-weight="500" font-size="10" letter-spacing="3" fill="${GREY}">STRUCTURE, DISCOVERED IN THE NOISE</text>
<text x="${ML-3}" y="872" font-family="Roboto Serif" font-weight="300" font-size="54" fill="${INK}">Ambitious ideas,</text>
<text x="${ML-3}" y="932" font-family="Roboto Serif" font-weight="300" font-style="italic" font-size="54" fill="${INK}">made legible.</text>

<!-- footer -->
<line x1="${ML}" y1="970" x2="${MR}" y2="970" stroke="${HAIR}" stroke-width="0.8"/>
<text x="${ML}" y="992" font-family="Sora" font-weight="400" font-size="8" letter-spacing="2" fill="${GREY}">SIGNAL · SCREEN · SEQUENCE</text>
<text x="${(ML+MR)/2}" y="992" text-anchor="middle" font-family="Sora" font-weight="500" font-size="8" letter-spacing="2" fill="${INK}">id8investments.com</text>
<text x="${MR}" y="992" text-anchor="end" font-family="Sora" font-weight="400" font-size="8" letter-spacing="2" fill="${GREY}">MMXXVI</text>
</svg>`;

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
${face("Sora","Sora-Light.ttf",300)}
${face("Sora","Sora-Regular.ttf",400)}
${face("Sora","Sora-Medium.ttf",500)}
${face("Sora","Sora-SemiBold.ttf",600)}
${face("Roboto Serif","RobotoSerif-Light.ttf",300)}
${face("Roboto Serif","RobotoSerif-LightItalic.ttf",300,"italic")}
@page{size:8.5in 11in;margin:0}
html,body{margin:0;padding:0;background:${PAPER}}
svg{display:block;width:8.5in;height:11in}
</style></head><body>${svg}</body></html>`;

fs.writeFileSync(path.join(__dirname, "canvas.html"), html);
console.log("canvas.html written");
