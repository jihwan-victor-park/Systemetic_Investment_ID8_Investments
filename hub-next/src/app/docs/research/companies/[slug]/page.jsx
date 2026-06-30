import { notFound } from "next/navigation";
import Link from "next/link";
import { getCompany } from "@/lib/firestore";
import ScreenView from "@/components/ScreenView";

// Always render from live Firestore — a new screen appears the instant it's written.
export const dynamic = "force-dynamic";

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const company = await getCompany(slug);
  return { title: company ? company.name : "Company" };
}

export default async function CompanyPage({ params }) {
  const { slug } = await params;
  const company = await getCompany(slug);
  if (!company) notFound();

  const context = [company.round, company.hq, company.lead_investors].filter(Boolean);

  return (
    <main className="container" style={{ paddingTop: "2.5rem", paddingBottom: "2rem" }}>
      <div className="prose">
        <div className="kicker">Deal screen</div>
        <h1>{company.name}</h1>
        <p style={{ color: "var(--id8-grey)", marginTop: "0.2rem" }}>
          {company.domain && (
            <a href={`https://${company.domain}`} target="_blank" rel="noreferrer">{company.domain}</a>
          )}
          {context.map((b, i) => (
            <span key={i}>{(company.domain || i > 0) ? "  ·  " : ""}{b}</span>
          ))}
        </p>

        <p style={{ display: "flex", gap: "1.4rem", fontSize: "0.9rem" }}>
          {company.has_docx && (
            <a href={`/docs/research/companies/${company.slug}/download`}>
              Download latest screen (Word) →
            </a>
          )}
          <Link href="/docs/research">← All research</Link>
        </p>

        {company.screens.length === 0 && (
          <p style={{ color: "var(--id8-grey)" }}>No screens recorded yet.</p>
        )}
        {company.screens.map((s, i) => <ScreenView key={`${s.date}-${i}`} screen={s} />)}
      </div>
    </main>
  );
}
