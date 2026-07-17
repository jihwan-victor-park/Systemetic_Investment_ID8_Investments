import styles from './QualityFunnel.module.css';

// Animated quality funnel: the market streams in, AI filters it at each gate,
// and only a few hubs remain. Shows how sourcing quality is assured.
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

const W = 1000;
const GATES = [300, 560, 820];
const STAGES = [
  { x: 165, name: 'AI Coverage', sub: 'the whole market' },
  { x: 430, name: 'AI Scoring', sub: 'one rubric, every deal' },
  { x: 690, name: 'AI Diligence', sub: 'evidence, not gut' },
  { x: 915, name: 'Conviction', sub: 'the few we back' },
];

// Every Y position below is a ratio of H, calibrated against the original
// H=340 desktop design (CY=158, gate span 26-290, labels at 314/332) -- so
// the exact same composition can be redrawn at a taller H for mobile, with
// more room between the flow lines and labels, instead of the whole thing
// getting squeezed thin at a narrow width.
const CY_R = 158 / 340, GATE_Y1_R = 26 / 340, GATE_Y2_R = 290 / 340;
const SY_MIN_R = 26 / 340, SY_RANGE_R = 286 / 340;
const HUB_OFFSET_R = 42 / 340, LABEL_Y_R = 314 / 340, SUB_Y_R = 332 / 340;

function genDots(seed, H) {
  const rng = mulberry32(seed >>> 0);
  const cy = H * CY_R;
  const syMin = H * SY_MIN_R, syRange = H * SY_RANGE_R;
  const hubOffset = H * HUB_OFFSET_R;
  const dots = [];
  for (let i = 0; i < 40; i++) {
    const sy = syMin + rng() * syRange;
    const t = rng();
    // most filtered early; a rare few (tier 4) travel all the way and arrive
    const tier = t < 0.5 ? 1 : t < 0.78 ? 2 : t < 0.92 ? 3 : 4;
    if (tier === 4) {
      const ey = [cy - hubOffset, cy, cy + hubOffset][Math.floor(rng() * 3)];
      const dur = ((915 - 20) / 105 + 0.8);
      dots.push({ sy, ex: 915, ey, r: 3.6, arrive: true, dur: dur.toFixed(2), delay: (rng() * dur).toFixed(2), mid: 0.95 });
      continue;
    }
    const ex = tier === 1 ? GATES[0] : tier === 2 ? GATES[1] : 815;
    const shrink = tier === 1 ? 0.8 : tier === 2 ? 0.52 : 0.3;
    const ey = cy + (sy - cy) * shrink;
    const dur = ((ex - 20) / 130 + 0.5);
    dots.push({ sy, ex, ey, r: 2.7, arrive: false, dur: dur.toFixed(2), delay: (rng() * dur).toFixed(2), mid: (0.45 + rng() * 0.3).toFixed(2) });
  }
  return dots;
}

function Funnel({ H, seed, wrapClassName }) {
  const cy = H * CY_R;
  const dots = genDots(seed, H);
  const hubOffset = H * HUB_OFFSET_R;
  const hubs = [cy - hubOffset, cy, cy + hubOffset].map((y) => ({ x: 915, y }));
  const gateY1 = H * GATE_Y1_R, gateY2 = H * GATE_Y2_R;
  const labelY = H * LABEL_Y_R, subY = H * SUB_Y_R;

  return (
    <div className={`${styles.wrap} ${wrapClassName}`}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
        {GATES.map((x, i) => <line key={i} className={styles.gate} x1={x} y1={gateY1} x2={x} y2={gateY2} />)}

        {dots.map((d, i) => (
          <circle key={i} className={`${styles.dot}${d.arrive ? ' ' + styles.arrive : ''}`} cx={0} cy={0} r={d.r}
            style={{ '--sy': `${d.sy}px`, '--ex': `${d.ex}px`, '--ey': `${d.ey}px`, '--mid': d.mid,
              animationDuration: `${d.dur}s`, animationDelay: `${d.delay}s` }} />
        ))}

        {hubs.map((h, i) => (
          <g key={`h${i}`}>
            <circle className={styles.ring} cx={h.x} cy={h.y} r={15} style={{ animationDelay: `${i * 0.5}s` }} />
            <circle className={styles.ring} cx={h.x} cy={h.y} r={24} style={{ animationDelay: `${i * 0.5 + 0.3}s` }} />
            <circle className={styles.hub} cx={h.x} cy={h.y} r={5} />
          </g>
        ))}

        {STAGES.map((s, i) => (
          <g key={`s${i}`}>
            <text className={styles.label} x={s.x} y={labelY} textAnchor="middle">{s.name}</text>
            <text className={styles.sub} x={s.x} y={subY} textAnchor="middle">{s.sub}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

// Static Server Component (deterministic seed, CSS-only animation) -- renders
// both a desktop and a taller mobile layout and lets a media query pick
// which one is visible, rather than reaching for client-side JS just to
// detect viewport width.
export default function QualityFunnel() {
  return (
    <>
      <Funnel H={340} seed={0x1d8f} wrapClassName={styles.desktopOnly} />
      <Funnel H={580} seed={0x1d8f} wrapClassName={styles.mobileOnly} />
    </>
  );
}
