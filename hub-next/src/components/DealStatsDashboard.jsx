import { computeDealStats } from '@/lib/dealStats';
import { STAGE_LABELS } from '@/lib/stages';
import styles from './DealStatsDashboard.module.css';

const PIPELINE_STAGES = ['watchlist', 'pipeline', 'qualified', 'radar', 'invested'];

// Summary-statistics landing page (Oscar, 2026-08-06: "the landing page to
// be the summary statistics of the hub... deals qualified/pipeline (the
// ones we get access to), and other metrics such as trending sectors in our
// qualified deals, amounts maybe, averages of the raises of the companies
// we like, average time between rounds... Be imaginative"). Pure
// presentation over computeDealStats()'s already-computed numbers -- see
// that module's own docstring for every metric's exact definition and
// why each one excludes rather than zero-fills missing data.
export default function DealStatsDashboard({ companies }) {
  const stats = computeDealStats(companies);
  const maxSectorCount = stats.topSectors[0]?.count || 1;

  return (
    <div>
      <div className={styles.section}>
        <div className={styles.sectionTitle}>Pipeline</div>
        <div className={styles.card}>
          <div className={styles.statGrid}>
            <div className={styles.stat}>
              <span className={styles.statLabel}>Total tracked</span>
              <span className={styles.statValueLarge}>{stats.total}</span>
            </div>
            {PIPELINE_STAGES.map((s) => (
              <div key={s} className={styles.stat}>
                <span className={styles.statLabel}>{STAGE_LABELS[s]}</span>
                <span className={styles.statValueLarge}>{stats.byStage[s] || 0}</span>
              </div>
            ))}
            <div className={styles.stat}>
              <span className={styles.statLabel}>Passed</span>
              <span className={styles.statValueLarge}>{stats.byTag.passed}</span>
              <span className={styles.statSub}>additive tag — not exclusive of stage above</span>
            </div>
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Access — by stage</div>
        <div className={styles.card}>
          <table className={styles.accessTable}>
            <thead>
              <tr><th>Stage</th><th>Total</th><th>Access</th><th>No access</th><th>Unrecorded</th></tr>
            </thead>
            <tbody>
              {PIPELINE_STAGES.map((s) => {
                const row = stats.accessByStage[s];
                return (
                  <tr key={s}>
                    <td>{STAGE_LABELS[s]}</td>
                    <td>{row.total}</td>
                    <td>{row.access}</td>
                    <td>{row.noAccess}</td>
                    <td>{row.total - row.access - row.noAccess}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Qualified deals — the companies we like</div>
        <div className={styles.twoCol}>
          <div className={styles.card}>
            <div className={styles.statGrid}>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Avg raise size</span>
                <span className={styles.statValueLarge}>{stats.raiseSizeStats.avgMillions != null ? `$${stats.raiseSizeStats.avgMillions}M` : '—'}</span>
                <span className={styles.statSub}>
                  {stats.raiseSizeStats.medianMillions != null && `median $${stats.raiseSizeStats.medianMillions}M`}
                  {stats.raiseSizeStats.count > 0 && ` · ${stats.raiseSizeStats.count} with a round size on file`}
                </span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Median fit score</span>
                <span className={styles.statValueLarge}>{stats.medianFitScore != null ? `${stats.medianFitScore} / 4` : '—'}</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Tier 1 (33) backed</span>
                <span className={styles.statValueLarge}>
                  {stats.tier1BackedRate.total > 0 ? `${Math.round((stats.tier1BackedRate.tier1_33 / stats.tier1BackedRate.total) * 100)}%` : '—'}
                </span>
                <span className={styles.statSub}>{stats.tier1BackedRate.top10} with a Top 10 firm specifically</span>
              </div>
            </div>
          </div>
          <div className={styles.card}>
            <span className={styles.statLabel}>Trending sectors</span>
            {stats.topSectors.length > 0 ? (
              <ul className={styles.sectorList}>
                {stats.topSectors.map((s) => (
                  <li key={s.category} className={styles.sectorRow}>
                    <span>{s.category}</span>
                    <span className={styles.sectorBar}>
                      <span className={styles.sectorBarFill} style={{ width: `${(s.count / maxSectorCount) * 100}%` }} />
                    </span>
                    <span className={styles.sectorCount}>{s.count}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.statSub}>No Radar Category data on qualified deals yet.</p>
            )}
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Deal velocity</div>
        <div className={styles.card}>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Avg time between rounds</span>
            <span className={styles.statValueLarge}>
              {stats.avgDaysBetweenRounds.avgDays != null ? `${Math.round(stats.avgDaysBetweenRounds.avgDays / 30.44)} months` : '—'}
            </span>
            <span className={styles.statSub}>
              {stats.avgDaysBetweenRounds.avgDays != null
                ? `${stats.avgDaysBetweenRounds.avgDays} days, across ${stats.avgDaysBetweenRounds.companiesWithMultipleRounds} tracked round gap${stats.avgDaysBetweenRounds.companiesWithMultipleRounds === 1 ? '' : 's'}`
                : 'not enough multi-round companies on file yet'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
