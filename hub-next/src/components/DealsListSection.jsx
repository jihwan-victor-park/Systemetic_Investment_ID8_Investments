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
//
// `hidePassed` (Oscar, 2026-08-05: "on the pipeline view there should be a
// button... so that it's automatically switched off, not showing the
// [passed]... deals") -- a SEPARATE toggle from the fit-score one above,
// same reusable pattern, opt-in per caller (only pipeline/page.jsx passes
// it true today) rather than applied to every stage page unasked.
// 'passed' is an ADDITIVE tag (see lib/stages.js's TAGS comment) -- a
// company can carry both its real working stage AND this tag at once (the
// "double tag" case), so a stage page's own server-side filter can't
// exclude it upstream without also losing it from the Passed tab itself.
export default function DealsListSection({ companies, basePath, canEdit, investorIndex = {}, domainIndex = {}, defaultSort, searchPlaceholder, emptyMessage, hidePassed = false }) {
  const [showAll, setShowAll] = useState(false);
  const [showPassed, setShowPassed] = useState(false);

  // Two independent hide-reasons, applied in sequence so each toggle's own
  // hint count reflects exactly what THAT toggle is hiding, not a combined
  // number that would misrepresent either one once both are active.
  const { visible, fitHiddenCount, passedHiddenCount } = useMemo(() => {
    const afterFitScope = showAll ? companies : companies.filter(isInScope);
    const afterPassed = hidePassed && !showPassed
      ? afterFitScope.filter((c) => !c.tags?.includes('passed'))
      : afterFitScope;
    return {
      visible: afterPassed,
      fitHiddenCount: companies.length - afterFitScope.length,
      passedHiddenCount: afterFitScope.length - afterPassed.length,
    };
  }, [companies, showAll, showPassed, hidePassed]);

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
      <label className={styles.scopeToggle}>
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
        Show all deals
        {!showAll && fitHiddenCount > 0 && (
          <span className={styles.scopeHint}>({fitHiddenCount} hidden — fit score under 3.0)</span>
        )}
      </label>
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
