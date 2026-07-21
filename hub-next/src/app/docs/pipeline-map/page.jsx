import { listCompanies } from '@/lib/companies';
import { STAGES } from '@/lib/stages';
import StageCategoryGraph from '@/components/StageCategoryGraph';

export const metadata = {
  title: 'Pipeline Map',
  description: 'Where every tracked company sits by stage and Radar Category.',
};

export const dynamic = 'force-dynamic';

// Stage -> Radar Category flow across the whole pipeline, not just one
// stage table -- a company without a radarCategory yet (the vast majority
// until the Attio backfill lands) is grouped under "Uncategorized" rather
// than dropped, so the graph is honest about how little is categorized so
// far instead of just looking sparse for no visible reason.
export default async function PipelineMapPage() {
  const companies = await listCompanies();
  const categories = [...new Set(companies.map((c) => c.radarCategory || 'Uncategorized'))].sort((a, b) => {
    if (a === 'Uncategorized') return 1;
    if (b === 'Uncategorized') return -1;
    return a.localeCompare(b);
  });

  const flows = [];
  for (const s of STAGES) {
    for (const cat of categories) {
      const count = companies.filter((c) => c.stage === s && (c.radarCategory || 'Uncategorized') === cat).length;
      if (count > 0) flows.push({ stage: s, category: cat, count });
    }
  }

  const uncategorizedCount = companies.filter((c) => !c.radarCategory).length;

  return (
    <>
      <h1>Pipeline Map</h1>
      <p>
        Every tracked company, grouped by its current stage on the left and its Radar Category on the right.
        {uncategorizedCount > 0 && companies.length > 0 && (
          ` ${uncategorizedCount} of ${companies.length} companies don't have a Radar Category yet — most will land in "Uncategorized" until that field is backfilled from Attio.`
        )}
      </p>
      {flows.length === 0 ? (
        <p>No companies tracked yet.</p>
      ) : (
        <StageCategoryGraph flows={flows} stages={STAGES} categories={categories} />
      )}
    </>
  );
}
