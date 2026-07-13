'use client';

import { useState, useEffect } from 'react';
import styles from './TopVCsAdmin.module.css';

const TIERS = ['Tier 1', 'Tier 2', 'Tier 3'];

export default function TopVCsAdmin() {
  const [vcs, setVcs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tier, setTier] = useState(TIERS[0]);
  const [name, setName] = useState('');
  const [sector, setSector] = useState('');
  const [website, setWebsite] = useState('');
  const [note, setNote] = useState('');

  useEffect(() => {
    fetch('/api/top-vcs')
      .then((r) => r.json())
      .then((d) => setVcs(d.vcs || []))
      .finally(() => setLoading(false));
  }, []);

  const add = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    const res = await fetch('/api/top-vcs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim(), tier, sector: sector.trim(), website: website.trim(), note: note.trim() }),
    });
    if (res.ok) {
      const { id } = await res.json();
      setVcs([...vcs, { id, name: name.trim(), tier, sector: sector.trim(), website: website.trim(), note: note.trim() }]);
      setName('');
      setSector('');
      setWebsite('');
      setNote('');
    }
  };

  const remove = async (id) => {
    setVcs(vcs.filter((v) => v.id !== id));
    await fetch(`/api/top-vcs?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
  };

  return (
    <div className={styles.board}>
      <form className={styles.form} onSubmit={add}>
        <div>
          <div className={styles.label}>Tier</div>
          <select className={styles.select} value={tier} onChange={(e) => setTier(e.target.value)}>
            {TIERS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <div className={styles.label}>Firm</div>
          <input className={styles.input} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Sequoia Capital" />
        </div>
        <div>
          <div className={styles.label}>Sector focus</div>
          <input className={styles.input} value={sector} onChange={(e) => setSector(e.target.value)} placeholder="e.g. AI infra, defense tech" />
        </div>
        <div>
          <div className={styles.label}>Website</div>
          <input className={styles.input} value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="e.g. sequoiacap.com" />
        </div>
        <div className={styles.full}>
          <div className={styles.label}>Note</div>
          <textarea className={styles.textarea} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional — why they're tiered here" />
        </div>
        <div className={`${styles.full} ${styles.actions}`}>
          <button className={styles.add} type="submit">Add</button>
        </div>
      </form>

      <div className={styles.list}>
        {!loading && vcs.length === 0 && <div className={styles.empty}>No VCs added yet.</div>}
        {vcs.map((v) => (
          <div className={styles.item} key={v.id}>
            <div>
              <span className={styles.tag}>{v.tier}</span>
              <span className={styles.itemTitle}>{v.name}</span>
              {v.sector && <div className={styles.itemNote}>{v.sector}</div>}
              {v.note && <div className={styles.itemNote}>{v.note}</div>}
            </div>
            <div className={styles.meta}>
              {v.website && <a href={`https://${v.website}`} target="_blank" rel="noopener noreferrer">{v.website}</a>}
              <button className={styles.del} onClick={() => remove(v.id)} title="Remove">×</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
