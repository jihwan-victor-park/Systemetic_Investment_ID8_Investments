'use client';

import { useMemo, useState } from 'react';
import SortableTable from './SortableTable';
import { STAGE_TABLE_COLUMNS, companyToRow } from './companyStageColumns';
import styles from './DealsListSection.module.css';

// Shared by Watchlist / Pipeline / Qualified Deals.
//
// `hidePassed` (Oscar, 2026-08-05: "on the pipeline view there should be a
// button... so that it's automatically switched off, not showing the
// [passed]... deals"; 2026-08-06: "just keep the checkbox/toggle of the
// passed deals" -- the fit-score "Show all deals" toggle this used to pair
// with is gone, Passed is the only scope toggle left) -- opt-in per caller
// (only pipeline/page.jsx passes it true today) rather than applied to
// every stage page unasked. Every company tagged 'passed' also carries the
// 'pipeline' tag (deal_intelligence/import_attio_deals_csv.py, 2026-08-06:
// "make sure the lists of the passed deals are all tagged as both pipeline
// and passed") -- so Pipeline is where a Passed company is guaranteed to
// surface regardless of whatever else it's tagged, which is why this toggle
// only needs to live here, not on every stage page. 'passed' is an
// ADDITIVE tag (see lib/stages.js's TAGS comment) -- a company can carry
// both its real working stage AND this tag at once (the "double tag"
// case), so a stage page's own server-side filter can't exclude it
// upstream without also losing it from the Passed tab itself.
export default function DealsListSection({ companies, basePath, canEdit, investorIndex = {}, domainIndex = {}, defaultSort, searchPlaceholder, emptyMessage, hidePassed = false }) {
  const [showPassed, setShowPassed] = useState(false);

  const { visible, passedHiddenCount } = useMemo(() => {
    const v = hidePassed && !showPassed
      ? companies.filter((c) => !c.tags?.includes('passed'))
      : companies;
    return { visible: v, passedHiddenCount: companies.length - v.length };
  }, [companies, showPassed, hidePassed]);

  const rows = useMemo(
    () => visible.map((c) => companyToRow(c, { basePath, canEdit, investorIndex, domainIndex })),
    [visible, basePath, canEdit, investorIndex, domainIndex],
  );

  const hasAnyPassed = useMemo(
    () => hidePassed && companies.some((c) => c.tags?.includes('passed')),
    [companies, hidePassed],
  );

  return (
    <>
      {hasAnyPassed && (
        <label className={styles.scopeToggle}>
          <input type="checkbox" checked={showPassed} onChange={(e) => setShowPassed(e.target.checked)} />
          Show passed deals
          {!showPassed && passedHiddenCount > 0 && (
            <span className={styles.scopeHint}>({passedHiddenCount} hidden — tagged Passed)</span>
          )}
        </label>
      )}
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
