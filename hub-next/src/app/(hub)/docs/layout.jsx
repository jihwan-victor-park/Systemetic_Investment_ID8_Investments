import DocsShell from '@/components/DocsShell';
import { listCompanySlugsForSidebar } from '@/lib/companies';
import { listDealResearchDecks } from '@/lib/dealResearchDecks';

// Every /docs/* route shares this layout's sidebar, which lists companies and
// deal summaries from Firestore — force the whole section dynamic so a newly-
// added one shows up in the sidebar immediately, not just on pages that
// already opt into dynamic rendering for their own data.
export const dynamic = 'force-dynamic';

export default async function DocsLayout({ children }) {
  const [companies, deals] = await Promise.all([listCompanySlugsForSidebar(), listDealResearchDecks()]);
  return <DocsShell companies={companies} deals={deals}>{children}</DocsShell>;
}
