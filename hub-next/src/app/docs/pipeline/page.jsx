import { auth } from '@/auth';
import DealsListSection from '@/components/DealsListSection';
import { listCompanies } from '@/lib/companies';

export const metadata = { title: 'Pipeline', description: 'Companies ID8 is actively working right now.' };

export const dynamic = 'force-dynamic';

export default async function PipelinePage() {
  const [companies, session] = await Promise.all([listCompanies(), auth()]);
  const canEdit = session?.user?.role === 'internal';
  const pipeline = companies.filter((c) => c.stage === 'pipeline');

  return (
    <>
      <h1>Pipeline</h1>
      <p>Companies ID8 is actively working right now. Move one to Qualified Deals once it clears the Stage 1 rubric, or back to Watchlist if it cools off.</p>
      <DealsListSection
        companies={pipeline}
        basePath="/docs/pipeline"
        canEdit={canEdit}
        defaultSort={{ key: 'company', dir: 'asc' }}
        searchPlaceholder="Filter by company or stage…"
        emptyMessage="Nothing in the pipeline yet."
      />
    </>
  );
}
