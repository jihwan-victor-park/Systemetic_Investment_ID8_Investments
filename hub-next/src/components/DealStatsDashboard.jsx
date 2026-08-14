import Link from 'next/link';
import { computeDealStats } from '@/lib/dealStats';
import { STAGE_BASEPATH } from '@/lib/stages';
import styles from './DealStatsDashboard.module.css';

// The live version of the LP deck's "Demonstrated Success In Deal Sourcing"
// slide (Oscar, 2026-08-13, pointing at it: "the stat should be something more
// like this, this is what we are trying to demonstrate").
//
// The story is two numbers, in Oscar's own framing: "qualified have our
// mandate, pipeline are the ones we get access to." Qualified says how much of
// the market ID8 should be able to play in; pipeline says how much of it ID8
// actually reaches. Every chart here cuts one of those two -- by stage, or by
// round. See lib/dealStats.js's mandateStats for the denominator, which is the
// one part of this that needed real care.
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
// strong/pale sit adjacent by construction in the meters (arc against track), so
// they're spaced far apart (normal-vision ΔE well past the 15 floor) rather than
// one ramp step apart. `pale` is below 3:1 against white, so every mark using it
// also carries a visible value label -- identity never rests on the fill alone.
const RAMP = {
  strong: '#112ED4',   // --id8-accent
  pale: '#CFD7F9',
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

// `rows`: [{key, label, count}]. `share` puts a second, smaller line under each
// label -- "% of the book" on the stage chart, omitted where the count is the
// whole story. `tooltip(row)` overrides the hover text, since what a bar means
// differs per chart and a generic "N deals" sentence would be wrong on one of
// them.
//
// `backgroundKey` turns each column into an OVERLAY: a pale bar for
// `row[backgroundKey]` with the solid `count` bar drawn in front of it, from the
// same baseline. Safe as a part-to-whole read because the only caller uses
// mandate as the background and pipeline as the count, and pipeline is a subset
// of mandate by construction (lib/dealStats.js) -- so the dark bar can never
// overflow the pale one. Grouping the two side by side instead would ask the eye
// to compare two heights; nesting them shows the fraction directly.
function ColumnChart({ rows, total, ariaLabel, share = true, tooltip, backgroundKey }) {
  const plotW = CHART_W - PAD.left - PAD.right;
  const plotH = CHART_H - PAD.top - PAD.bottom;
  // Axis scales on the background when there is one -- scaling on `count` would
  // let the pale bars run off the top of the plot.
  const peak = Math.max(...rows.map((r) => (backgroundKey ? r[backgroundKey] : r.count)), 1);
  const max = niceMax(peak);
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
         aria-label={`${ariaLabel}. ${rows.map((r) => `${r.label}: ${r.count}`).join('. ')}.`}>
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
        const bgValue = backgroundKey ? r[backgroundKey] : null;
        const bgH = bgValue == null ? 0 : (bgValue / max) * plotH;
        const bgY = PAD.top + plotH - bgH;
        const pctOfTotal = total ? Math.round((r.count / total) * 100) : 0;
        return (
          <g key={r.key} className={styles.barGroup}>
            <title>{tooltip ? tooltip(r) : `${r.label}: ${num(r.count)} deals · ${pctOfTotal}% of ${num(total)} tracked`}</title>
            {/* Full-height hit target: a 3-deal bar is ~8px tall, far too small
                to hover reliably. Invisible, and it carries the <title>. */}
            <rect className={styles.barHit} x={PAD.left + i * band} y={PAD.top} width={band} height={plotH} />
            {bgH > 0 && <path className={styles.barBg} d={barPath(x, bgY, barW, bgH)} fill={RAMP.pale} />}
            <path className={styles.bar} d={barPath(x, y, barW, h)} fill={RAMP.strong} />
            {/* Only the solid bar's value is labelled. Labelling both would put
                two numbers on every column -- 22 of them here -- and direct
                labels stop working the moment they flood. The background's value
                is on the hover tooltip and in the legend's own reading. */}
            <text className={styles.barValue} x={x + barW / 2}
                  y={(bgH > h + 14 ? y : Math.min(y, bgY)) - 7} textAnchor="middle">
              {num(r.count)}
            </text>
            {/* The background's value above its own cap, muted, only when the
                solid bar's label can't collide with it. */}
            {bgH > h + 14 && (
              <text className={styles.barBgValue} x={x + barW / 2} y={bgY - 7} textAnchor="middle">
                {num(bgValue)}
              </text>
            )}
            <text className={styles.barLabel} x={PAD.left + i * band + band / 2} y={CHART_H - 26} textAnchor="middle">
              {r.label}
            </text>
            {share && (
              <text className={styles.barLabelSub} x={PAD.left + i * band + band / 2} y={CHART_H - 11} textAnchor="middle">
                {pctOfTotal}%
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// A chart plus a legend down its right-hand side. `keys` is [{label, note,
// color, count}], drawn top to bottom. Wraps the legend under the chart on a
// narrow viewport rather than squeezing the plot -- the bars are the point.
function ChartWithLegend({ keys, children }) {
  return (
    <div className={styles.chartRow}>
      <div className={styles.chartCol}>{children}</div>
      <ul className={styles.chartLegend}>
        {keys.map((k) => (
          <li key={k.label} className={styles.chartLegendItem}>
            <span className={styles.chartLegendDot} style={{ background: k.color }} aria-hidden="true" />
            <span className={styles.chartLegendText}>
              <span className={styles.chartLegendLabel}>
                {k.label}
                {k.count != null && <span className={styles.chartLegendCount}>{num(k.count)}</span>}
              </span>
              <span className={styles.chartLegendNote}>{k.note}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const DONUT = { size: 168, r: 62, stroke: 20 };

// A METER, not a part-to-whole ring: one arc showing a share against a
// full-circle track. A meter claims "this fraction of that", which is exactly
// what a ratio is; a two-segment pie of qualified-vs-pipeline would instead
// claim the two partition something, and they don't -- see mandateStats. The
// track is the whole, the arc is the part.
function Meter({ pct: value, label, whole, part, title }) {
  const circumference = 2 * Math.PI * DONUT.r;
  const dash = (value == null ? 0 : Math.min(1, value / 100)) * circumference;

  return (
    <div className={styles.donutRow}>
      <svg className={styles.donut} viewBox={`0 0 ${DONUT.size} ${DONUT.size}`} role="img" aria-label={title}>
        <g transform={`translate(${DONUT.size / 2} ${DONUT.size / 2}) rotate(-90)`}>
          {/* Unfilled track is a lighter step of the same hue, so the meter
              reads as one object across its whole circumference. */}
          <circle r={DONUT.r} fill="none" stroke={RAMP.pale} strokeWidth={DONUT.stroke} />
          {dash > 0 && (
            <circle className={styles.donutSeg} r={DONUT.r} fill="none" stroke={RAMP.strong}
                    strokeWidth={DONUT.stroke} strokeLinecap="butt"
                    strokeDasharray={`${dash} ${circumference - dash}`}>
              <title>{title}</title>
            </circle>
          )}
        </g>
        <text className={styles.donutCenterValue} x={DONUT.size / 2} y={DONUT.size / 2 - 2} textAnchor="middle">
          {pct(value)}
        </text>
        <text className={styles.donutCenterLabel} x={DONUT.size / 2} y={DONUT.size / 2 + 16} textAnchor="middle">
          {label}
        </text>
      </svg>
      <ul className={styles.legend}>
        {[whole, part].map((row, i) => (
          <li key={row.label} className={styles.legendItem}>
            <span className={styles.legendDot} style={{ background: i === 0 ? RAMP.pale : RAMP.strong }}
                  aria-hidden="true" />
            <span className={styles.legendLabel}>
              {row.label}
              <span className={styles.legendNote}>{row.note}</span>
            </span>
            <span className={styles.legendValue}>{num(row.count)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function DealStatsDashboard({ companies }) {
  const { total, byStage, bySeries, mandate } = computeDealStats(companies);

  // One bar per round, height = pipeline deals at that round. Rounds with no
  // mandate at all are dropped: a bar of height 0 for a round ID8 has never
  // qualified anything at is noise, not information. Rounds that DO have mandate
  // but no pipeline stay, at zero -- that's a real and interesting gap.
  const seriesPipelineRows = bySeries
    .filter((r) => r.mandate > 0)
    .map((r) => ({ key: r.label, label: r.label, count: r.pipeline, mandate: r.mandate }));

  // No explanatory paragraph under any card title (Oscar, 2026-08-13) -- the
  // titles, the axis labels and the hover tooltips carry it. Anything that
  // genuinely needs stating rides in a tooltip instead of prose above a chart.
  return (
    <section className={styles.wrap}>
      <div className={styles.head}>
        <h1 className={styles.title}>Dashboard</h1>
      </div>

      {/* No "Access rate" tile (Oscar, 2026-08-13: "delete the access rate
          card") -- the ring below carries that same ratio, and the tile row is
          now purely counts, which is what makes it scannable.
          No "Invested" tile either (Oscar, 2026-08-14: "eliminate the
          invested card on the dashboard") -- 4 tiles now. */}
      <div className={styles.tiles}>
        <StatTile hero label="Qualified" value={num(mandate.qualifiedCount)} href={STAGE_BASEPATH.qualified} />
        <StatTile label="In pipeline" value={num(mandate.pipelineCount)} href={STAGE_BASEPATH.pipeline} />
        <StatTile label="Qualified + pipeline" value={num(mandate.converted.both)}
                  sub={`${pct(mandate.converted.pct)} of qualified`} />
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
        <ColumnChart rows={byStage} total={total} ariaLabel="Deals by stage" />
      </div>

      {/* Bars, not the nested-bar list this used to be (Oscar: "make it into a
          bar chart, not like that one"), and titled for pipeline rather than
          access ("change the name to pipeline, not mentioning access"). Each bar
          is the number of PIPELINE deals at that round -- where ID8 actually
          gets in, by stage of company. The mandate figure per round is still on
          the hover tooltip, which is where the ratio belongs now that the
          headline is a count. */}
      <div className={styles.card}>
        <div className={styles.cardHead}>
          <h2 className={styles.cardTitle}>Pipeline by series</h2>
        </div>
        <ChartWithLegend
          keys={[
            { label: 'Qualified', note: 'meets our mandate at this round', color: RAMP.pale, count: mandate.mandateTotal },
            { label: 'In pipeline', note: 'the ones we got into', color: RAMP.strong, count: mandate.pipelineCount },
          ]}
        >
          <ColumnChart
            rows={seriesPipelineRows}
            total={mandate.pipelineCount}
            share={false}
            backgroundKey="mandate"
            ariaLabel="Pipeline deals by series, against the mandate at each round"
            tooltip={(r) => `${r.label}: ${num(r.count)} in pipeline of ${num(r.mandate)} qualified`
              + ` (${Math.round((r.count / r.mandate) * 100)}%)`}
          />
        </ChartWithLegend>
      </div>

      <div className={styles.twoUp}>
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <h2 className={styles.cardTitle}>Pipeline rate</h2>
          </div>
          <Meter
            pct={mandate.pct}
            label="in pipeline"
            title={`${num(mandate.pipelineCount)} of ${num(mandate.mandateTotal)} deals reached pipeline`}
            whole={{ label: 'Overall deals', note: 'incl. those now in pipeline', count: mandate.mandateTotal }}
            part={{ label: 'Pipeline', note: 'the ones we got into', count: mandate.pipelineCount }}
          />
        </div>

        {/* The strict read Oscar called "the real number" (2026-08-13): not
            deals we merely got into, but deals we got into that we had also
            judged to fit the mandate. Only answerable because the import now
            carries Attio's stage HISTORY as tags -- see
            import_attio_deals_csv.stage_history_tags. */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <h2 className={styles.cardTitle}>Qualified deals we got into</h2>
          </div>
          <Meter
            pct={mandate.converted.pct}
            label="converted"
            title={`${num(mandate.converted.both)} of ${num(mandate.qualifiedCount)} qualified deals are also in pipeline`}
            whole={{ label: 'Qualified', note: 'meets our mandate', count: mandate.qualifiedCount }}
            part={{ label: 'Also in pipeline', note: 'qualified and we got in', count: mandate.converted.both }}
          />
        </div>
      </div>
    </section>
  );
}
