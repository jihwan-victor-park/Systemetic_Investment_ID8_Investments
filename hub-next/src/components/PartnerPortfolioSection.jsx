'use client';

import { useState } from 'react';
import PortfolioTable from './PortfolioTable';
import PortfolioGraph from './PortfolioGraph';
import styles from './PartnerPortfolioSection.module.css';

// Portfolio tile on a Partner VC's page -- List (the same sortable/
// searchable table every other deal list in the hub uses, and the source
// of truth for this data) and Graph (read-only network view; fit scores
// are cross-referenced live from ID8's own companies/screens in
// PortfolioGraph, never typed in here). Editing only ever happens in List
// view.
export default function PartnerPortfolioSection({ vcId, vcName, portfolio, companyIndex, canEdit }) {
  const [view, setView] = useState('list');

  return (
    <div>
      <div className={styles.head}>
        <h2>Portfolio</h2>
        <div className={styles.subtabs}>
          <button type="button" className={view === 'list' ? styles.active : ''} onClick={() => setView('list')}>List</button>
          <button type="button" className={view === 'graph' ? styles.active : ''} onClick={() => setView('graph')}>Graph</button>
        </div>
      </div>

      {view === 'list' ? (
        <PortfolioTable
          endpoint="/api/partner-vcs"
          id={vcId}
          field="portfolio"
          items={portfolio}
          companyIndex={companyIndex}
          canEdit={canEdit}
          addLabel="Add company"
        />
      ) : (
        <PortfolioGraph vcName={vcName} portfolio={portfolio} companyIndex={companyIndex} />
      )}
    </div>
  );
}
