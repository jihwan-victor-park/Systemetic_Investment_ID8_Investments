'use client';

import { useMemo, useState } from 'react';
import styles from './SortableTable.module.css';

// Generic sortable/filterable table for the deal-listing pages (Deal
// Summaries, Qualified Deals). Each column optionally supplies `sortValue`
// (row -> comparable) to make its header clickable, and `filterValue`
// (row -> string) to make it part of the free-text search. Sorting handles
// numbers and strings; nullish values always sort to the bottom regardless
// of direction, so "no score yet" rows don't dominate a descending sort.
export default function SortableTable({ columns, rows, rowKey, defaultSort, searchPlaceholder, emptyMessage }) {
  const [sortKey, setSortKey] = useState(defaultSort?.key ?? null);
  const [sortDir, setSortDir] = useState(defaultSort?.dir ?? 'asc');
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) =>
      columns.some((c) => {
        const v = c.filterValue ? c.filterValue(row) : c.sortValue ? c.sortValue(row) : row[c.key];
        return v != null && String(v).toLowerCase().includes(q);
      }),
    );
  }, [rows, query, columns]);

  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return filtered;
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = col.sortValue(a);
      const bv = col.sortValue(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortKey, sortDir, columns]);

  function toggleSort(col) {
    if (!col.sortValue) return;
    if (sortKey === col.key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(col.key);
      setSortDir(col.defaultDir || 'asc');
    }
  }

  return (
    <div className={styles.wrap}>
      {searchPlaceholder !== false && (
        <input
          type="text"
          className={styles.search}
          placeholder={searchPlaceholder || 'Filter…'}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      )}
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={c.sortValue ? styles.sortableHeader : undefined}
                onClick={c.sortValue ? () => toggleSort(c) : undefined}
              >
                {c.label}
                {c.sortValue && (
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
            <tr key={rowKey(row)}>
              {columns.map((c) => (
                <td key={c.key}>{c.render ? c.render(row) : row[c.key]}</td>
              ))}
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr><td colSpan={columns.length}><em>{rows.length === 0 ? (emptyMessage || 'No results.') : 'No rows match your filter.'}</em></td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
