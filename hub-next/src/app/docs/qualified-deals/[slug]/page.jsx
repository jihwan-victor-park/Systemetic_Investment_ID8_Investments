import { notFound } from 'next/navigation';
import { auth } from '@/auth';
import { getCompany } from '@/lib/companies';
import ScreenView from '@/components/ScreenView';

export const dynamic = 'force-dynamic';

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const company = await getCompany(slug);
  if (!company) return {};
  return { title: company.name, description: `Deal screens for ${company.name}` };
}

export default async function CompanyScreenPage({ params }) {
  const { slug } = await params;
  const [company, session] = await Promise.all([getCompany(slug), auth()]);
  if (!company) notFound();
  // Editing (subcategory scores/findings, dimension evidence, deal rationale)
  // is internal-only -- same role check as /api/top-vcs. This page is
  // already internal-only end to end (investors are redirected to
  // /investors/research before reaching /docs/qualified-deals), so this only
  // gates whether the edit controls render, not whether the page loads.
  const canEdit = session?.user?.role === 'internal';

  return (
    <>
      <h1>{company.name}</h1>
      <p>
        <a href={`https://${company.website}`} target="_blank" rel="noopener noreferrer">{company.website}</a>
        {' · '}
        <a href={company.screens[0]?.docxPath || `/research/companies/${company.slug}.docx`}>Download latest screen (Word) →</a>
      </p>
      {company.screens.map((screen) => (
        <ScreenView key={screen.id} screen={screen} canEdit={canEdit} slug={company.slug} />
      ))}
    </>
  );
}
