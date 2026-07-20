import Link from 'next/link';
import { notFound } from 'next/navigation';
import { H2 } from '@/components/Prose';
import { listTopVCs } from '@/lib/topVCs';
import { listPartnerVCs } from '@/lib/partnerVCs';

export const dynamic = 'force-dynamic';

export async function generateMetadata({ params }) {
  const { slug } = await params;
  return { title: decodeURIComponent(slug) };
}

function statusBadge(status) {
  if (status === 'co') return <span className="badge badge--co">Co-invested</span>;
  if (status === 'pipe') return <span className="badge badge--pipe">In pipeline</span>;
  return '—';
}

// By-Investment drill-in -- not a company ID8 has screened itself, just
// somewhere in a VC's recorded portfolio (Tier 1's deals[] or a partner's
// portfolio[]). `slug` is an encodeURIComponent'd company name, matched
// case-insensitively against both -- no separate collection needed.
export default async function VCPortfolioCompanyPage({ params }) {
  const { slug } = await params;
  const companyName = decodeURIComponent(slug);
  const nameLc = companyName.toLowerCase();
  const [tier1, partners] = await Promise.all([listTopVCs(), listPartnerVCs()]);

  const tier1Matches = [];
  tier1.forEach((firm) => {
    (firm.deals || []).forEach((d) => {
      if (d.company.toLowerCase() === nameLc) tier1Matches.push({ d, firm });
    });
  });

  const partnerMatches = [];
  partners.forEach((p) => {
    (p.portfolio || []).forEach((entry) => {
      if (entry.company.toLowerCase() === nameLc) partnerMatches.push({ entry, firm: p });
    });
  });

  if (tier1Matches.length === 0 && partnerMatches.length === 0) notFound();

  const rep = tier1Matches[0]?.d;
  const repEntry = partnerMatches[0]?.entry;
  const repIndustry = rep?.industry || repEntry?.industry;
  const repCategory = repEntry?.category;
  const repDescription = repEntry?.description;

  return (
    <>
      <p><Link href="/docs/vcs">← VCs</Link></p>
      <h1>{companyName}</h1>
      <p>
        {[repIndustry, repCategory, rep && rep.type && rep.date ? `last deal ${rep.type}, ${rep.date}${rep.size ? ` (${rep.size})` : ''}` : null]
          .filter(Boolean).join(' · ') || 'No deal detail recorded.'}
      </p>
      {repDescription && <p>{repDescription}</p>}

      {tier1Matches.length > 0 && (
        <>
          <H2>Tier 1 VCs on cap table</H2>
          <ul>
            {tier1Matches.map(({ firm }) => (
              <li key={firm.id}><Link href={`/docs/vcs/tier1/${firm.id}`}>{firm.name}</Link></li>
            ))}
          </ul>

          <H2>Deals recorded</H2>
          <table>
            <thead><tr><th>Tier 1 VC</th><th>Deal date</th><th>Type</th><th>Size</th><th>Status</th></tr></thead>
            <tbody>
              {tier1Matches.map(({ d, firm }, i) => (
                <tr key={i}>
                  <td><Link href={`/docs/vcs/tier1/${firm.id}`}>{firm.name}</Link></td>
                  <td>{d.date || '—'}</td>
                  <td>{d.type || '—'}</td>
                  <td>{d.size || '—'}</td>
                  <td>{statusBadge(d.status)}{d.hot && <span className="badge badge--hot" style={{ marginLeft: 4 }}>Hot</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {partnerMatches.length > 0 && (
        <>
          <H2>Partner relationships</H2>
          <table>
            <thead><tr><th>VC</th><th>Tracked by</th><th>Series</th></tr></thead>
            <tbody>
              {partnerMatches.map(({ entry, firm }, i) => (
                <tr key={i}>
                  <td><Link href={`/docs/vcs/partner/${firm.id}`}>{firm.name}</Link></td>
                  <td>{firm.trackedBy || '—'}</td>
                  <td>{entry.series || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
