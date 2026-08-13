import Link from 'next/link';
import { computeDealStats, SERIES_UNKNOWN } from '@/lib/dealStats';
import { STAGE_BASEPATH } from '@/lib/stages';
import styles from './DealStatsDashboard.module.css';

// The live version of the LP deck's "Demonstrated Success In Deal Sourcing"
// slide (Oscar, 2026-08-13, pointing at it: "the stat should be something more
// like this, this is what we are trying to demonstrate").
//
// The story is two numbers, in Oscar's own framing: "qualified have our
// mandate, pipeline are the ones we get access to." The mandate says how much
// of the market ID8 should be able to play in; the access rate says how much of
// it ID8 actually reaches. Every chart here cuts one of those two -- by stage,
// or by round. See lib/dealStats.js's mandateStats for the denominator, which
// is the one part of this that needed real care.
//
// Nothing here holds a literal figure: every number comes from computeDealStats
// over the live `companies` collection, on a force-dynamic page. Add a deal in
// Attio and it moves on the next load -- unlike the deck slide, which is a
// hand-built snapshot.
//
// No explanatory paragraph under any title (Oscar, same day: "delete this stupid
// subtitles"). Titles, column headers, axis labels and hover tooltips carry it.
//
// A Server Component -- no client JS, no chart library (none is installed, and
// the repo's existing charts are hand-rolled inline SVG; see QualityFunnel.jsx).
// The hover layer is native SVG <title> plus CSS :hover, which gives a real
// tooltip and a highlight without shipping a byte of JS.
//
// COLOR. Two steps off ID8's accent blue, plus one neutral gray -- deliberately
// not a categorical palette. Nothing on this page encodes unrelated categories:
// every chart is one measure (deals) with at most a part-to-whole split inside
// it, so a rainbow would invent distinctions that aren't in the data. `strong`
// always means "sourced"/"the count"; `pale` is only ever the whole it sits
// inside; gray is reserved for absence -- "not recorded", "tracked only",
// "other rounds" -- because absence isn't a point on the magnitude scale (the
// same missing-is-not-zero rule lib/dealStats.js applies to the counts).
//
// strong/pale sit adjacent by construction in the nested series bars, so they're
// spaced far apart (normal-vision ΔE well past the 15 floor) rather than one
// ramp step apart. `pale` is below 3:1 against white, so every mark using it
// also carries a visible value label -- identity never rests on the fill alone.
const RAMP = {
  strong: '#112ED4',   // --id8-accent
  pale: '#CFD7F9',
  none: '#B5AFA3',     // warm gray, --id8-hair family
};

const pct = (n) => (n == null ? '—' : `${Math.round(n)}%`);

// A count is a count -- no K/M compaction. The largest number this page will
// ever show is in the hundreds, and "318" beats "0.3K" every time.
const num = (n) => n.toLocaleString('en-US');

function StatTile({ label, value, sub, href, hero = false }) {
  const body = (
    <>
      <span className={styles.tileLabel}>{label}</span>
      <span className={hero ? styles.tileValueHero : styles.tileValue}>{value}</span>
      <span className={styles.tileSub}>{sub}</span>
    </>
  );
  // The tiles that correspond to a real tab link there -- a partner reading
  // "34 in pipeline" almost always wants the 34.
  return href
    ? <Link href={href} className={`${styles.tile} ${styles.tileLink}`}>{body}</Link>
    : <div className={styles.tile}>{body}</div>;
}

// Rounded top, square baseline (the bar never floats off its axis), per the
// house mark spec. Falls back to a plain rect below 2r tall so a 1-deal bar
// doesn't render as a lopsided blob.
function barPath(x, y, w, h, r = 4) {
  if (h <= 0) return '';
  const rr = Math.min(r, w / 2, h);
  return `M${x} ${y + h} L${x} ${y + rr} Q${x} ${y} ${x + rr} ${y} L${x + w - rr} ${y} Q${x + w} ${y} ${x + w} ${y + rr} L${x + w} ${y + h} Z`;
}

// Round the axis up to a clean number so the gridline labels read 0/20/40, not
// 0/17/34. Steps through 1/2/5 x 10^n, the standard nice-number ladder.
function niceMax(value) {
  if (value <= 0) return 1;
  const mag = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (value <= mag * step) return mag * step;
  }
  return mag * 10;
}

// viewBox proportions are chosen to match the card this sits in at desktop
// width (~1020px of inner width), so one viewBox unit is roughly one CSS pixel
// and the bar width below means what it says. A viewBox much narrower than its
// container silently scales every "24px" mark up by the difference.
const CHART_W = 1000;
const CHART_H = 260;
const PAD = { top: 24, right: 8, bottom: 48, left: 38 };

function StageColumns({ rows, total }) {
  const plotW = CHART_W - PAD.left - PAD.right;
  const plotH = CHART_H - PAD.top - PAD.bottom;
  const max = niceMax(Math.max(...rows.map((r) => r.count), 1));
  const band = plotW / rows.length;
  // Capped at 34px rather than the house 24px: with only six stages across a
  // full-width card the bands are ~160px, and a 24px bar in a 160px band reads
  // as a sparse hairline rather than a column. Still barely a third of the band,
  // so the "let the leftover be air" intent holds -- the cap exists to stop bars
  // filling their slot, and 21% fill is nowhere near that.
  const barW = Math.min(34, band * 0.34);
  const ticks = [0, max / 2, max];

  return (
    <svg className={styles.chart} viewBox={`0 0 ${CHART_W} ${CHART_H}`} role="img"
         aria-label={`Deals by stage. ${rows.map((r) => `${r.label}: ${r.count}`).join('. ')}.`}>
      {ticks.map((t) => {
        const y = PAD.top + plotH - (t / max) * plotH;
        return (
          <g key={t}>
            <line className={styles.grid} x1={PAD.left} x2={CHART_W - PAD.right} y1={y} y2={y} />
            <text className={styles.axisText} x={PAD.left - 8} y={y + 3.5} textAnchor="end">{num(t)}</text>
          </g>
        );
      })}
      {rows.map((r, i) => {
        const h = (r.count / max) * plotH;
        const x = PAD.left + i * band + (band - barW) / 2;
        const y = PAD.top + plotH - h;
        const share = total ? Math.round((r.count / total) * 100) : 0;
        return (
          <g key={r.stage} className={styles.barGroup}>
            <title>{`${r.label}: ${num(r.count)} deals · ${share}% of ${num(total)} tracked`}</title>
            {/* Full-height hit target: a 3-deal bar is ~8px tall, far too small
                to hover reliably. Invisible, and it carries the <title>. */}
            <rect className={styles.barHit} x={PAD.left + i * band} y={PAD.top} width={band} height={plotH} />
            <path className={styles.bar} d={barPath(x, y, barW, h)} fill={RAMP.strong} />
            {/* Value on the cap. One series, so there's no legend to defer to
                and no risk of a flood of labels -- six numbers total. */}
            <text className={styles.barValue} x={x + barW / 2} y={y - 7} textAnchor="middle">{num(r.count)}</text>
            <text className={styles.barLabel} x={PAD.left + i * band + band / 2} y={CHART_H - 26} textAnchor="middle">
              {r.label}
            </text>
            <text className={styles.barLabelSub} x={PAD.left + i * band + band / 2} y={CHART_H - 11} textAnchor="middle">
              {share}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const DONUT = { size: 168, r: 62, stroke: 20 };

// A METER, not a part-to-whole ring: one arc showing the pipeline share of the
// mandate against a full-circle track. A meter claims "this fraction of that",
// which is exactly the ratio; a two-segment pie of qualified-vs-pipeline would
// instead claim the two partition something, and they don't -- see
// mandateStats. The track is the mandate; the arc is the part we reach.
function AccessMeter({ mandate }) {
  const circumference = 2 * Math.PI * DONUT.r;
  const frac = mandate.pct == null ? 0 : Math.min(1, mandate.pct / 100);
  const dash = frac * circumference;

  return (
    <div className={styles.donutRow}>
      <svg className={styles.donut} viewBox={`0 0 ${DONUT.size} ${DONUT.size}`} role="img"
           aria-label={`Access rate: ${num(mandate.pipelineCount)} deals in pipeline out of ${num(mandate.mandateTotal)} in our mandate.`}>
        <g transform={`translate(${DONUT.size / 2} ${DONUT.size / 2}) rotate(-90)`}>
          {/* Unfilled track is a lighter step of the same hue, so the meter
              reads as one object across its whole circumference. */}
          <circle r={DONUT.r} fill="none" stroke={RAMP.pale} strokeWidth={DONUT.stroke} />
          {dash > 0 && (
            <circle className={styles.donutSeg} r={DONUT.r} fill="none" stroke={RAMP.strong}
                    strokeWidth={DONUT.stroke} strokeLinecap="butt"
                    strokeDasharray={`${dash} ${circumference - dash}`}>
              <title>{`${num(mandate.pipelineCount)} of ${num(mandate.mandateTotal)} mandate deals reached pipeline`}</title>
            </circle>
          )}
        </g>
        <text className={styles.donutCenterValue} x={DONUT.size / 2} y={DONUT.size / 2 - 2} textAnchor="middle">
          {pct(mandate.pct)}
        </text>
        <text className={styles.donutCenterLabel} x={DONUT.size / 2} y={DONUT.size / 2 + 16} textAnchor="middle">
          access
        </text>
      </svg>
      <ul className={styles.legend}>
        <li className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: RAMP.pale }} aria-hidden="true" />
          <span className={styles.legendLabel}>
            Our mandate
            <span className={styles.legendNote}>qualified, incl. those now in pipeline</span>
          </span>
          <span className={styles.legendValue}>{num(mandate.mandateTotal)}</span>
        </li>
        <li className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: RAMP.strong }} aria-hidden="true" />
          <span className={styles.legendLabel}>
            Pipeline
            <span className={styles.legendNote}>the ones we get access to</span>
          </span>
          <span className={styles.legendValue}>{num(mandate.pipelineCount)}</span>
        </li>
      </ul>
    </div>
  );
}

// Ranked bar rows rather than a second ring: there are more series buckets than
// a ring can carry legibly (past ~6 segments adjacent arcs blur), and series is
// ORDERED -- kept in round progression, not sorted by count.
//
// Each row is a nested bar: the pale bar is that round's mandate (qualified +
// pipeline, scaled against the biggest round), and the solid portion inside it
// is the share we got into. So the bar's LENGTH says how much mandate the round
// carries and its FILL says how much of it we reach -- the two questions the LP
// slide is about, in one row.
function SeriesBars({ rows, total }) {
  const max = Math.max(...rows.map((r) => r.mandate), 1);
  return (
    <ul className={styles.seriesList}>
      {rows.map((r) => {
        // "Other rounds" names its members on hover, so a mis-imported Series
        // (an investor name in the Series field, a PitchBook "Later Stage VC"
        // placeholder) is discoverable rather than swallowed by the fold.
        const detail = `${r.label}: ${num(r.pipeline)} in pipeline of ${num(r.mandate)} in our mandate`
          + ` (${num(r.qualified)} still at Qualified) · ${num(r.count)} tracked,`
          + ` ${Math.round(r.pct)}% of the ${num(total)} book`;
        const isNeutral = r.label === SERIES_UNKNOWN || !!r.members;
        return (
          <li key={r.label} className={styles.seriesRow}
              title={r.members ? `${detail}\n${r.members.join(', ')}` : detail}>
            <span className={styles.seriesLabel}>{r.label}</span>
            <span className={styles.seriesTrack}>
              {/* Outer: this round's mandate, relative to the biggest round. */}
              <span className={styles.seriesFill}
                    style={{ width: `${(r.mandate / max) * 100}%`, background: RAMP.pale }}>
                {/* Inner: the pipeline share of THIS round's mandate, so its
                    width reads as an access rate within the bar it sits in. */}
                <span className={styles.seriesSourced}
                      style={{
                        width: `${r.accessPct ?? 0}%`,
                        background: isNeutral ? RAMP.none : RAMP.strong,
                      }} />
              </span>
            </span>
            <span className={styles.seriesValue}>{num(r.mandate)}</span>
            <span className={styles.seriesPct}>{r.accessPct == null ? '—' : `${Math.round(r.accessPct)}%`}</span>
          </li>
        );
      })}
    </ul>
  );
}

export default function DealStatsDashboard({ companies }) {
  const { total, byStage, bySeries, mandate } = computeDealStats(companies);

  // No explanatory paragraph under any card title (Oscar, 2026-08-13) -- the
  // titles, the axis labels and the hover tooltips carry it. Anything that
  // genuinely needs stating rides in a column header or a tooltip instead of a
  // paragraph of prose above the chart.
  return (
    <section className={styles.wrap}>
      <div className={styles.head}>
        <h1 className={styles.title}>Dashboard</h1>
      </div>

      {/* Qualified (the mandate) -> Pipeline (what we get into) -> the rate
          between them, reading left to right in that order. */}
      <div className={styles.tiles}>
        <StatTile hero label="Qualified" value={num(mandate.qualifiedCount)} href={STAGE_BASEPATH.qualified} />
        <StatTile label="In pipeline" value={num(mandate.pipelineCount)} href={STAGE_BASEPATH.pipeline} />
        <StatTile label="Access rate" value={pct(mandate.pct)}
                  sub={`${num(mandate.pipelineCount)} of ${num(mandate.mandateTotal)} in our mandate`} />
        <StatTile label="Invested" value={num(mandate.investedCount)} href={STAGE_BASEPATH.invested} />
        <StatTile label="Deals tracked" value={num(total)} />
      </div>

      <div className={styles.card}>
        <div className={styles.cardHead}>
          <h2 className={styles.cardTitle}>Deals by stage</h2>
          {/* Untriaged deals belong to no public stage, so they appear in no bar.
              A count in the header (not a paragraph) keeps the chart honest
              without explaining itself at length. */}
          {mandate.needsTriageCount > 0 && (
            <span className={styles.cardMeta}>{num(mandate.needsTriageCount)} untriaged, not shown</span>
          )}
        </div>
        <StageColumns rows={byStage} total={total} />
      </div>

      <div className={styles.twoUp}>
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <h2 className={styles.cardTitle}>Access to our mandate</h2>
          </div>
          <AccessMeter mandate={mandate} />
        </div>

        <div className={styles.card}>
          <div className={styles.cardHead}>
            <h2 className={styles.cardTitle}>Access by series</h2>
          </div>
          {/* Column headers do the work the removed paragraph used to: they name
              what each number is, in place, without a preamble. */}
          <div className={styles.seriesHead}>
            <span />
            <span />
            <span className={styles.seriesHeadCell}>Mandate</span>
            <span className={styles.seriesHeadCell}>Access</span>
          </div>
          <SeriesBars rows={bySeries} total={total} />
        </div>
      </div>
    </section>
  );
}
