import { notFound } from 'next/navigation';
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
  const company = await getCompany(slug);
  if (!company) notFound();

  return (
    <>
      <h1>{company.name}</h1>
      <p>
        <a href={`https://${company.website}`} target="_blank" rel="noopener noreferrer">{company.website}</a>
        {' · '}
        <a href={`/research/companies/${company.slug}.docx`}>Download latest screen (Word) →</a>
      </p>
      {company.screens.map((screen) => (
        <ScreenView key={screen.id} screen={screen} />
      ))}
    </>
  );
}
