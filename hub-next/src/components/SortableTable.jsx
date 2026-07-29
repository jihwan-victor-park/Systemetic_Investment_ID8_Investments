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
//
// `filterGroups` ([{key, label, options: [{key,label}]}]) replaces the old
// single-purpose "Also in" tag filter (2026-07-29) with a generic one: any
// number of independent toggle-button groups, each reading a row's
// `filterValues[group.key]` (a single value or array of values). Multiselect
// (OR) within a group, AND across groups if more than one is active --
// e.g. Top 10 VCs' Stage filter, or Radar's keyword chips (those are driven
// by RadarBoard.jsx instead, since they need to filter two separate table
// instances at once, but the matching rule is the same). `initialFilters`
// seeds the starting selection (e.g. a VC directory link landing pre-filtered
// to `?pipeline=qualified,radar`).
export default function SortableTable({ columns, rows, defaultSort, searchPlaceholder, emptyMessage, filterGroups, initialFilters }) {
  const [sortKey, setSortKey] = useState(defaultSort?.key ?? null);
  const [sortDir, setSortDir] = useState(defaultSort?.dir ?? 'asc');
  const [query, setQuery] = useState('');
  const [activeFilters, setActiveFilters] = useState(initialFilters || {});

  function toggleFilter(groupKey, optionKey) {
    setActiveFilters((prev) => {
      const current = prev[groupKey] || [];
      const next = current.includes(optionKey) ? current.filter((k) => k !== optionKey) : [...current, optionKey];
      return { ...prev, [groupKey]: next };
    });
  }

  function matchesGroup(row, groupKey, activeKeys) {
    if (!activeKeys?.length) return true;
    const value = row.filterValues?.[groupKey];
    const rowValues = Array.isArray(value) ? value : [value];
    return activeKeys.some((k) => rowValues.includes(k));
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((row) => {
      for (const groupKey of Object.keys(activeFilters)) {
        if (!matchesGroup(row, groupKey, activeFilters[groupKey])) return false;
      }
      if (!q) return true;
      return columns.some((c) => {
        const v = row.search?.[c.key] ?? row.sort?.[c.key];
        return v != null && String(v).toLowerCase().includes(q);
      });
    });
  }, [rows, query, columns, activeFilters]);

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
        {filterGroups?.map((group) => (
          <div className={styles.filterGroup} key={group.key}>
            <span className={styles.filterGroupLabel}>{group.label}</span>
            {group.options.map((opt) => (
              <button
                key={opt.key}
                type="button"
                className={styles.filterBtn}
                data-active={(activeFilters[group.key] || []).includes(opt.key)}
                onClick={() => toggleFilter(group.key, opt.key)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        ))}
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
