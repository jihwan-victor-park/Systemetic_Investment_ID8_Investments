'use client';

import { useMemo, useState } from 'react';
import SortableTable from './SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from './companyStageColumns';
import styles from './DealsListSection.module.css';

const MIN_FIT_SCORE = 3.0;

// A deal with no score yet (not screened, or a failed run) stays visible --
// same "no data -> don't hide it" convention PartnerPortfolioSection's
// isPortfolioCompanyInScope uses for portfolio companies; only a real
// sub-3.0 score is a hide reason here.
function isInScope(c) {
  const score = c.latestScreen?.fitScore;
  return score == null || score >= MIN_FIT_SCORE;
}

// Shared by Watchlist / Pipeline / Qualified Deals -- the same "show all"
// scope toggle PartnerPortfolioSection uses for a VC's portfolio, applied
// here to hide sub-3.0 fit scores by default so the list opens on what's
// actually worth a look rather than the full unfiltered feed.
export default function DealsListSection({ companies, basePath, canEdit, tier1 = [], partners = [], defaultSort, searchPlaceholder, emptyMessage }) {
  const [showAll, setShowAll] = useState(false);

  const { visible, hiddenCount } = useMemo(() => {
    if (showAll) return { visible: companies, hiddenCount: 0 };
    const v = companies.filter(isInScope);
    return { visible: v, hiddenCount: companies.length - v.length };
  }, [companies, showAll]);

  const rows = useMemo(
    () => visible.map((c) => companyToRow(c, { basePath, canEdit, tier1, partners })),
    [visible, basePath, canEdit, tier1, partners],
  );

  return (
    <>
      <label className={styles.scopeToggle}>
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
        Show all deals
        {!showAll && hiddenCount > 0 && (
          <span className={styles.scopeHint}>({hiddenCount} hidden — fit score under 3.0)</span>
        )}
      </label>
      <SortableTable
        columns={STAGE_TABLE_COLUMNS}
        rows={rows}
        defaultSort={defaultSort}
        searchPlaceholder={searchPlaceholder}
        emptyMessage={emptyMessage}
      />
    </>
  );
}
