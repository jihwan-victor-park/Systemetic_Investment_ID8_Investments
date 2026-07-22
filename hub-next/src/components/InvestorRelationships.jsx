import Link from 'next/link';
import { H2 } from '@/components/Prose';

function statusBadge(status) {
  if (status === 'co') return <span className="badge badge--co">Co-invested</span>;
  if (status === 'pipe') return <span className="badge badge--pipe">In pipeline</span>;
  return '—';
}

// Shared by the VC-portfolio drill-in page (docs/vcs/company/[slug]) and
// CompanyDetailPage -- renders which Tier 1 / partner VCs hold this company,
// regardless of whether ID8 has also screened it. Matches come from
// companyIndex.js's findInvestorMatches.
export default function InvestorRelationships({ tier1Matches, partnerMatches }) {
  if (tier1Matches.length === 0 && partnerMatches.length === 0) return null;

  return (
    <>
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
