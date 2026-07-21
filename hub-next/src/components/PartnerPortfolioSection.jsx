'use client';

import { useMemo, useState } from 'react';
import PortfolioTable from './PortfolioTable';
import PortfolioGraph from './PortfolioGraph';
import { isSectorInScope } from '@/lib/sectorRelevance';
import styles from './PartnerPortfolioSection.module.css';

// Portfolio tile on a Partner VC's page -- List (the same sortable/
// searchable table every other deal list in the hub uses, and the source
// of truth for this data) and Graph (read-only network view; fit scores
// are cross-referenced live from ID8's own companies/screens in
// PortfolioGraph, never typed in here). Editing only ever happens in List
// view.
//
// The scope toggle defaults OFF (i.e. showing the filtered, in-thesis view)
// -- per Oscar's "biotech shouldn't be here" ask, a portfolio is assumed to
// contain off-thesis companies until proven otherwise. Graph gets a plain
// pre-filtered array (read-only, nothing to persist); List gets the full
// unfiltered array plus a filterFn, since PortfolioTable's add/remove needs
// the true underlying array to persist correctly (see PortfolioTable.jsx).
export default function PartnerPortfolioSection({ vcId, vcName, portfolio, companyIndex, canEdit }) {
  const [view, setView] = useState('list');
  const [showAll, setShowAll] = useState(false);

  const { visiblePortfolio, hiddenCount } = useMemo(() => {
    if (showAll) return { visiblePortfolio: portfolio, hiddenCount: 0 };
    const visible = portfolio.filter(isSectorInScope);
    return { visiblePortfolio: visible, hiddenCount: portfolio.length - visible.length };
  }, [portfolio, showAll]);

  return (
    <div>
      <div className={styles.head}>
        <h2>Portfolio</h2>
        <div className={styles.subtabs}>
          <button type="button" className={view === 'list' ? styles.active : ''} onClick={() => setView('list')}>List</button>
          <button type="button" className={view === 'graph' ? styles.active : ''} onClick={() => setView('graph')}>Graph</button>
        </div>
      </div>

      <label className={styles.scopeToggle}>
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
        Show all portfolio companies
        {!showAll && hiddenCount > 0 && (
          <span className={styles.scopeHint}>({hiddenCount} hidden — out of scope, e.g. biotech)</span>
        )}
      </label>

      {view === 'list' ? (
        <PortfolioTable
          endpoint="/api/partner-vcs"
          id={vcId}
          field="portfolio"
          items={portfolio}
          filterFn={showAll ? null : isSectorInScope}
          companyIndex={companyIndex}
          canEdit={canEdit}
          addLabel="Add company"
          vcName={vcName}
        />
      ) : (
        <PortfolioGraph vcName={vcName} portfolio={visiblePortfolio} companyIndex={companyIndex} />
      )}
    </div>
  );
}
