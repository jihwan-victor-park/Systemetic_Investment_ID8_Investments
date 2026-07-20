import Link from 'next/link';
import { auth } from '@/auth';
import SortableTable from '@/components/SortableTable';
import StageSelect from '@/components/StageSelect';
import { listCompanies } from '@/lib/companies';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';
import { STAGE_BASEPATH } from '@/lib/stages';

export const metadata = { title: 'Hot Deals', description: 'Every company that cleared the Stage 1 gate this week.' };

export const dynamic = 'force-dynamic';

const WINDOW_DAYS = 7;

const COLUMNS = [
  { key: 'company', label: 'Company', sortable: true },
  { key: 'score', label: 'Score', sortable: true },
  { key: 'source', label: 'Source', sortable: true },
  { key: 'via', label: 'Via' },
  { key: 'stage', label: 'Stage', sortable: true },
  { key: 'date', label: 'Screened', sortable: true },
  { key: 'report', label: 'Report' },
];

// Best-effort case-insensitive name match against every VC's recorded
// portfolio -- Tier 1 VCs' deals[] first, then partner VCs' portfolio[],
// falling back to "Qualified screen" when nothing matches. Not a persisted
// field: recomputed on every page load from whatever's currently in topVCs/
// partnerVCs, so a portfolio added after a company gated still attributes
// correctly on the next view.
function findSource(companyName, tier1, partners) {
  const nameLc = companyName.toLowerCase();
  for (const firm of tier1) {
    if ((firm.deals || []).some((d) => d.company.toLowerCase() === nameLc)) {
      return { source: 'Tier 1 VC', via: firm.name, viaHref: `/docs/vcs/tier1/${firm.id}` };
    }
  }
  for (const p of partners) {
    if ((p.portfolio || []).some((x) => x.company.toLowerCase() === nameLc)) {
      return { source: 'Partner VC', via: p.trackedBy ? `${p.name} · ${p.trackedBy}` : p.name, viaHref: `/docs/vcs/partner/${p.id}` };
    }
  }
  return { source: 'Qualified screen', via: 'Weekly automated screen', viaHref: null };
}

export default async function HotDealsPage() {
  const [companies, tier1, partners, session] = await Promise.all([
    listCompanies(),
    listTopVCs(),
    listPartnerVCs(),
    auth(),
  ]);
  const canEdit = session?.user?.role === 'internal';

  const cutoff = Date.now() - WINDOW_DAYS * 24 * 60 * 60 * 1000;
  const gated = companies.filter((c) => {
    const s = c.latestScreen;
    if (!s || !s.gate) return false;
    const t = new Date(s.date).getTime();
    return Number.isFinite(t) && t >= cutoff;
  });

  const rows = gated.map((c) => {
    const { source, via, viaHref } = findSource(c.name, tier1, partners);
    const basePath = STAGE_BASEPATH[c.stage] || STAGE_BASEPATH.qualified;
    const score = c.latestScreen.fitScore;
    return {
      key: c.slug,
      sort: { company: c.name.toLowerCase(), score, source, stage: c.stage, date: c.latestScreen.date },
      search: { company: c.name, source, via },
      cells: {
        company: c.website ? (
          <>{c.name} (<a href={`https://${c.website}`} target="_blank" rel="noopener noreferrer">{c.website}</a>)</>
        ) : c.name,
        score: (
          <>
            <span className="badge badge--gate">Gate</span> {score != null ? `${score.toFixed(1)} / 4` : '—'}
          </>
        ),
        source,
        via: viaHref ? <Link href={viaHref}>{via}</Link> : via,
        stage: <StageSelect slug={c.slug} stage={c.stage} canEdit={canEdit} />,
        date: c.latestScreen.date.slice(0, 10),
        report: <Link href={`${basePath}/${c.slug}`}>View screen →</Link>,
      },
    };
  });

  return (
    <>
      <h1>Hot Deals</h1>
      <p>
        Every company that cleared the 3.0 Stage 1 gate in the last {WINDOW_DAYS} days — from a Tier 1 VC&rsquo;s
        portfolio, a partner&rsquo;s own contact, or the regular automated screen, whichever surfaced it first.
      </p>
      <SortableTable
        columns={COLUMNS}
        rows={rows}
        defaultSort={{ key: 'date', dir: 'desc' }}
        searchPlaceholder="Filter by company or source…"
        emptyMessage={`No companies have cleared the gate in the last ${WINDOW_DAYS} days.`}
      />
    </>
  );
}
