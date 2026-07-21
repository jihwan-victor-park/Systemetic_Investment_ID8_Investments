import 'server-only';
import { listCompanySlugsForSidebar } from './companies';
import { listTopVCs } from './topVCs';
import { listPartnerVCs } from './partnerVCs';
import { STAGE_BASEPATH } from './stages';

// Hand-maintained -- the top-level/nested tab structure barely changes and
// doesn't need a Firestore round trip to enumerate, unlike companies/VCs
// below. Keep in sync with sidebarConfig.js when tabs are added/removed.
const STATIC_ENTRIES = [
  { type: 'Tab', label: 'Capabilities', href: '/docs/overview' },
  { type: 'Tab', label: 'Deal Summaries', href: '/docs/deals' },
  { type: 'Tab', label: 'New Deals', href: '/docs/new-deals' },
  { type: 'Tab', label: 'Watchlist', href: '/docs/watchlist' },
  { type: 'Tab', label: 'Pipeline', href: '/docs/pipeline' },
  { type: 'Tab', label: 'Qualified Deals', href: '/docs/qualified-deals' },
  { type: 'Tab', label: 'Top 10 VC Deals', href: '/docs/top-10-vc-deals' },
  { type: 'Tab', label: 'Pipeline Map', href: '/docs/pipeline-map' },
  { type: 'Tab', label: 'Hot Deals', href: '/docs/hot-deals' },
  { type: 'Tab', label: 'VCs', href: '/docs/vcs' },
  { type: 'Tab', label: 'Research', href: '/docs/research' },
  { type: 'Tab', label: 'Market Map Directory', href: '/docs/research/market-map' },
  { type: 'Tab', label: 'Research Chat', href: '/docs/research-chat' },
  { type: 'Tab', label: 'Admin', href: '/docs/admin' },
];

// Everything the global search (Cmd+K) can jump straight to: static tabs,
// every tracked company (wherever its real stage page lives), and every
// tracked VC (Tier 1 and Partner). Company/VC lists are already cheap here
// (listCompanySlugsForSidebar/listTopVCs/listPartnerVCs are the same calls
// DocsShell and the VCs page already make on every /docs/* request).
export async function buildSearchIndex() {
  const [companies, tier1, partners] = await Promise.all([
    listCompanySlugsForSidebar(),
    listTopVCs(),
    listPartnerVCs(),
  ]);

  const companyEntries = companies.map((c) => ({
    type: 'Company',
    label: c.name,
    href: `${STAGE_BASEPATH[c.stage] || STAGE_BASEPATH.qualified}/${c.slug}`,
  }));
  const tier1Entries = tier1.map((v) => ({ type: 'Tier 1 VC', label: v.name, href: `/docs/vcs/tier1/${v.id}` }));
  const partnerEntries = partners.map((v) => ({ type: 'Partner VC', label: v.name, href: `/docs/vcs/partner/${v.id}` }));

  return [...STATIC_ENTRIES, ...companyEntries, ...tier1Entries, ...partnerEntries];
}
