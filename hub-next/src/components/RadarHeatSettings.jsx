'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './RadarHeatSettings.module.css';

// One-line, inline control for the two knobs behind Radar's Hot/Cold split
// (lib/radarHeatScore.js / lib/radarConfig.js) -- deliberately NOT a boxed
// admin panel like the old RadarRulesAdmin.jsx this replaces (Oscar: "you
// fucked up the ui there"). Same optimistic-save/revert convention as
// StageSelect.jsx. Editing takes effect on save via router.refresh() -- no
// redeploy, no waiting on the next Python scan run.
export default function RadarHeatSettings({ config, canEdit }) {
  const router = useRouter();
  const [hotWindowMonths, setHotWindowMonths] = useState(config.hotWindowMonths);
  const [hotThreshold, setHotThreshold] = useState(config.hotThreshold);
  const [watchFloor, setWatchFloor] = useState(config.watchFloor);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [dirty, setDirty] = useState(false);

  if (!canEdit) {
    return (
      <p className={styles.readonly}>
        Hot: within {config.hotWindowMonths} {config.hotWindowMonths === 1 ? 'month' : 'months'} of its predicted raise window, or a heat score of {config.hotThreshold}+. Dropped from view below {config.watchFloor} for a few scans running.
      </p>
    );
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const res = await fetch('/api/radar-config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hotWindowMonths, hotThreshold, watchFloor }),
      });
      if (!res.ok) throw new Error('save-failed');
      setDirty(false);
      router.refresh();
    } catch {
      setError('Failed — try again');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className={styles.row} onSubmit={save}>
      <span className={styles.label}>Hot window</span>
      <input
        type="number" min="0.5" step="0.5" className={styles.input}
        value={hotWindowMonths}
        onChange={(e) => { setHotWindowMonths(e.target.value); setDirty(true); }}
      />
      <span className={styles.unit}>months</span>
      <span className={styles.sep}>·</span>
      <span className={styles.label}>Heat score threshold</span>
      <input
        type="number" min="0.5" step="0.5" className={styles.input}
        value={hotThreshold}
        onChange={(e) => { setHotThreshold(e.target.value); setDirty(true); }}
      />
      <span className={styles.unit}>pts</span>
      <span className={styles.sep}>·</span>
      <span className={styles.label}>Watch floor</span>
      <input
        type="number" min="0.5" step="0.5" className={styles.input}
        value={watchFloor}
        onChange={(e) => { setWatchFloor(e.target.value); setDirty(true); }}
      />
      <span className={styles.unit}>pts</span>
      {dirty && <button className={styles.save} type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>}
      {error && <span className={styles.error}>{error}</span>}
    </form>
  );
}
