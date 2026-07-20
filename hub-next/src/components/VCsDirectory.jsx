'use client';

import { useState } from 'react';
import Link from 'next/link';
import SortableTable from './SortableTable';
import styles from './VCsDirectory.module.css';

function statusBadge(status) {
  if (status === 'co') return <span className="badge badge--co">Co-invested</span>;
  if (status === 'pipe') return <span className="badge badge--pipe">In pipeline</span>;
  return null;
}

const PARTNER_COLUMNS = [
  { key: 'name', label: 'VC', sortable: true },
  { key: 'trackedBy', label: 'Tracked by', sortable: true },
  { key: 'portfolio', label: 'Portfolio', sortable: true },
];

const TIER1_COLUMNS = [
  { key: 'name', label: 'VC', sortable: true },
  { key: 'sector', label: 'Sector focus', sortable: true },
  { key: 'portfolio', label: 'Portfolio', sortable: true },
];

const INVESTMENT_COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'deal', label: 'Deal', sortable: true },
  { key: 'firm', label: 'Tier 1 VC', sortable: true },
  { key: 'status', label: 'Status' },
];

function partnerToRow(v) {
  const count = (v.portfolio || []).length;
  return {
    key: v.id,
    sort: { name: v.name.toLowerCase(), trackedBy: v.trackedBy || '', portfolio: count },
    search: { name: v.name, trackedBy: v.trackedBy || '' },
    cells: {
      name: <Link href={`/docs/vcs/partner/${v.id}`}>{v.name}</Link>,
      trackedBy: v.trackedBy || '—',
      portfolio: count > 0 ? `${count} ${count === 1 ? 'company' : 'companies'}` : 'No data yet',
    },
  };
}

function tier1ToRow(v) {
  const count = v.totalInvestments ?? (v.deals || []).length;
  return {
    key: v.id,
    sort: { name: v.name.toLowerCase(), sector: (v.sector || ''), portfolio: count },
    search: { name: v.name, sector: v.sector || '' },
    cells: {
      name: <Link href={`/docs/vcs/tier1/${v.id}`}>{v.name}</Link>,
      sector: v.sector || '—',
      portfolio: count > 0 ? `${count} ${count === 1 ? 'company' : 'companies'}` : 'No data yet',
    },
  };
}

function allTier1Deals(tier1) {
  const out = [];
  tier1.forEach((f) => (f.deals || []).forEach((d) => out.push({ d, firm: f })));
  return out;
}

function investmentToRow({ d, firm }, i) {
  return {
    key: `${firm.id}-${i}`,
    sort: { company: d.company.toLowerCase(), deal: d.date || '', firm: firm.name.toLowerCase() },
    search: { company: d.company, firm: firm.name },
    cells: {
      company: <Link href={`/docs/vcs/company/${encodeURIComponent(d.company)}`}>{d.company}</Link>,
      deal: [d.type, d.date].filter(Boolean).join(' · ') || '—',
      firm: <Link href={`/docs/vcs/tier1/${firm.id}`}>{firm.name}</Link>,
      status: <>{statusBadge(d.status)}{d.hot && <span className="badge badge--hot">Hot</span>}</>,
    },
  };
}

// Directory for the merged VCs tab -- Partner VCs (each partner's own
// contact, not Attio-synced yet) and Tier 1 VCs (the curated list) side by
// side under "By VC", plus a "By Investment" view that flattens every Tier 1
// firm's portfolio into one searchable company list. tier1/partners arrive
// pre-shaped, plain, RSC-serializable data from the Server Component page.
export default function VCsDirectory({ tier1, partners }) {
  const [subtab, setSubtab] = useState('byvc');

  const partnerRows = partners.map(partnerToRow);
  const tier1Rows = tier1.map(tier1ToRow);
  const investmentRows = allTier1Deals(tier1).map(investmentToRow);

  return (
    <div>
      <div className={styles.subtabs}>
        <button type="button" className={subtab === 'byvc' ? styles.active : ''} onClick={() => setSubtab('byvc')}>By VC</button>
        <button type="button" className={subtab === 'byinv' ? styles.active : ''} onClick={() => setSubtab('byinv')}>By Investment</button>
      </div>

      {subtab === 'byvc' ? (
        <>
          <h2 className={styles.section}>Partner VCs</h2>
          <p className={styles.dek}>A partner&rsquo;s own contact into the firm — typed in by hand, not yet synced from Attio.</p>
          <SortableTable
            columns={PARTNER_COLUMNS}
            rows={partnerRows}
            defaultSort={{ key: 'name', dir: 'asc' }}
            searchPlaceholder="Filter partner VCs…"
            emptyMessage="No partner VCs added yet — add one from Admin."
          />

          <h2 className={styles.section}>Tier 1 VCs</h2>
          <p className={styles.dek}>The existing curated list, by tier and sector focus.</p>
          <SortableTable
            columns={TIER1_COLUMNS}
            rows={tier1Rows}
            defaultSort={{ key: 'name', dir: 'asc' }}
            searchPlaceholder="Filter Tier 1 VCs…"
            emptyMessage="No Tier 1 VCs added yet — add one from Admin."
          />
        </>
      ) : (
        <>
          <h2 className={styles.section}>By Investment</h2>
          <p className={styles.dek}>Every portfolio company recorded against a Tier 1 VC — click one to see which firms are on its cap table.</p>
          <SortableTable
            columns={INVESTMENT_COLUMNS}
            rows={investmentRows}
            defaultSort={{ key: 'deal', dir: 'desc' }}
            searchPlaceholder="Filter companies…"
            emptyMessage="No portfolio companies recorded yet."
          />
        </>
      )}
    </div>
  );
}
