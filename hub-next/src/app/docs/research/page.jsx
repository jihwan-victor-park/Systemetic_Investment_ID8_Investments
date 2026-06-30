import Link from "next/link";
import { listCompanies } from "@/lib/firestore";

export const dynamic = "force-dynamic";
export const metadata = { title: "Research" };

// Hand-curated deal research decks (static — rarely changes).
const DECKS = [
  {
    company: "Lila Sciences",
    thesis: "Autonomous AI science factories for scientific discovery. Comps and a bull, base, bear at the ~$8.5B rumored mark.",
    stage: "Series B rumored, Jun 2026, Cambridge MA",
    href: "/research/Lila_Sciences_Deal_Summary_draft.pptx",
  },
  {
    company: "Gimlet Labs",
    thesis: "Multi-silicon inference cloud for agentic AI. Comps and scenario valuations on the $208M Series A post.",
    stage: "Series A closed, Mar 2026, San Francisco",
    href: "/research/Gimlet_Labs_Deal_Draft.pptx",
  },
];

export default async function ResearchPage() {
  let companies = [];
  let error = null;
  try {
    companies = await listCompanies();
  } catch (e) {
    error = e.message;
  }

  return (
    <main className="container" style={{ paddingTop: "2.5rem", paddingBottom: "2rem" }}>
      <div className="prose">
        <div className="kicker">Research</div>
        <h1>Research</h1>
        <p>Deal research and the knowledge base behind the systems. Each entry links to the source.</p>

        <h2>Deal screens</h2>
        <p>
          Stage 1 fit screens produced by{" "}
          <Link href="/docs/projects/intelligence">Deal Intelligence</Link> — one page per
          company, scored against the ID8 rubric with a dated screen history. Updates live.
        </p>

        {error ? (
          <p style={{ color: "var(--id8-grey)" }}>Screens unavailable ({error}).</p>
        ) : (
          <table className="htable">
            <thead>
              <tr><th>Company</th><th>Latest screen</th><th>Fit</th><th>Report</th></tr>
            </thead>
            <tbody>
              {companies.length === 0 && (
                <tr><td colSpan={4} style={{ color: "var(--id8-grey)" }}>No screens yet.</td></tr>
              )}
              {companies.map((c) => (
                <tr key={c.slug}>
                  <td>{c.name}</td>
                  <td>{c.latest_screen_date}{c.latest_round ? ` · ${c.latest_round}` : ""}</td>
                  <td>
                    {c.latest_fit_score != null ? Number(c.latest_fit_score).toFixed(1) : "—"}
                    {c.latest_gate ? " ✓" : ""}
                  </td>
                  <td><Link href={`/docs/research/companies/${c.slug}`}>View screen →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <h2>Deal research</h2>
        <table className="htable">
          <thead>
            <tr><th>Company</th><th>Thesis</th><th>Stage</th><th>Deck</th></tr>
          </thead>
          <tbody>
            {DECKS.map((d) => (
              <tr key={d.company}>
                <td>{d.company}</td>
                <td>{d.thesis}</td>
                <td>{d.stage}</td>
                <td><a href={d.href}>PPTX →</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
