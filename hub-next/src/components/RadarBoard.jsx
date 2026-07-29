'use client';

import { useMemo, useState } from 'react';
import SortableTable from './SortableTable';
import RadarHeatSettings from './RadarHeatSettings';
import RadarKeywordFilter from './RadarKeywordFilter';
import { RADAR_TABLE_COLUMNS } from './radarTableColumns';
import styles from './RadarBoard.module.css';

// Hosts both Radar tables (Hot on top, Cold below -- Oscar: "hot should be
// in top") plus the keyword chips above them. A client wrapper, not two
// independent server-rendered SortableTables, purely because the keyword
// chips need to filter BOTH tables from one shared selection -- SortableTable
// itself stays a single-table, self-contained component (its own
// `filterGroups` still drives the unrelated Stage filter on Top 10 VCs/Hot
// Deals). `hotRows`/`coldRows` arrive pre-built (already-rendered React
// elements in `cells`, same as every other SortableTable caller) from the
// Server Component page.
//
// Clicking a keyword EXCLUDES matches (2026-07-29, reversed from the first
// pass) -- the old admin panel's whole job was hiding off-thesis companies,
// and that's what a keyword click does here too, just without the boxed
// admin UI. Nothing is silently lost: excluded companies are named right
// below the chips, and un-toggling the keyword brings them straight back --
// same "nothing is ever deleted" principle RADAR_PLAN.md §1.6 describes, no
// separate pin/restore mechanism needed since the toggle itself is the
// restore.
export default function RadarBoard({ hotRows, coldRows, keywords, radarConfig, canEdit }) {
  const [activeKeywords, setActiveKeywords] = useState([]);

  function toggleKeyword(term) {
    setActiveKeywords((prev) => (prev.includes(term) ? prev.filter((t) => t !== term) : [...prev, term]));
  }

  function matchedActiveKeywords(row) {
    return (row.filterValues?.keyword || []).filter((k) => activeKeywords.includes(k));
  }

  const allRows = useMemo(() => [...hotRows, ...coldRows], [hotRows, coldRows]);
  const excludedRows = useMemo(
    () => (activeKeywords.length ? allRows.filter((r) => matchedActiveKeywords(r).length > 0) : []),
    [allRows, activeKeywords]
  );
  const excludedKeys = useMemo(() => new Set(excludedRows.map((r) => r.key)), [excludedRows]);

  const visibleHot = useMemo(() => hotRows.filter((r) => !excludedKeys.has(r.key)), [hotRows, excludedKeys]);
  const visibleCold = useMemo(() => coldRows.filter((r) => !excludedKeys.has(r.key)), [coldRows, excludedKeys]);

  return (
    <>
      <RadarHeatSettings config={radarConfig} canEdit={canEdit} />
      <RadarKeywordFilter keywords={keywords} active={activeKeywords} onToggle={toggleKeyword} canEdit={canEdit} />

      {excludedRows.length > 0 && (
        <details className={styles.excludedBox} open>
          <summary>Excluded by keyword ({excludedRows.length})</summary>
          <ul className={styles.excludedList}>
            {excludedRows.map((r) => (
              <li key={r.key}>{r.search?.company || r.key} — matched {matchedActiveKeywords(r).join(', ')}</li>
            ))}
          </ul>
        </details>
      )}

      <h2 className={styles.sectionTitle}>Hot ({visibleHot.length})</h2>
      <SortableTable
        columns={RADAR_TABLE_COLUMNS}
        rows={visibleHot}
        defaultSort={{ key: 'heat', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing hot right now."
      />

      <h2 className={styles.sectionTitle}>Cold ({visibleCold.length})</h2>
      <SortableTable
        columns={RADAR_TABLE_COLUMNS}
        rows={visibleCold}
        defaultSort={{ key: 'dealDate', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing on Radar yet."
      />
    </>
  );
}
