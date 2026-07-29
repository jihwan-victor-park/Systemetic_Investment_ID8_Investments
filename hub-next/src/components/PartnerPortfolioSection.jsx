'use client';

import { Suspense, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import PortfolioTable from './PortfolioTable';
import PortfolioGraph from './PortfolioGraph';
import { isThesisInScope, isFitScoreInScope } from '@/lib/sectorRelevance';
import styles from './PartnerPortfolioSection.module.css';

// Portfolio tile on a Partner VC's page -- List (the same sortable/
// searchable table every other deal list in the hub uses, and the source
// of truth for this data) and Graph (read-only network view; fit scores
// are cross-referenced live from ID8's own companies/screens in
// PortfolioGraph, never typed in here). Editing only ever happens in List
// view.
//
// Two independent scope toggles, OFF by default (i.e. showing the filtered,
// in-thesis + track-worthy view) -- per Oscar's "biotech shouldn't be here"
// ask, a portfolio is assumed to contain off-thesis companies until proven
// otherwise, and a sub-3.0 fit score is the same "not worth tracking" bar the
// deal lists use. They're kept separate rather than one combined "show all"
// switch because they answer different questions (is this even in our market
// vs. is this a strong company in our market) -- collapsing them hid the
// reason a specific company was missing. Both default ON instead when
// arriving via the qualified/radar pipeline link (see
// PartnerPortfolioSectionInner's own comment) -- that's the one case where
// hiding by default works against the reason the visit happened.
// isThesisInScope/isFitScoreInScope (sectorRelevance.js): the former layers
// this file's own keyword check on top of the real prefilterPass verdict
// deal_intelligence/portfolio_prefilter.py stamps onto each company
// (geography, business status, AI-relevance) -- funds over 500 companies
// haven't been run through that yet, so they fall back to the keyword check
// alone until they are. Graph gets a plain pre-filtered array (read-only,
// nothing to persist); List gets the full unfiltered array plus a filterFn,
// since PortfolioTable's add/remove needs the true underlying array to
// persist correctly (see PortfolioTable.jsx).
function PartnerPortfolioSectionInner({ vcId, vcName, portfolio, companyIndex, canEdit }) {
  // Arriving via the VCs directory's "N qualified/radar →" link
  // (?pipeline=qualified,radar, see VCsDirectory.jsx's PipelineCell) means
  // these specific companies are already known-relevant -- the off-thesis/
  // low-fit scope toggles below exist to hide noise in the OTHER 99% of a
  // portfolio ID8 hasn't screened, and shouldn't also hide the very
  // companies that link was built to surface. Bypass both by default in
  // that case; a plain visit to the Portfolio tab keeps the original
  // hide-by-default behavior.
  const searchParams = useSearchParams();
  const arrivedViaPipelineLink = Boolean(searchParams.get('pipeline'));
  const [view, setView] = useState('list');
  const [showOffThesis, setShowOffThesis] = useState(arrivedViaPipelineLink);
  const [showLowFit, setShowLowFit] = useState(arrivedViaPipelineLink);

  const filterFn = useMemo(
    () => (entry) => (showOffThesis || isThesisInScope(entry)) && (showLowFit || isFitScoreInScope(entry)),
    [showOffThesis, showLowFit]
  );

  // Each toggle's hidden count is independent of the OTHER toggle's current
  // state -- it always answers "how many would flipping just this switch
  // reveal", not "how many are hidden right now for this reason and no other".
  const { visiblePortfolio, offThesisHiddenCount, lowFitHiddenCount } = useMemo(() => ({
    visiblePortfolio: portfolio.filter(filterFn),
    offThesisHiddenCount: portfolio.filter((p) => !isThesisInScope(p)).length,
    lowFitHiddenCount: portfolio.filter((p) => !isFitScoreInScope(p)).length,
  }), [portfolio, filterFn]);

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
        <input type="checkbox" checked={showOffThesis} onChange={(e) => setShowOffThesis(e.target.checked)} />
        Show off-thesis / wrong-geography / inactive companies
        {!showOffThesis && offThesisHiddenCount > 0 && (
          <span className={styles.scopeHint}>({offThesisHiddenCount} hidden)</span>
        )}
      </label>
      <label className={styles.scopeToggle}>
        <input type="checkbox" checked={showLowFit} onChange={(e) => setShowLowFit(e.target.checked)} />
        Show fit score under 3.0
        {!showLowFit && lowFitHiddenCount > 0 && (
          <span className={styles.scopeHint}>({lowFitHiddenCount} hidden)</span>
        )}
      </label>

      {view === 'list' ? (
        // PortfolioTable reads ?pipeline=qualified,radar via useSearchParams
        // (the VCs directory's pre-filtered link) -- same Suspense-boundary
        // convention signin/page.jsx already uses for that hook.
        <Suspense fallback={null}>
          <PortfolioTable
            endpoint="/api/partner-vcs"
            id={vcId}
            field="portfolio"
            items={portfolio}
            filterFn={filterFn}
            companyIndex={companyIndex}
            canEdit={canEdit}
            addLabel="Add company"
            vcName={vcName}
          />
        </Suspense>
      ) : (
        <PortfolioGraph vcName={vcName} portfolio={visiblePortfolio} companyIndex={companyIndex} />
      )}
    </div>
  );
}

export default function PartnerPortfolioSection(props) {
  return (
    <Suspense fallback={null}>
      <PartnerPortfolioSectionInner {...props} />
    </Suspense>
  );
}
