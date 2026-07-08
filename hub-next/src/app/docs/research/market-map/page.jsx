import { H2 } from '@/components/Prose';
import MarketMap from '@/components/MarketMap';
import { listMarketMapEntries } from '@/lib/marketMap';

export const metadata = { title: 'Market Map Directory', description: 'A directory of external VC/research market maps.' };

export const dynamic = 'force-dynamic';

export default async function MarketMapPage() {
  const entries = await listMarketMapEntries();
  return (
    <>
      <h1>Market Map Directory</h1>
      <p>
        A curated directory of external VC and research market maps — browsable by category or by firm, with a
        freshness read on each one so it&apos;s obvious what&apos;s current versus dated.
      </p>
      <MarketMap initialEntries={entries} />

      <H2>Status</H2>
      <p>
        Live and backed by Firestore — entries added through &quot;+ Add new&quot; save straight to the shared
        directory. See the <a href="/research/market-map-original.html">original, unstyled source</a> for comparison.
      </p>
    </>
  );
}
