'use client';

import { useState } from 'react';
import Link from 'next/link';
import SortableTable from './SortableTable';
import { companyHref, lookupStage } from '@/lib/companyIndex';
import { STAGE_LABELS } from '@/lib/stages';
import styles from './VCsDirectory.module.css';

function statusBadge(status) {
  if (status === 'co') return <span className="badge badge--co">Co-invested</span>;
  if (status === 'pipe') return <span className="badge badge--pipe">In pipeline</span>;
  return null;
}

// How many of this firm's recorded companies are currently `qualified` or
// `radar` in ID8's own pipeline -- the subset worth linking to, not the raw
// portfolio size (Oscar: "eliminate the number of Portfolio ... a list of
// qualified/radar companies in which they have invested, not their whole
// portfolio"). `nameKey` differs between Partner VCs' `portfolio[].company`
// and Tier 1's `deals[].company`.
function qualifiedRadarCount(companyIndex, items, nameKey) {
  let n = 0;
  for (const item of items || []) {
    const stage = lookupStage(companyIndex, item[nameKey]);
    if (stage === 'qualified' || stage === 'radar') n += 1;
  }
  return n;
}

function contactNames(contacts) {
  return (contacts || []).map((c) => c.name).join(', ');
}

function ContactsCell({ contacts }) {
  if (!contacts?.length) return '—';
  return (
    <span className={styles.contactList}>
      {contacts.map((c, i) => (
        <span key={c.name}>
          {i > 0 && ', '}
          {c.email ? <a href={`mailto:${c.email}`}>{c.name}</a> : c.name}
        </span>
      ))}
    </span>
  );
}

function PipelineCell({ count, href }) {
  if (!count) return '—';
  return <Link href={href}>{count} qualified/radar →</Link>;
}

const PARTNER_COLUMNS = [
  { key: 'name', label: 'VC', sortable: true },
  { key: 'trackedBy', label: 'Tracked by', sortable: true },
  { key: 'contacts', label: 'Contacts', sortable: true },
  { key: 'pipeline', label: 'Qualified/Radar', sortable: true, defaultDir: 'desc' },
];

const TIER1_COLUMNS = [
  { key: 'name', label: 'VC', sortable: true },
  { key: 'sector', label: 'Sector focus', sortable: true },
  { key: 'contacts', label: 'Contacts', sortable: true },
  { key: 'pipeline', label: 'Qualified/Radar', sortable: true, defaultDir: 'desc' },
];

const INVESTMENT_COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'detail', label: 'Detail', sortable: true },
  { key: 'firm', label: 'VC', sortable: true },
  { key: 'type', label: 'Type', sortable: true },
  { key: 'pipeline', label: 'Pipeline', sortable: true },
];

function partnerToRow(v, companyIndex) {
  const count = qualifiedRadarCount(companyIndex, v.portfolio, 'company');
  return {
    key: v.id,
    sort: { name: v.name.toLowerCase(), trackedBy: v.trackedBy || '', contacts: contactNames(v.contacts), pipeline: count },
    search: { name: v.name, trackedBy: v.trackedBy || '', contacts: contactNames(v.contacts) },
    cells: {
      name: <Link href={`/docs/vcs/partner/${v.id}`}>{v.name}</Link>,
      trackedBy: v.trackedBy || '—',
      contacts: <ContactsCell contacts={v.contacts} />,
      pipeline: <PipelineCell count={count} href={`/docs/vcs/partner/${v.id}?pipeline=qualified,radar`} />,
    },
  };
}

function tier1ToRow(v, companyIndex) {
  const count = qualifiedRadarCount(companyIndex, v.deals, 'company');
  return {
    key: v.id,
    sort: { name: v.name.toLowerCase(), sector: (v.sector || ''), contacts: '', pipeline: count },
    search: { name: v.name, sector: v.sector || '' },
    cells: {
      name: <Link href={`/docs/vcs/tier1/${v.id}`}>{v.name}</Link>,
      sector: v.sector || '—',
      // Tier 1 VCs have no contact field on file -- unlike Partner VCs, this
      // data model never tracks a personal relationship into the firm (see
      // topVCs.js's _mapVC).
      contacts: '—',
      pipeline: <PipelineCell count={count} href={`/docs/vcs/tier1/${v.id}?pipeline=qualified,radar`} />,
    },
  };
}

// Flattens both Tier 1's deals[] and every Partner VC's portfolio[] into one
// common shape -- previously this view only showed Tier 1 deals, silently
// dropping every Partner VC portfolio company from "every investment ID8
// has a line into".
function allInvestments(tier1, partners) {
  const out = [];
  tier1.forEach((f) => (f.deals || []).forEach((d) => out.push({
    company: d.company,
    detail: [d.type, d.date].filter(Boolean).join(' · '),
    firmName: f.name,
    firmHref: `/docs/vcs/tier1/${f.id}`,
    firmType: 'Tier 1',
    status: d.status,
    hot: d.hot,
  })));
  partners.forEach((p) => (p.portfolio || []).forEach((c) => out.push({
    company: c.company,
    detail: [c.series, c.investorStatus].filter(Boolean).join(' · '),
    firmName: p.name,
    firmHref: `/docs/vcs/partner/${p.id}`,
    firmType: 'Partner',
  })));
  return out;
}

function investmentToRow(inv, i, companyIndex) {
  const href = companyHref(companyIndex, inv.company) || `/docs/vcs/company/${encodeURIComponent(inv.company)}`;
  const stage = lookupStage(companyIndex, inv.company);
  return {
    key: `${inv.firmHref}-${i}`,
    sort: { company: inv.company.toLowerCase(), detail: inv.detail || '', firm: inv.firmName.toLowerCase(), type: inv.firmType, pipeline: stage || '' },
    search: { company: inv.company, firm: inv.firmName },
    cells: {
      company: <Link href={href}>{inv.company}</Link>,
      detail: inv.detail || '—',
      firm: <Link href={inv.firmHref}>{inv.firmName}</Link>,
      type: inv.firmType,
      pipeline: stage
        ? <span className="badge">{STAGE_LABELS[stage] || stage}</span>
        : <>{statusBadge(inv.status)}{inv.hot && <span className="badge badge--hot">Hot</span>}{!inv.status && !inv.hot && '—'}</>,
    },
  };
}

// Directory for the merged VCs tab -- Partner VCs (each partner's own
// contact, not Attio-synced yet) and Tier 1 VCs (the curated list) side by
// side under "By VC", plus a "By Investment" view that flattens every Tier 1
// firm's portfolio into one searchable company list. tier1/partners arrive
// pre-shaped, plain, RSC-serializable data from the Server Component page.
export default function VCsDirectory({ tier1, partners, companyIndex }) {
  const [subtab, setSubtab] = useState('byvc');

  const partnerRows = partners.map((v) => partnerToRow(v, companyIndex));
  const tier1Rows = tier1.map((v) => tier1ToRow(v, companyIndex));
  const investmentRows = allInvestments(tier1, partners).map((inv, i) => investmentToRow(inv, i, companyIndex));

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
          <p className={styles.dek}>Every portfolio company recorded against a Tier 1 or Partner VC — click one to see which firms are on its cap table.</p>
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
