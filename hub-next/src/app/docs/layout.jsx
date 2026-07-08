import DocsShell from '@/components/DocsShell';
import { listCompanySlugsForSidebar } from '@/lib/companies';

// Every /docs/* route shares this layout's sidebar, which lists companies
// from Firestore — force the whole section dynamic so a newly-added company
// shows up in the sidebar immediately, not just on pages that already opt
// into dynamic rendering for their own data.
export const dynamic = 'force-dynamic';

export default async function DocsLayout({ children }) {
  const companies = await listCompanySlugsForSidebar();
  return <DocsShell companies={companies}>{children}</DocsShell>;
}
