// Latent Order signal field: faint lattice + an emergent, harmonic constellation.
// Static. The most-connected nodes (the hubs) are highlighted in black.
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hashStr(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

const FX = 16, FY = 16, STEP = 38, COLS = 27, ROWS = 7;
const W = FX * 2 + COLS * STEP, H = FY * 2 + ROWS * STEP;
const gx = c => FX + c * STEP, gy = r => FY + r * STEP;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function generate(seed) {
  const rng = mulberry32(hashStr(seed));
  const count = 8 + Math.floor(rng() * 3);
  const keys = 'abcdefghij'.split('').slice(0, count);
  const band = (COLS - 2) / count;
  let row = 1.5 + rng() * (ROWS - 3);
  const pos = {};
  keys.forEach((k, i) => {
    const col = clamp(1 + i * band + (rng() - 0.5) * band * 0.7, 1, COLS - 1);
    row = clamp(row + (rng() - 0.5) * 3.0, 1, ROWS - 1);   // smooth walk = harmonic
    pos[k] = [gx(col), gy(row)];
  });
  const order = [...keys].sort((a, b) => pos[a][0] - pos[b][0]);
  const edges = [];
  for (let i = 0; i < order.length - 1; i++) edges.push([order[i], order[i + 1]]);
  const branches = 1 + Math.floor(rng() * 2);
  for (let b = 0; b < branches; b++) { const i = Math.floor(rng() * (order.length - 2)); edges.push([order[i], order[i + 2]]); }
  // highlight the most-connected nodes
  const deg = {}; keys.forEach(k => (deg[k] = 0));
  edges.forEach(([a, b]) => { deg[a]++; deg[b]++; });
  const sig = [...keys].sort((a, b) => deg[b] - deg[a]).slice(0, 2);
  return { pos, edges, sig };
}

export default function SignalField({ seed = 'id8' }) {
  const { pos, edges, sig } = generate(seed);
  const ticks = [];
  for (let c = 0; c <= COLS; c++) for (let r = 0; r <= ROWS; r++) {
    const x = gx(c), y = gy(r);
    ticks.push(<path key={`${c}-${r}`} d={`M${x - 2.4} ${y}H${x + 2.4}M${x} ${y - 2.4}V${y + 2.4}`} stroke="var(--id8-hair)" strokeWidth="1" />);
  }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <g>{ticks}</g>
      {sig.map(k => (
        <g key={`s${k}`}>
          <circle cx={pos[k][0]} cy={pos[k][1]} r="18" fill="none" stroke="var(--id8-ink)" strokeWidth="0.7" opacity="0.26" />
          <circle cx={pos[k][0]} cy={pos[k][1]} r="30" fill="none" stroke="var(--id8-ink)" strokeWidth="0.6" opacity="0.13" />
        </g>
      ))}
      {edges.map(([a, b], i) => (
        <line key={`e${i}`} x1={pos[a][0]} y1={pos[a][1]} x2={pos[b][0]} y2={pos[b][1]} stroke="var(--id8-ink)" strokeWidth="1" opacity="0.8" />
      ))}
      {Object.keys(pos).map(k => {
        const s = sig.includes(k);
        return <circle key={`n${k}`} cx={pos[k][0]} cy={pos[k][1]} r={s ? 5.5 : 4} fill={s ? 'var(--id8-ink)' : 'var(--id8-paper)'} stroke="var(--id8-ink)" strokeWidth={s ? 0 : 1.3} />;
      })}
    </svg>
  );
}
