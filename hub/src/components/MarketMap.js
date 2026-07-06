import React, { useMemo, useState } from 'react';
import styles from './MarketMap.module.css';
import { MARKET_MAPS, CAT_CODE, freshness, firmCode, domainOf } from '../data/marketMapData';

const FRESH_LABEL = { fresh: 'Fresh', aging: 'Aging', stale: 'Stale', undated: 'Undated' };
const FRESH_BADGE = { fresh: 'badge--gate', aging: 'badge--borderline', stale: 'badge--below', undated: 'badge--below' };

const ARROW = (
  <svg className={styles.arrow} width="13" height="13" viewBox="0 0 16 16" fill="none">
    <path d="M4 12L12 4M12 4H5.5M12 4V10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function sortItems(items) {
  return items.slice().sort((a, b) => {
    const av = a.ym || 0, bv = b.ym || 0;
    if (av !== bv) return bv - av;
    return a.firm.localeCompare(b.firm);
  });
}

function Card({ item, mode }) {
  const fr = freshness(item.ym);
  const sub = mode === 'cat' ? item.firm : item.cat;
  return (
    <a className={styles.card} href={item.url} target="_blank" rel="noopener noreferrer">
      <div className={styles.cardTop}>
        <span className={styles.cardSub}>{sub}</span>
        <span className={`badge ${FRESH_BADGE[fr]}`} style={{ fontSize: '0.6rem', padding: '1px 6px' }}>{FRESH_LABEL[fr]}</span>
      </div>
      <div className={styles.cardTitle}>{item.title}</div>
      {item.note && <span className={styles.note}>{item.note}</span>}
      <div className={styles.cardFoot}>
        <span className={styles.domain}>{domainOf(item.url)}</span>
        {ARROW}
      </div>
    </a>
  );
}

function Section({ id, code, isFirm, title, items, mode }) {
  const sorted = sortItems(items);
  return (
    <section className={styles.section} id={id}>
      <div className={styles.secHead}>
        <span className={`${styles.code}${isFirm ? ` ${styles.firm}` : ''}`}>{code}</span>
        <span className={styles.secTitle}>{title}</span>
        <span className={styles.secCount}>{sorted.length} {sorted.length === 1 ? 'map' : 'maps'}</span>
      </div>
      <div className={styles.grid}>
        {sorted.map((it, i) => <Card key={i} item={it} mode={mode} />)}
      </div>
    </section>
  );
}

export default function MarketMap() {
  const [mode, setMode] = useState('cat');
  const [frFilter, setFrFilter] = useState('all');
  const [q, setQ] = useState('');

  const rows = useMemo(() => {
    const query = q.trim().toLowerCase();
    return MARKET_MAPS.filter((d) => {
      if (frFilter !== 'all' && freshness(d.ym) !== frFilter) return false;
      if (query && !(`${d.firm} ${d.title} ${d.cat} ${domainOf(d.url)}`.toLowerCase().includes(query))) return false;
      return true;
    });
  }, [q, frFilter]);

  const grouped = useMemo(() => {
    const key = mode === 'cat' ? 'cat' : 'firm';
    const byKey = {};
    rows.forEach((d) => { (byKey[d[key]] = byKey[d[key]] || []).push(d); });
    return Object.keys(byKey).sort((a, b) => a.localeCompare(b)).map((k) => ({ key: k, items: byKey[k] }));
  }, [rows, mode]);

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const totalMaps = MARKET_MAPS.length;
  const totalCats = new Set(MARKET_MAPS.map((d) => d.cat)).size;
  const totalFirms = new Set(MARKET_MAPS.map((d) => d.firm)).size;

  return (
    <div className={styles.board}>
      <div className={styles.stats}>
        <span>{totalMaps} maps</span>
        <span>{totalCats} categories</span>
        <span>{totalFirms} sources</span>
        <span>Freshness as of Jul 2026</span>
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
          />
        ))
      )}
    </div>
  );
}
