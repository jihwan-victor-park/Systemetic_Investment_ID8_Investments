'use client';

import { useState } from 'react';
import Link from 'next/link';
import { STAGES, STAGE_LABELS } from '@/lib/stages';
import styles from './HubSearchPanel.module.css';

// "Search the Hub" -- a structured facet search over tracked companies
// (VC, round, Radar Category, stage, minimum fit score), not a natural-
// language query. Deliberately not dressed up as chat: it's a filter panel
// that happens to live next to Research Chat, since both answer "what do we
// already know" rather than "go research something new." Covers queries
// like "who's Series A/B, invested by a partner VC, clearing our score gate"
// today; "probable to be raising" isn't filterable yet since that metric
// doesn't exist (see the Portfolio table's "Coming soon" column).
export default function HubSearchPanel() {
  const [vc, setVc] = useState('');
  const [round, setRound] = useState('');
  const [radarCategory, setRadarCategory] = useState('');
  const [stage, setStage] = useState('any');
  const [minFitScore, setMinFitScore] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);

  async function search(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (vc.trim()) params.set('vc', vc.trim());
      if (round.trim()) params.set('round', round.trim());
      if (radarCategory.trim()) params.set('radarCategory', radarCategory.trim());
      if (stage !== 'any') params.set('stage', stage);
      if (minFitScore !== '') params.set('minFitScore', minFitScore);
      const res = await fetch(`/api/hub-search?${params.toString()}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'search failed');
      setResults(data.results || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.wrap}>
      <form className={styles.filters} onSubmit={search}>
        <div className={styles.field}>
          <label className={styles.label}>VC</label>
          <input className={styles.input} value={vc} onChange={(e) => setVc(e.target.value)} placeholder="e.g. Founders Fund" />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>Round</label>
          <input className={styles.input} value={round} onChange={(e) => setRound(e.target.value)} placeholder="e.g. Series B" />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>Radar Category</label>
          <input className={styles.input} value={radarCategory} onChange={(e) => setRadarCategory(e.target.value)} placeholder="e.g. AI Infra" />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>Stage</label>
          <select className={styles.select} value={stage} onChange={(e) => setStage(e.target.value)}>
            <option value="any">Any</option>
            {STAGES.map((s) => (
              <option key={s} value={s}>{STAGE_LABELS[s]}</option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label}>Min. fit score</label>
          <input
            className={styles.input}
            type="number"
            step="0.1"
            min="1"
            max="4"
            value={minFitScore}
            onChange={(e) => setMinFitScore(e.target.value)}
            placeholder="e.g. 3.0"
          />
        </div>
        <button className={styles.searchBtn} type="submit" disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
      </form>

      {error && <p className={styles.error}>{error}</p>}

      {results === null ? (
        <p className={styles.empty}>Set any combination of filters and search — results pull straight from what&rsquo;s already tracked in the Hub.</p>
      ) : results.length === 0 ? (
        <p className={styles.empty}>No matches for these filters.</p>
      ) : (
        <div className={styles.results}>
          {results.map((r) => (
            <Link key={r.slug} href={r.href} className={styles.resultRow}>
              <div className={styles.resultMain}>
                <span className={styles.resultName}>{r.name}</span>
                <span className={styles.resultStage}>{r.stageLabel}</span>
              </div>
              <div className={styles.resultMeta}>
                {[r.round, r.radarCategory, r.via.length ? `via ${r.via.join(', ')}` : null].filter(Boolean).join(' · ') || 'No detail recorded'}
              </div>
              <div className={styles.resultScore}>{r.fitScore != null ? `${r.fitScore.toFixed(1)} / 4` : '—'}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
