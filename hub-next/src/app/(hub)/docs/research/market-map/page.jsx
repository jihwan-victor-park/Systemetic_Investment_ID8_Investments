import { H2 } from '@/components/Prose';
import MarketMap from '@/components/MarketMap';
import { listMarketMapEntries } from '@/lib/marketMap';

export const metadata = {
  title: 'Market Map Directory',
  description: 'A browsable directory of external VC market maps and industry landscapes, organized by category and firm.',
};

export const dynamic = 'force-dynamic';

export default async function MarketMapPage() {
  const entries = await listMarketMapEntries();
  return (
    <>
      <h1>Market Map Directory</h1>
      <p>
        A directory of market maps and landscape reports published by VC firms and research shops &mdash;
        organized by category and by firm, with a freshness read on each one. Built to have one place to check
        the state of a market before a deal comes in, instead of re-checking the same handful of firms&apos;
        blogs every time.
      </p>
      <MarketMap initialEntries={entries} />

      <H2>Status</H2>
      <p>
        Backed by Firestore &mdash; entries added through &quot;+ Add new&quot; save straight to the shared
        directory instead of a hand-curated array. See the{' '}
        <a href="/research/market-map-original.html">original, unstyled directory</a> for comparison.
      </p>
    </>
  );
}
