'use client';

import { useEffect, useMemo, useState } from 'react';
import styles from './MarketMap.module.css';
import {
  CAT_CODE, freshness, firmCode, domainOf,
  ymFromMonthInput, firmsList, firmForDomain,
} from '@/data/marketMapHelpers';

const FRESH_LABEL = { fresh: 'Fresh', aging: 'Aging', stale: 'Stale', undated: 'Undated' };

const ARROW = (
  <svg className={styles.arrow} width="13" height="13" viewBox="0 0 16 16" fill="none">
    <path d="M4 12L12 4M12 4H5.5M12 4V10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function todayMonthValue() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function sortItems(items) {
  return items.slice().sort((a, b) => {
    const av = a.ym || 0, bv = b.ym || 0;
    if (av !== bv) return bv - av;
    return a.firm.localeCompare(b.firm);
  });
}

// Clicking anywhere on the card opens the map image in a lightbox; the arrow
// is its own link so it can still take you straight to the original source
// without stealing the click from the lightbox.
function Card({ item, mode, onOpen }) {
  const fr = freshness(item.ym);
  const sub = mode === 'cat' ? item.firm : item.cat;
  const hasImage = !!item.image;

  const activate = () => {
    if (hasImage) onOpen(item);
    else window.open(item.url, '_blank', 'noopener,noreferrer');
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      activate();
    }
  };

  return (
    <div
      className={styles.card}
      role="button"
      tabIndex={0}
      onClick={activate}
      onKeyDown={onKeyDown}
    >
      <div className={styles.cardTop}>
        <span className={styles.cardSub}>{sub}</span>
        <span className={`${styles.date} ${styles[`d-${fr}`]}`}><i className={styles.dot} />{item.date}</span>
      </div>
      <div className={styles.cardTitle}>{item.title}</div>
      {item.note && <span className={styles.note}>{item.note}</span>}
      <div className={styles.cardFoot}>
        <span className={styles.domain}>{domainOf(item.url)}</span>
        <a
          className={styles.arrowLink}
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          aria-label="Open original source"
        >
          {ARROW}
        </a>
      </div>
    </div>
  );
}

function Lightbox({ item, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!item) return null;

  return (
    <div className={styles.lbOverlay} onClick={onClose}>
      <div className={styles.lbPanel} onClick={(e) => e.stopPropagation()}>
        <button className={styles.lbClose} onClick={onClose} aria-label="Close">×</button>
        <div className={styles.lbImgWrap}>
          {item.imageIsDoc ? (
            <a className={styles.lbDoc} href={item.image} target="_blank" rel="noopener noreferrer">
              Open document
            </a>
          ) : (
            <img className={styles.lbImg} src={item.image} alt={item.title} />
          )}
        </div>
        <div className={styles.lbFoot}>
          <div>
            <div className={styles.lbTitle}>{item.title}</div>
            <div className={styles.lbSub}>{item.firm} · {item.date}</div>
          </div>
          <a className={styles.lbSource} href={item.url} target="_blank" rel="noopener noreferrer">
            Original source {ARROW}
          </a>
        </div>
      </div>
    </div>
  );
}

function Section({ id, code, isFirm, title, items, mode, onOpen }) {
  const sorted = sortItems(items);
  return (
    <section className={styles.section} id={id}>
      <div className={styles.secHead}>
        <span className={`${styles.code}${isFirm ? ` ${styles.firm}` : ''}`}>{code}</span>
        <span className={styles.secTitle}>{title}</span>
        <span className={styles.secCount}>{sorted.length} {sorted.length === 1 ? 'map' : 'maps'}</span>
      </div>
      <div className={styles.grid}>
        {sorted.map((it, i) => <Card key={i} item={it} mode={mode} onOpen={onOpen} />)}
      </div>
    </section>
  );
}

const EMPTY_FORM = { url: '', firm: '', cat: '', title: '', month: todayMonthValue(), note: '', photo: null };

function AddMapForm({ entries, onAdded }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [status, setStatus] = useState('idle'); // idle | saving | error
  const firms = useMemo(() => firmsList(entries), [entries]);
  const cats = useMemo(() => Object.keys(CAT_CODE).sort((a, b) => a.localeCompare(b)), []);

  const field = (key) => ({
    value: form[key],
    onChange: (e) => setForm((f) => ({ ...f, [key]: e.target.value })),
  });

  const onUrlBlur = () => {
    if (form.firm.trim()) return;
    const suggested = firmForDomain(entries, form.url);
    if (suggested) setForm((f) => ({ ...f, firm: suggested }));
  };

  const onPhotoChange = (e) => {
    setForm((f) => ({ ...f, photo: e.target.files?.[0] || null }));
  };

  const add = async (e) => {
    e.preventDefault();
    if (!form.url.trim() || !form.firm.trim() || !form.cat.trim() || !form.title.trim() || !form.photo) return;
    const { ym, date } = ymFromMonthInput(form.month);
    setStatus('saving');
    try {
      const body = new FormData();
      body.set('firm', form.firm.trim());
      body.set('title', form.title.trim());
      body.set('category', form.cat.trim());
      body.set('url', form.url.trim());
      body.set('ym', String(ym));
      body.set('dateLabel', date);
      body.set('note', form.note.trim());
      body.set('photo', form.photo);

      const res = await fetch('/api/market-map', { method: 'POST', body });
      if (!res.ok) throw new Error('save-failed');
      const saved = await res.json();
      onAdded({
        firm: form.firm.trim(), title: form.title.trim(), cat: form.cat.trim(), url: form.url.trim(),
        ym, date, note: form.note.trim() || undefined,
        image: saved.hasImage ? `/api/market-map/image/${saved.id}` : null,
        imageIsDoc: form.photo.type === 'application/pdf',
      });
      setForm({ ...EMPTY_FORM, month: form.month });
      setStatus('idle');
    } catch (err) {
      setStatus('error');
    }
  };

  return (
    <div className={styles.addWrap}>
      <form className={styles.addForm} onSubmit={add}>
        <div className={styles.addFull}>
          <div className={styles.addLabel}>Photo</div>
          <input
            className={styles.addFile}
            type="file"
            accept="image/*,application/pdf"
            onChange={onPhotoChange}
            required
          />
          {form.photo && <span className={styles.hint}>{form.photo.name}</span>}
        </div>
        <div className={styles.addFull}>
          <div className={styles.addLabel}>Link</div>
          <input {...field('url')} onBlur={onUrlBlur} className={styles.addInput} type="url" placeholder="https://…" required />
        </div>
        <div>
          <div className={styles.addLabel}>Name</div>
          <input {...field('title')} className={styles.addInput} placeholder="e.g. Defense Tech Landscape" required />
        </div>
        <div>
          <div className={styles.addLabel}>VC</div>
          <input {...field('firm')} className={styles.addInput} list="mm-firm-list" placeholder="Autocompletes from the link" required />
          <datalist id="mm-firm-list">{firms.map((f) => <option key={f} value={f} />)}</datalist>
        </div>
        <div>
          <div className={styles.addLabel}>Category</div>
          <input {...field('cat')} className={styles.addInput} list="mm-cat-list" placeholder="Existing or new" required />
          <datalist id="mm-cat-list">{cats.map((c) => <option key={c} value={c} />)}</datalist>
        </div>
        <div>
          <div className={styles.addLabel}>Published</div>
          <input {...field('month')} className={styles.addInput} type="month" required />
        </div>
        <div className={styles.addFull}>
          <div className={styles.addLabel}>Note (optional)</div>
          <input {...field('note')} className={styles.addInput} placeholder="e.g. Refreshed" />
        </div>
        <div className={`${styles.addFull} ${styles.addActions}`}>
          <button className={styles.addBtn} type="submit" disabled={status === 'saving'}>
            {status === 'saving' ? 'Saving…' : 'Add to directory'}
          </button>
          {status === 'error' && <span className={styles.hint}>Couldn’t save — try again.</span>}
        </div>
      </form>

      <p className={styles.hint}>
        New entries save straight to the shared directory — no copy-pasting into source files.
        New categories also need a two-letter code added to <code>CAT_CODE</code> in the code.
      </p>
    </div>
  );
}

export default function MarketMap({ initialEntries = [] }) {
  const [entries, setEntries] = useState(initialEntries);
  const [tab, setTab] = useState('browse');
  const [mode, setMode] = useState('cat');
  const [frFilter, setFrFilter] = useState('all');
  const [q, setQ] = useState('');
  const [lightbox, setLightbox] = useState(null);

  useEffect(() => setEntries(initialEntries), [initialEntries]);

  const rows = useMemo(() => {
    const query = q.trim().toLowerCase();
    return entries.filter((d) => {
      if (frFilter !== 'all' && freshness(d.ym) !== frFilter) return false;
      if (query && !(`${d.firm} ${d.title} ${d.cat} ${domainOf(d.url)}`.toLowerCase().includes(query))) return false;
      return true;
    });
  }, [entries, q, frFilter]);

  const grouped = useMemo(() => {
    const key = mode === 'cat' ? 'cat' : 'firm';
    const byKey = {};
    rows.forEach((d) => { (byKey[d[key]] = byKey[d[key]] || []).push(d); });
    return Object.keys(byKey).sort((a, b) => a.localeCompare(b)).map((k) => ({ key: k, items: byKey[k] }));
  }, [rows, mode]);

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const totalMaps = entries.length;
  const totalCats = new Set(entries.map((d) => d.cat)).size;
  const totalFirms = new Set(entries.map((d) => d.firm)).size;
  const nowLabel = new Date().toLocaleDateString('en-US', { month: 'short', year: 'numeric' });

  return (
    <div className={styles.board}>
      <div className={styles.tabs}>
        <button className={tab === 'browse' ? styles.on : ''} onClick={() => setTab('browse')}>Directory</button>
        <button className={tab === 'add' ? styles.on : ''} onClick={() => setTab('add')}>+ Add new</button>
      </div>

      {tab === 'add' ? (
        <AddMapForm
          entries={entries}
          onAdded={(entry) => {
            setEntries((prev) => [entry, ...prev]);
            setTab('browse');
          }}
        />
      ) : (
        <>
          <div className={styles.stats}>
            <span>{totalMaps} maps</span>
            <span>{totalCats} categories</span>
            <span>{totalFirms} sources</span>
            <span>Freshness as of {nowLabel}</span>
          </div>

          <div className={styles.controls}>
            <div className={styles.search}>
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                <circle cx="7" cy="7" r="5" stroke="var(--id8-grey)" strokeWidth="1.5" />
                <line x1="11" y1="11" x2="14.5" y2="14.5" stroke="var(--id8-grey)" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <input
                type="text"
                placeholder="Search firm, category, or map…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                autoComplete="off"
                spellCheck="false"
              />
            </div>
            <div className={styles.seg}>
              <button className={mode === 'cat' ? styles.on : ''} onClick={() => setMode('cat')}>By category</button>
              <button className={mode === 'firm' ? styles.on : ''} onClick={() => setMode('firm')}>By firm</button>
            </div>
            <div className={styles.seg}>
              {['all', 'fresh', 'aging', 'stale'].map((f) => (
                <button key={f} data-fr={f} className={frFilter === f ? styles.on : ''} onClick={() => setFrFilter(f)}>
                  {f === 'all' ? 'All' : FRESH_LABEL[f]}
                </button>
              ))}
            </div>
          </div>

          {mode === 'cat' && grouped.length > 0 && (
            <nav className={styles.pills}>
              {grouped.map(({ key, items }) => (
                <span key={key} className={styles.pill} onClick={() => scrollTo(`mm-${key.replace(/\W+/g, '-')}`)}>
                  <b>{CAT_CODE[key] || ''}</b>{key}<i>{items.length}</i>
                </span>
              ))}
            </nav>
          )}

          {grouped.length === 0 ? (
            <div className={styles.empty}>No maps match those filters.</div>
          ) : (
            grouped.map(({ key, items }) => (
              <Section
                key={key}
                id={`mm-${key.replace(/\W+/g, '-')}`}
                code={mode === 'cat' ? (CAT_CODE[key] || '') : firmCode(key)}
                isFirm={mode === 'firm'}
                title={key}
                items={items}
                mode={mode}
                onOpen={setLightbox}
              />
            ))
          )}
        </>
      )}

      <Lightbox item={lightbox} onClose={() => setLightbox(null)} />
    </div>
  );
}
