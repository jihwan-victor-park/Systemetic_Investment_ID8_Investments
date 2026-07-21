import { redirect, notFound } from 'next/navigation';
import { getCompany } from '@/lib/companies';
import { STAGE_BASEPATH } from '@/lib/stages';

// Top 10 VC Deals is a cross-cutting view, not a real stage (a company here
// is still actually filed under Watchlist/Pipeline/Qualified/New) -- so
// unlike the other stage routes, this one doesn't render its own detail
// page. It redirects to wherever the company really lives, which is where
// its screen history / edit controls actually are.
export const dynamic = 'force-dynamic';

export default async function Top10VcDealRedirect({ params }) {
  const { slug } = await params;
  const company = await getCompany(slug);
  if (!company) notFound();
  const basePath = STAGE_BASEPATH[company.stage] || STAGE_BASEPATH.qualified;
  redirect(`${basePath}/${slug}`);
}
