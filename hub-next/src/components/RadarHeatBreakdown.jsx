import { H2 } from '@/components/Prose';
import styles from './ScreenView.module.css';

// Human-readable labels for radar_market_heat.py's WEIGHTS keys -- the
// Firestore doc only has the camelCase key + weight/raw/contribution per
// signal (see that module's _entry()), so the display name lives here,
// not duplicated from Python. Matches the original Heat Score Signal
// Framework spreadsheet's own row names.
const SIGNAL_LABELS = {
  raiseProbability: 'Raise Probability',
  industryGrowth: 'Industry Growth',
  momEmployeeGrowth: 'MoM Employee Growth',
  jobPostingVelocity: 'Job Posting Velocity',
  crunchbaseGrowthScore: 'Growth Momentum',
  stepUp: 'Step-Up',
  yoyRevenueGrowth: 'YoY Revenue/ARR Growth',
  newsVolume: 'News Volume',
  websiteVisitsGrowth: 'Website Visits Growth',
  googleTrendsSearchInterest: 'Google Trends Search Interest',
  redditActivity: 'Reddit Activity',
  crunchbaseHeatScore: 'Public Attention & Heat',
  crunchbaseSurgeScore: 'Momentum Surge',
  tier1InvestorCount: 'Tier 1 Investor Count',
};

// Short evidence line per signal. Two distinct sources feed this, never
// both at once: the wired Python signals stamp band/momRate/count/context/
// proxyNote (radar_market_heat.py's own _entry() extras); the 2026-08-06
// manual web-research pass instead stamps a plain `evidence` sentence + a
// `source` citation URL (see docs/RADAR_HEAT_SCORE_RULES.md) -- same
// per-dimension "why" ScreenView/FitScoreScreenView already show, just two
// different field shapes depending on which pass produced the number.
function signalEvidence(entry) {
  const bits = [];
  if (entry.band) bits.push(`band: ${entry.band}`);
  if (entry.context) bits.push(entry.context);
  if (entry.momRate != null) bits.push(`MoM rate: ${(entry.momRate * 100).toFixed(1)}%`);
  if (entry.count != null) bits.push(`count: ${entry.count}`);
  if (entry.proxyNote) bits.push(entry.proxyNote);
  if (entry.evidence) bits.push(entry.evidence);
  return bits.join(' — ');
}

// Full breakdown of Radar's two scores -- the Heat Score Signal Framework
// (radar.marketHeat, the primary/hegemonic one per Oscar's 2026-08-05 call)
// and the hazard model underneath it (radar.hazard, still driving auto-drop
// and scan cadence -- see radar_market_heat.py's own module docstring for
// why they're deliberately kept separate). Same "expandable per-row detail"
// template as FitScoreScreenView/ScreenView, so this reads as the same kind
// of document as the Stage 0/1 score breakdowns already do (Oscar,
// 2026-08-06: "I want to be able to see a full desglose the same [way] I'm
// able to look at the details of the score").
export default function RadarHeatBreakdown({ radar }) {
  const marketHeat = radar?.marketHeat;
  const hazard = radar?.hazard;
  if (!marketHeat && !hazard) return null;

  const signals = marketHeat?.signals
    ? Object.entries(marketHeat.signals).sort((a, b) => b[1].weight - a[1].weight)
    : [];

  return (
    <div>
      <H2>Radar — Heat Score Signal Framework</H2>
      {marketHeat && (
        <>
          <p>
            <strong>Score: {marketHeat.score ?? '—'} / 100</strong>
            {marketHeat.normalizedScore != null && ` (${marketHeat.normalizedScore}/100 normalized, ${marketHeat.pointsAvailable}/100 pts of the rubric scored)`}
          </p>
          {marketHeat.timingUrgencyMultiplier > 1 && (
            <p><em>Timing urgency: ×{marketHeat.timingUrgencyMultiplier} — {marketHeat.monthsUntilWindow != null ? `${marketHeat.monthsUntilWindow} months to the predicted window` : 'no window estimate'}</em></p>
          )}
          {marketHeat.roundAnnouncedFlag && (
            <p><em>⚠ A round was detected as already announced — score capped, since it's too late to chase.</em></p>
          )}

          {signals.length > 0 && (
            <div className={styles.dimensions}>
              {signals.map(([key, entry]) => (
                <details key={key} className={styles.dim}>
                  <summary>
                    <span className={styles.summaryLeft}>
                      <svg className={styles.chevron} width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                        <path d="M2 0.5 L8 5 L2 9.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
                      </svg>
                      <span className={styles.dimName}>{SIGNAL_LABELS[key] || key}</span>
                    </span>
                    <span className={styles.dimScore}>
                      {entry.computed ? <>{entry.raw} / 10<em> · {entry.contribution} pts</em></> : <em>not measured</em>}
                    </span>
                  </summary>
                  <div className={styles.dimEvidence}>
                    {entry.computed ? (signalEvidence(entry) || `Weight: ${entry.weight} pts`) : `Weight: ${entry.weight} pts — no source wired for this signal yet`}
                    {entry.source && (
                      <>
                        {' '}
                        <a href={entry.source} target="_blank" rel="noopener noreferrer">source</a>
                      </>
                    )}
                  </div>
                </details>
              ))}
            </div>
          )}
        </>
      )}

      {hazard && (
        <>
          <p style={{ marginTop: '1.2rem' }}>
            <strong>Hazard model: {hazard.heatPoints} / 100</strong>
            {hazard.confidence && ` — confidence ${hazard.confidence}`}
            {hazard.dataCoverage != null && `, ${Math.round(hazard.dataCoverage * 100)}% data coverage`}
          </p>
          <p>
            P90 raise probability: {Math.round((hazard.p90 || 0) * 100)}%
            {' · '}P180: {Math.round((hazard.p180 || 0) * 100)}%
            {hazard.familiesActive?.length > 0 && ` · families active: ${hazard.familiesActive.join(', ')}`}
          </p>
          {hazard.distressFlag && (
            <p><em>⚠ Distress signal{hazard.distressSignals?.length === 1 ? '' : 's'}: {hazard.distressSignals?.join(', ') || 'active'}</em></p>
          )}
          {hazard.growthTier && <p><em>Growth tier: {hazard.growthTier}</em></p>}
        </>
      )}

      <hr />
    </div>
  );
}
