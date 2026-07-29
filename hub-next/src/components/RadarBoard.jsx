'use client';

import { useMemo, useState } from 'react';
import SortableTable from './SortableTable';
import RadarHeatSettings from './RadarHeatSettings';
import RadarKeywordFilter from './RadarKeywordFilter';
import { RADAR_TABLE_COLUMNS } from './radarTableColumns';
import styles from './RadarBoard.module.css';

// Hosts both Radar tables (Hot on top, Cold below -- Oscar: "hot should be
// in top") plus the keyword filter chips above them. A client wrapper,
// not two independent server-rendered SortableTables, purely because the
// keyword chips need to filter BOTH tables from one shared selection --
// SortableTable itself stays a single-table, self-contained component (its
// own `filterGroups` still drives the unrelated Stage filter on Top 10
// VCs/Hot Deals). `hotRows`/`coldRows` arrive pre-built (already-rendered
// React elements in `cells`, same as every other SortableTable caller) from
// the Server Component page.
export default function RadarBoard({ hotRows, coldRows, keywords, radarConfig, canEdit }) {
  const [activeKeywords, setActiveKeywords] = useState([]);

  function toggleKeyword(term) {
    setActiveKeywords((prev) => (prev.includes(term) ? prev.filter((t) => t !== term) : [...prev, term]));
  }

  const matchesActiveKeywords = (row) =>
    !activeKeywords.length || activeKeywords.some((k) => row.filterValues?.keyword?.includes(k));

  const visibleHot = useMemo(() => hotRows.filter(matchesActiveKeywords), [hotRows, activeKeywords]);
  const visibleCold = useMemo(() => coldRows.filter(matchesActiveKeywords), [coldRows, activeKeywords]);

  return (
    <>
      <RadarHeatSettings config={radarConfig} canEdit={canEdit} />
      <RadarKeywordFilter keywords={keywords} active={activeKeywords} onToggle={toggleKeyword} canEdit={canEdit} />

      <h2 className={styles.sectionTitle}>🔥 Hot ({hotRows.length})</h2>
      <SortableTable
        columns={RADAR_TABLE_COLUMNS}
        rows={visibleHot}
        defaultSort={{ key: 'heat', dir: 'desc' }}
        searchPlaceholder="Filter by company or series…"
        emptyMessage="Nothing hot right now."
      />

      <h2 className={styles.sectionTitle}>Cold ({coldRows.length})</h2>
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
