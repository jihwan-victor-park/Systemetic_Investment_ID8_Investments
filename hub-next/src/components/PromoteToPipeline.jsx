'use client';

import { useState } from 'react';
import RunAnalysisButton from './RunAnalysisButton';
import { PUBLIC_STAGES, STAGE_LABELS, STAGE_BASEPATH } from '@/lib/stages';
import styles from './PromoteToPipeline.module.css';

// Promotes a VC-portfolio-only company (this drill-in page's whole reason
// to exist -- see VCPortfolioCompanyPage's docstring) into ID8's real
// pipeline, then immediately offers RunAnalysisButton without navigating
// away -- same two-step "Add to pipeline" -> "Run Analysis" flow
// PortfolioTable.jsx's pipeline cell already uses, just here on the
// standalone company page instead of a table row.
//
// The round is a required field, not inferred silently -- createCompanyFromPortfolio
// rejects a blank one (see lib/companies.js). `defaultRound` pre-fills it from
// whatever's already known (the Stage 0-researched current stage, or the
// on-file latest round) so the common case is just "confirm and go," but a
// human always confirms the value that lands in the pipeline's Series field
// rather than it silently staying blank.
//
// sourceVCName is best-effort attribution (the first VC relationship found),
// stored as origin.leadInvestors -- purely informational, never used to gate
// anything.
export default function PromoteToPipeline({ companyName, sourceVCName, defaultRound }) {
  const [round, setRound] = useState(defaultRound || '');
  const [stage, setStage] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null); // { slug, stage } once added

  async function submit(e) {
    e.preventDefault();
    if (!round.trim() || !stage) return;
    setSaving(true);
    setError('');
    try {
      const res = await fetch('/api/companies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: companyName, stage, sourceVCName, round: round.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) {
        const message = data.error === 'already-exists' ? 'Already in the pipeline (name mismatch?)'
          : data.error === 'invalid-round' ? 'The latest round is required'
          : 'Failed — try again';
        throw new Error(message);
      }
      setResult({ slug: data.slug, stage });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (result) {
    return (
      <div className={styles.wrap}>
        <a href={`${STAGE_BASEPATH[result.stage]}/${result.slug}`} className={styles.stageLink}>
          Added to {STAGE_LABELS[result.stage]} ✓
        </a>
        <RunAnalysisButton slug={result.slug} name={companyName} />
      </div>
    );
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <label className={styles.field}>
        <span className={styles.label}>The latest round is:</span>
        <input
          type="text"
          className={styles.input}
          value={round}
          disabled={saving}
          onChange={(e) => setRound(e.target.value)}
          placeholder="e.g. Series B"
          required
        />
      </label>
      <label className={styles.field}>
        <span className={styles.label}>Add to:</span>
        <select
          className={styles.select}
          disabled={saving}
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          required
        >
          <option value="" disabled>Choose a stage…</option>
          {PUBLIC_STAGES.map((s) => (
            <option key={s} value={s}>{STAGE_LABELS[s]}</option>
          ))}
        </select>
      </label>
      <button type="submit" className={styles.submit} disabled={saving || !round.trim() || !stage}>
        {saving ? 'Adding…' : 'Add to pipeline'}
      </button>
      {error && <span className={styles.error}>{error}</span>}
    </form>
  );
}
