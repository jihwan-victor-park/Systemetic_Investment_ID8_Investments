'use client';

import { useMemo, useState } from 'react';
import styles from './SortableTable.module.css';

// Generic sortable/filterable table for the deal-listing pages (Deal
// Summaries, Watchlist, Pipeline, Qualified Deals). Callers are Server
// Components, so `columns` and `rows` must be plain, RSC-serializable data
// -- no function props. Each row supplies pre-computed `sort` values
// (primitives to compare on), optional `search` strings (falls back to
// `sort` when omitted), and `cells` (already-rendered React nodes to
// display) -- the caller does all the row -> cell mapping server-side.
export default function SortableTable({ columns, rows, defaultSort, searchPlaceholder, emptyMessage, tagFilterOptions }) {
  const [sortKey, setSortKey] = useState(defaultSort?.key ?? null);
  const [sortDir, setSortDir] = useState(defaultSort?.dir ?? 'asc');
  const [query, setQuery] = useState('');
  const [activeTags, setActiveTags] = useState([]);

  function toggleTag(key) {
    setActiveTags((prev) => (prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]));
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((row) => {
      if (activeTags.length && !activeTags.some((t) => row.tags?.includes(t))) return false;
      if (!q) return true;
      return columns.some((c) => {
        const v = row.search?.[c.key] ?? row.sort?.[c.key];
        return v != null && String(v).toLowerCase().includes(q);
      });
    });
  }, [rows, query, columns, activeTags]);

  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sortKey && c.sortable);
    if (!col) return filtered;
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = a.sort?.[col.key];
      const bv = b.sort?.[col.key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortKey, sortDir, columns]);

  function toggleSort(col) {
    if (!col.sortable) return;
    if (sortKey === col.key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(col.key);
      setSortDir(col.defaultDir || 'asc');
    }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.controls}>
        {searchPlaceholder !== false && (
          <input
            type="text"
            className={styles.search}
            placeholder={searchPlaceholder || 'Filter…'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        )}
        {tagFilterOptions?.length > 0 && (
          <div className={styles.tagFilter}>
            <span className={styles.tagFilterLabel}>Also in</span>
            {tagFilterOptions.map((opt) => (
              <button
                key={opt.key}
                type="button"
                className={styles.tagFilterBtn}
                data-tag={opt.key}
                data-active={activeTags.includes(opt.key)}
                onClick={() => toggleTag(opt.key)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className={styles.scrollWrap}>
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={c.sortable ? styles.sortableHeader : undefined}
                  onClick={c.sortable ? () => toggleSort(c) : undefined}
                >
                  {c.label}
                  {c.sortable && (
                    <span className={styles.sortArrow} data-active={sortKey === c.key}>
                      {sortKey === c.key ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.key}>
                {columns.map((c) => (
                  <td key={c.key}>{row.cells[c.key]}</td>
                ))}
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={columns.length}>
                  <em>{rows.length === 0 ? (emptyMessage || 'No results.') : 'No rows match your filter.'}</em>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
