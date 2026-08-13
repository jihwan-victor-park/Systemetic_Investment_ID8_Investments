import Link from 'next/link';
import { computeDealStats, SERIES_OTHER, SERIES_UNKNOWN } from '@/lib/dealStats';
import { STAGE_BASEPATH, STAGE_LABELS } from '@/lib/stages';
import styles from './DealStatsDashboard.module.css';

// Live summary statistics for the whole deal universe (Oscar, 2026-08-13:
// "numbers of deals of each stage, total, number per series, and ratios such as
// number of pipeline deals which are as well qualified (ie how much percentage
// of access we have to our mandate), as well number of pipeline/qualified
// overall. Everything very stripe looking professionally and of course that it
// automatically updates (not hard coded numbers)").
//
// Nothing here holds a literal figure: every number comes from computeDealStats
// over the live `companies` collection, on a force-dynamic page. Add a deal in
// Attio and it moves on the next load.
//
// A Server Component -- no client JS, no chart library (none is installed, and
// the repo's existing charts are hand-rolled inline SVG; see QualityFunnel.jsx).
// The hover layer is native SVG <title> plus CSS :hover, which gives a real
// tooltip and a highlight without shipping a byte of JS.
//
// COLOR. One sequential ramp off ID8's accent blue, plus one neutral gray.
// That's deliberate rather than a fallback for having no categorical palette:
// every breakdown on this page is ORDINAL (Seed -> Series H; both-buckets ->
// one-bucket -> neither), and a sequential single-hue ramp is the correct
// encoding for ordered magnitude -- a rainbow would imply these categories are
// unrelated. Gray is reserved for "not recorded" / "not active": absence is not
// a point on the magnitude scale (the same missing-is-not-zero rule
// lib/dealStats.js applies to the counts themselves). Steps are monotonic in
// lightness, and every adjacent pair clears normal-vision ΔE 17+ / CVD ΔE 16+.
// The palest step is below 3:1 against white, so every mark that uses it also
// carries a visible value label and a legend entry -- identity never rests on
// the fill alone.
const RAMP = {
  strong: '#112ED4',   // --id8-accent
  mid: '#4F6BEA',
  soft: '#93A3F0',
  none: '#B5AFA3',     // warm gray, --id8-hair family: "not recorded"/"not active"
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

// Access within the mandate universe (Pipeline union Qualified) -- a true
// three-way partition of that population, so a part-to-whole ring is honest
// here (unlike the stage counts above, which deliberately overlap and would sum
// past 100%). Three segments, well inside the six-segment ceiling a ring can be
// read at a glance.
//
// "Not recorded" is its own gray segment rather than folded into "No access":
// nobody has assessed those deals, which is a different fact from having tried
// and been shut out, and it's the majority of the population -- hiding it would
// make the ring imply a precision the data doesn't have.
function CoverageDonut({ mandateAccess }) {
  const segments = [
    { key: 'access', label: 'Access', count: mandateAccess.access, fill: RAMP.strong,
      note: 'we have a route into this round' },
    { key: 'noAccess', label: 'No access', count: mandateAccess.noAccess, fill: RAMP.soft,
      note: 'assessed, no route in' },
    { key: 'unrecorded', label: 'Not assessed', count: mandateAccess.unrecorded, fill: RAMP.none,
      note: 'no Access value in Attio yet' },
  ];
  const total = mandateAccess.population;
  const circumference = 2 * Math.PI * DONUT.r;
  // 2px surface gap between touching segments, the house spacer. Dropped
  // entirely when a segment is too thin to survive it -- a gap wider than the
  // arc would erase the segment rather than separate it.
  const gap = segments.filter((s) => s.count > 0).length > 1 ? 2 : 0;
  let offset = 0;

  return (
    <div className={styles.donutRow}>
      <svg className={styles.donut} viewBox={`0 0 ${DONUT.size} ${DONUT.size}`} role="img"
           aria-label={`Pipeline coverage of ${num(total)} tracked deals. ${segments.map((s) => `${s.label}: ${s.count}`).join('. ')}.`}>
        <g transform={`translate(${DONUT.size / 2} ${DONUT.size / 2}) rotate(-90)`}>
          <circle className={styles.donutTrack} r={DONUT.r} fill="none" strokeWidth={DONUT.stroke} />
          {segments.map((s) => {
            const len = total ? (s.count / total) * circumference : 0;
            const dash = Math.max(0, len - gap);
            const el = s.count > 0 && (
              <circle key={s.key} className={styles.donutSeg} r={DONUT.r} fill="none" stroke={s.fill}
                      strokeWidth={DONUT.stroke} strokeDasharray={`${dash} ${circumference - dash}`}
                      strokeDashoffset={-offset}>
                <title>{`${s.label}: ${num(s.count)} of ${num(total)} (${Math.round((s.count / total) * 100)}%)`}</title>
              </circle>
            );
            offset += len;
            return el;
          })}
        </g>
        {/* The ring's own headline sits in the hole: the ratio the whole card is
            about, so the eye doesn't have to reconstruct it from arcs. It's the
            rate among ASSESSED deals, which is deliberately not the same as the
            blue arc's share of the ring -- the caption below says so. */}
        <text className={styles.donutCenterValue} x={DONUT.size / 2} y={DONUT.size / 2 - 2} textAnchor="middle">
          {pct(mandateAccess.pct)}
        </text>
        <text className={styles.donutCenterLabel} x={DONUT.size / 2} y={DONUT.size / 2 + 16} textAnchor="middle">
          of assessed
        </text>
      </svg>
      <ul className={styles.legend}>
        {segments.map((s) => (
          <li key={s.key} className={styles.legendItem}>
            <span className={styles.legendDot} style={{ background: s.fill }} aria-hidden="true" />
            <span className={styles.legendLabel}>
              {s.label}
              <span className={styles.legendNote}>{s.note}</span>
            </span>
            <span className={styles.legendValue}>
              {num(s.count)}
              <span className={styles.legendPct}>{total ? `${Math.round((s.count / total) * 100)}%` : '—'}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Ranked bar rows rather than a second ring: there are more series buckets than
// a ring can carry legibly (past ~6 segments adjacent arcs blur), and series is
// ORDERED -- kept in round progression, not sorted by count, because the
// question this answers is "where does our book sit in the round spectrum."
function SeriesBars({ rows, total }) {
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <ul className={styles.seriesList}>
      {rows.map((r) => {
        // "Other rounds" names its members on hover, so a mis-imported Series
        // (an investor name in the Series field, a PitchBook "Later Stage VC"
        // placeholder) is discoverable rather than swallowed by the fold.
        const detail = `${r.label}: ${num(r.count)} of ${num(total)} deals (${Math.round(r.pct)}%)`;
        return (
          <li key={r.label} className={styles.seriesRow}
              title={r.members ? `${detail}\n${r.members.join(', ')}` : detail}>
            <span className={styles.seriesLabel}>{r.label}</span>
            <span className={styles.seriesTrack}>
              <span
                className={styles.seriesFill}
                style={{
                  width: `${(r.count / max) * 100}%`,
                  // Gray for both non-magnitude rows: "not recorded" is absent
                  // data, "other rounds" is a mixed bag, and neither is a point
                  // on the round ladder the blue ramp encodes.
                  background: r.label === SERIES_UNKNOWN || r.members ? RAMP.none : RAMP.strong,
                }}
              />
            </span>
            <span className={styles.seriesValue}>{num(r.count)}</span>
            <span className={styles.seriesPct}>{Math.round(r.pct)}%</span>
          </li>
        );
      })}
    </ul>
  );
}

export default function DealStatsDashboard({ companies }) {
  const { total, byStage, bySeries, ratios } = computeDealStats(companies);
  const recordedSeries = bySeries.filter((r) => r.label !== SERIES_UNKNOWN).reduce((s, r) => s + r.count, 0);
  const otherRounds = bySeries.find((r) => r.label === SERIES_OTHER);

  return (
    <section className={styles.wrap}>
      {/* Title only -- no "Live / recomputed every load" badge (Oscar,
          2026-08-13). The numbers being current is the baseline expectation,
          not a feature to advertise on the page. */}
      <div className={styles.head}>
        <h1 className={styles.title}>Dashboard</h1>
      </div>

      <div className={styles.tiles}>
        <StatTile hero label="Deals tracked" value={num(total)}
                  sub={`${num(recordedSeries)} with a Series on file`} />
        <StatTile label="In pipeline" value={num(ratios.pipelineCount)} href={STAGE_BASEPATH.pipeline}
                  sub={`${pct(total ? (ratios.pipelineCount / total) * 100 : null)} of everything tracked`} />
        <StatTile label="Qualified" value={num(ratios.qualifiedCount)} href={STAGE_BASEPATH.qualified}
                  sub={`${pct(total ? (ratios.qualifiedCount / total) * 100 : null)} of everything tracked`} />
        <StatTile label="Mandate access" value={pct(ratios.mandateAccess.pct)}
                  sub={`${num(ratios.mandateAccess.access)} of ${num(ratios.mandateAccess.recorded)} assessed mandate deals`} />
        <StatTile label="Active share" value={pct(ratios.activeShare.pct)}
                  sub={`${num(ratios.activeShare.numerator)} in pipeline or qualified`} />
      </div>

      <div className={styles.card}>
        <div className={styles.cardHead}>
          <h2 className={styles.cardTitle}>Deals by stage</h2>
          {/* Stated, not buried: these bars intentionally sum past the total,
              because stage membership is additive (a deal can be in Pipeline
              and Qualified at once). Without this the reader does the addition,
              gets a bigger number than "Deals tracked", and stops trusting the
              page. */}
          <p className={styles.cardNote}>
            A deal can sit in more than one stage at once, so these add up to more than the {num(total)} tracked.
            Percentages are of the {num(total)}.
            {ratios.needsTriageCount > 0 && (
              <> {num(ratios.needsTriageCount)} more are untriaged and appear in no bar —
                they have no stage recorded in Attio.</>
            )}
          </p>
        </div>
        <StageColumns rows={byStage} total={total} />
      </div>

      <div className={styles.twoUp}>
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <h2 className={styles.cardTitle}>Access to the mandate</h2>
            <p className={styles.cardNote}>
              Attio&apos;s Access field across the {num(ratios.mandateCount)} deals in Pipeline or Qualified.
              The headline rate is of the {num(ratios.mandateAccess.recorded)} that have actually been
              assessed — an unassessed deal isn&apos;t a <strong>no</strong>.
            </p>
          </div>
          <CoverageDonut mandateAccess={ratios.mandateAccess} />
          {/* The blended rate hides a real split, so both halves are stated. */}
          <ul className={styles.splitList}>
            {ratios.accessByStage.map((s) => (
              <li key={s.stage} className={styles.splitRow}>
                <span className={styles.splitLabel}>{STAGE_LABELS[s.stage]}</span>
                <span className={styles.splitValue}>{pct(s.pct)}</span>
                <span className={styles.splitSub}>
                  {s.recorded ? `${num(s.access)} of ${num(s.recorded)} assessed` : 'none assessed yet'}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHead}>
            <h2 className={styles.cardTitle}>Deals by series</h2>
            <p className={styles.cardNote}>
              In round order, not by size. Bars are relative to the largest bucket; percentages are of
              the {num(total)} tracked.
              {otherRounds && <> Hover <strong>Other rounds</strong> to see the {otherRounds.count} deals
                on non-standard labels — SAFEs, secondaries, and a few bad Series imports.</>}
            </p>
          </div>
          <SeriesBars rows={bySeries} total={total} />
        </div>
      </div>
    </section>
  );
}
