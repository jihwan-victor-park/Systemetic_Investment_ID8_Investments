'use client';

import { useState, useEffect } from 'react';
import styles from './PartnerVCsAdmin.module.css';

// Adds a partner's own personal contact into a VC firm -- distinct from the
// curated Tier 1 list (TopVCsAdmin). `defaultTrackedBy` is the signed-in
// user's name (there's no per-partner identity in the auth/session model
// yet, so this is a free-text field seeded from whoever's adding the VC,
// editable to any partner's name).
export default function PartnerVCsAdmin({ defaultTrackedBy }) {
  const [vcs, setVcs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [trackedBy, setTrackedBy] = useState(defaultTrackedBy || '');
  const [contact, setContact] = useState('');
  const [sector, setSector] = useState('');
  const [website, setWebsite] = useState('');
  const [note, setNote] = useState('');

  useEffect(() => {
    fetch('/api/partner-vcs')
      .then((r) => r.json())
      .then((d) => setVcs(d.vcs || []))
      .finally(() => setLoading(false));
  }, []);

  const add = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    const body = {
      name: name.trim(),
      trackedBy: trackedBy.trim(),
      contact: contact.trim(),
      sector: sector.trim(),
      website: website.trim(),
      note: note.trim(),
    };
    const res = await fetch('/api/partner-vcs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      const { id } = await res.json();
      setVcs([...vcs, { id, ...body, portfolio: [], news: [] }]);
      setName('');
      setContact('');
      setSector('');
      setWebsite('');
      setNote('');
    }
  };

  const remove = async (id) => {
    setVcs(vcs.filter((v) => v.id !== id));
    await fetch(`/api/partner-vcs?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
  };

  return (
    <div className={styles.board}>
      <form className={styles.form} onSubmit={add}>
        <div>
          <div className={styles.label}>Firm</div>
          <input className={styles.input} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Acme Ventures" />
        </div>
        <div>
          <div className={styles.label}>Tracked by</div>
          <input className={styles.input} value={trackedBy} onChange={(e) => setTrackedBy(e.target.value)} placeholder="Which partner" />
        </div>
        <div>
          <div className={styles.label}>Contact</div>
          <input className={styles.input} value={contact} onChange={(e) => setContact(e.target.value)} placeholder="e.g. A. Rivera" />
        </div>
        <div>
          <div className={styles.label}>Website</div>
          <input className={styles.input} value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="e.g. acmevc.com" />
        </div>
        <div className={styles.full}>
          <div className={styles.label}>Note</div>
          <textarea className={styles.textarea} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional — context on the relationship" />
        </div>
        <div className={`${styles.full} ${styles.actions}`}>
          <button className={styles.add} type="submit">Add</button>
        </div>
      </form>

      <div className={styles.list}>
        {!loading && vcs.length === 0 && <div className={styles.empty}>No partner VCs added yet.</div>}
        {vcs.map((v) => (
          <div className={styles.item} key={v.id}>
            <div>
              {v.trackedBy && <span className={styles.tag}>{v.trackedBy}</span>}
              <span className={styles.itemTitle}>{v.name}</span>
              {v.contact && <div className={styles.itemNote}>Contact: {v.contact}</div>}
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
