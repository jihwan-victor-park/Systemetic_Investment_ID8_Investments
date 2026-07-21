'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './GlobalSearch.module.css';

// Cmd/Ctrl+K command palette -- jumps straight to any tab, tracked company,
// or tracked VC by name, so "looking through registries" doesn't mean
// hunting through the sidebar tree by hand. The index is fetched once, lazily
// (only when first opened, not on every page load), and re-filtered locally
// on every keystroke -- a few hundred entries is cheap enough that a live
// Firestore query per keystroke would be pure waste.
export default function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [entries, setEntries] = useState(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    function onKey(e) {
      const isCmdK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k';
      if (isCmdK) {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (!open) {
      setQuery('');
      setActiveIdx(0);
      return;
    }
    if (entries === null) {
      fetch('/api/search-index').then((r) => r.json()).then((d) => setEntries(d.entries || [])).catch(() => setEntries([]));
    }
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    return () => clearTimeout(t);
  }, [open, entries]);

  const q = query.trim().toLowerCase();
  const matches = !entries ? [] : (q
    ? entries.filter((e) => e.label.toLowerCase().includes(q)).slice(0, 40)
    : entries.slice(0, 12));

  function go(href) {
    setOpen(false);
    router.push(href);
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, matches.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && matches[activeIdx]) {
      go(matches[activeIdx].href);
    }
  }

  return (
    <>
      <button type="button" className={styles.trigger} onClick={() => setOpen(true)} aria-label="Search the Hub">
        <span className={styles.icon} aria-hidden="true">⌕</span>
        <span className={styles.triggerLabel}>Search</span>
        <span className={styles.kbd}>⌘K</span>
      </button>
      {open && (
        <div className={styles.overlay} onClick={() => setOpen(false)}>
          <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
            <input
              ref={inputRef}
              className={styles.input}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setActiveIdx(0); }}
              onKeyDown={onKeyDown}
              placeholder="Jump to a tab, company, or VC…"
            />
            <div className={styles.results}>
              {entries === null && <div className={styles.empty}>Loading…</div>}
              {entries !== null && matches.length === 0 && <div className={styles.empty}>No matches.</div>}
              {matches.map((m, i) => (
                <button
                  key={`${m.type}-${m.href}`}
                  type="button"
                  className={`${styles.result} ${i === activeIdx ? styles.resultActive : ''}`}
                  onMouseEnter={() => setActiveIdx(i)}
                  onClick={() => go(m.href)}
                >
                  <span className={styles.resultType}>{m.type}</span>
                  <span className={styles.resultLabel}>{m.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
