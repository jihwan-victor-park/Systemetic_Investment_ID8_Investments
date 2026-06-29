import React, { useState, useEffect } from 'react';
import styles from './IdeaBoard.module.css';

const KEY = 'id8-admin-board';
const TYPES = ['Idea', 'Suggestion', 'Request', 'Bug'];

export default function IdeaBoard() {
  const [items, setItems] = useState([]);
  const [type, setType] = useState('Idea');
  const [title, setTitle] = useState('');
  const [note, setNote] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    try { const raw = localStorage.getItem(KEY); if (raw) setItems(JSON.parse(raw)); } catch (e) {}
  }, []);

  const persist = next => {
    setItems(next);
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch (e) {}
  };

  const add = e => {
    e.preventDefault();
    if (!title.trim()) return;
    const entry = { id: Date.now(), type, title: title.trim(), note: note.trim(), date: new Date().toISOString().slice(0, 10) };
    persist([entry, ...items]);
    setTitle(''); setNote('');
  };

  const remove = id => persist(items.filter(i => i.id !== id));

  const markdown = items
    .map(i => `- **[${i.type}] ${i.title}**${i.note ? ` — ${i.note}` : ''}  _(${i.date})_`)
    .join('\n');

  const copy = () => {
    try { navigator.clipboard.writeText(markdown); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch (e) {}
  };

  return (
    <div className={styles.board}>
      <form className={styles.form} onSubmit={add}>
        <div>
          <div className={styles.label}>Type</div>
          <select className={styles.select} value={type} onChange={e => setType(e.target.value)}>
            {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <div className={styles.label}>Title</div>
          <input className={styles.input} value={title} onChange={e => setTitle(e.target.value)} placeholder="One line" />
        </div>
        <div className={styles.full}>
          <div className={styles.label}>Note</div>
          <textarea className={styles.textarea} value={note} onChange={e => setNote(e.target.value)} placeholder="Optional detail" />
        </div>
        <div className={`${styles.full} ${styles.actions}`}>
          <button className={styles.add} type="submit">Add</button>
          {items.length > 0 && (
            <button className={styles.copy} type="button" onClick={copy}>{copied ? 'Copied' : 'Copy all as Markdown'}</button>
          )}
        </div>
      </form>

      <div className={styles.list}>
        {items.length === 0 && <div className={styles.empty}>Nothing captured yet. Add an idea, suggestion, or request above.</div>}
        {items.map(i => (
          <div className={styles.item} key={i.id}>
            <div>
              <span className={styles.tag}>{i.type}</span>
              <span className={styles.itemTitle}>{i.title}</span>
              {i.note && <div className={styles.itemNote}>{i.note}</div>}
            </div>
            <div className={styles.meta}>
              {i.date}
              <button className={styles.del} onClick={() => remove(i.id)} title="Remove">×</button>
            </div>
          </div>
        ))}
      </div>

      <p className={styles.hint}>
        Entries are saved in this browser. Use “Copy all as Markdown” to paste them into the page below and commit them to the repo.
      </p>
    </div>
  );
}
