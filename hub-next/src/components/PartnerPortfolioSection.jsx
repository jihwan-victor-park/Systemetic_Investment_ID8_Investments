'use client';

import { useState } from 'react';
import Link from 'next/link';
import ArrayFieldEditor from './ArrayFieldEditor';
import PortfolioGraph from './PortfolioGraph';
import { companyHref } from '@/lib/companyIndex';
import styles from './PartnerPortfolioSection.module.css';

const PORTFOLIO_FIELDS = [
  { key: 'company', label: 'Company', required: true, placeholder: 'Company name' },
  { key: 'industry', label: 'Industry', placeholder: 'e.g. AI' },
  { key: 'series', label: 'Series', placeholder: 'e.g. Series B' },
];

// Portfolio tile on a Partner VC's page -- List (add/remove, the source of
// truth for this data) and Graph (read-only network view; fit scores are
// cross-referenced live from ID8's own companies/screens in PortfolioGraph,
// never typed in here). Editing only ever happens in List view.
export default function PartnerPortfolioSection({ vcId, vcName, portfolio, companyIndex, canEdit }) {
  const [view, setView] = useState('list');

  const displayItems = portfolio.map((p) => {
    const href = companyHref(companyIndex, p.company) || `/docs/vcs/company/${encodeURIComponent(p.company)}`;
    const meta = [p.industry, p.series].filter(Boolean).join(' · ');
    return (
      <>
        <Link href={href}>{p.company}</Link>
        {meta ? ` — ${meta}` : ''}
      </>
    );
  });

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
        <ArrayFieldEditor
          endpoint="/api/partner-vcs"
          id={vcId}
          field="portfolio"
          items={portfolio}
          displayItems={displayItems}
          fields={PORTFOLIO_FIELDS}
          canEdit={canEdit}
          addLabel="Add company"
        />
      ) : (
        <PortfolioGraph vcName={vcName} portfolio={portfolio} companyIndex={companyIndex} />
      )}
    </div>
  );
}
