import { auth } from '@/auth';
import DealsListSection from '@/components/DealsListSection';
import { listCompanies } from '@/lib/companies';

export const metadata = { title: 'Watchlist', description: 'Companies ID8 is keeping an eye on but isn\'t actively working yet.' };

export const dynamic = 'force-dynamic';

export default async function WatchlistPage() {
  const [companies, session] = await Promise.all([listCompanies(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const watchlist = companies.filter((c) => c.stage === 'watchlist');

  return (
    <>
      <h1>Watchlist</h1>
      <p>Companies ID8 is keeping an eye on but isn't actively working yet. Move one to Pipeline or Qualified Deals with the Stage dropdown once it's worth picking up.</p>
      <DealsListSection
        companies={watchlist}
        basePath="/docs/watchlist"
        canEdit={canEdit}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or stage…"
        emptyMessage="Nothing on the watchlist yet."
      />
    </>
  );
}
