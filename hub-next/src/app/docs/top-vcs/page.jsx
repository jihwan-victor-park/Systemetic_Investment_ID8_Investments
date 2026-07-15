import { H2 } from '@/components/Prose';
import { listTopVCs } from '@/lib/topVCs';

export const metadata = { title: 'Top 10 VCs', description: 'VCs by tier and sector focus.' };

export const dynamic = 'force-dynamic';

export default async function TopVCsPage() {
  const vcs = await listTopVCs();
  const byTier = vcs.reduce((acc, v) => {
    (acc[v.tier] = acc[v.tier] || []).push(v);
    return acc;
  }, {});
  const tiers = Object.keys(byTier).sort();

  return (
    <>
      <h1>Top 10 VCs</h1>
      <p>Curated list of VCs by tier and sector focus. Maintained from <a href="/docs/admin">Admin</a>.</p>
      {tiers.length === 0 && <p><em>No VCs added yet.</em></p>}
      {tiers.map((tier) => (
        <div key={tier}>
          <H2>{tier}</H2>
          <table>
            <thead><tr><th>Firm</th><th>Sector focus</th><th>Website</th></tr></thead>
            <tbody>
              {byTier[tier].map((v) => (
                <tr key={v.id}>
                  <td>{v.name}</td>
                  <td>{v.sector || '—'}</td>
                  <td>{v.website ? <a href={`https://${v.website}`} target="_blank" rel="noopener noreferrer">{v.website}</a> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </>
  );
}
