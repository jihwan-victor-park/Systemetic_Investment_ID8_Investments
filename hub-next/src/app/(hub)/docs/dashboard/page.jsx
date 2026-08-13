import DealStatsDashboard from '@/components/DealStatsDashboard';
import { listCompanies } from '@/lib/companies';

export const metadata = { title: 'Dashboard', description: 'Live summary statistics across the whole deal universe.' };

// force-dynamic, like every other /docs route -- the whole point of this page is
// that the numbers are current. listCompanies() still caches for 60s
// (CACHE_SECONDS in lib/companies.js) and revalidates immediately on any edit,
// so this is cheap without being stale.
export const dynamic = 'force-dynamic';

// Its own route rather than folded back into /docs/overview: that page is the
// AI Capabilities write-up and stayed that way after the 2026-08-06 dashboard
// experiment was removed. The sidebar's "Dashboard" entry and the navbar pill
// both point here now; AI Capabilities keeps its own entry.
export default async function DashboardPage() {
  const companies = await listCompanies();
  return <DealStatsDashboard companies={companies} />;
}
