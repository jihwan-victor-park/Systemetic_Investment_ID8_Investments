const { Paragraph, TextRun, BorderStyle } = require("docx");
const L = require("./lib");
const { C, HEAD, BODY, contents, chapter, h2, p, run, bold, note, table, check, closing, build } = L;

const titleBlock = [
  new Paragraph({ spacing: { after: 40 }, children: [
    new TextRun({ text: "Workflows & Platforms", font: HEAD, size: 44, bold: true, color: C.CHARCOAL })] }),
  new Paragraph({ spacing: { after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.CHARCOAL, space: 10 } },
    children: [new TextRun({ text: "Cloud migration — scope, requirements, sequence, and cost", font: BODY, size: 22, italics: true, color: C.GREY })] }),
];

const children = [
  ...titleBlock,

  chapter(1, "Current state and migration scope"),
  p("The pipeline (PitchBook, Watchlist, and Top 10 VC processing, Jesse's Deal intake) and Apollo Reach Out (list filtering, Perplexity enrichment, sequence loading) currently execute against a locally-run n8n instance and local Python processes. Execution depends on a single machine being on and the process being manually started; there is no automatic recovery and no execution history outside that machine."),
  p("Migrating to Google Cloud Run replaces that with two containerized services under ID8's own GCP project: continuous, IAM-scoped execution, automatic restart on failure, and a persisted, auditable run history. No application logic changes — the existing workflows and scripts move as-is."),

  chapter(2, "Platforms required"),
  table(["Platform", "Function"], [
    ["Google Cloud Run", "Container hosting for both services — the orchestration engine and the data-pipeline API"],
    ["n8n (self-hosted)", "Workflow orchestration engine — triggers, scheduling, and the visual workflow canvas"],
    ["Cloud SQL for PostgreSQL", "Persistence layer for n8n's configuration, credentials, and execution history — and the shared store for chatbot logs, research output, and skill run history as those land"],
    ["Secret Manager", "Stores API keys and the n8n encryption key outside the container image"],
    ["Artifact Registry", "Stores the Docker images built for each deploy"],
    ["Perplexity API", "LLM research used for Apollo enrichment and Deal Intelligence Stage 1/2"],
    ["Anthropic API", "LLM scoring and memo synthesis for Deal Intelligence"],
  ], [2800, 6560]),
  note("Cloud SQL replaces Neon (a third-party Postgres host) with a Postgres instance inside ID8's own GCP project. n8n keeps its existing schema; new tables/schemas for chatbot logs, research output, and skill run history live in the same instance, so there is one database to back up, secure, and query instead of one per system."),

  chapter(3, "Access and setup requirements"),
  p("Before deployment can begin, the following need to be granted or configured. Items marked Oscar require no action from the account owner."),
  table(["#", "Requirement", "Owner"], [
    ["1", "GCP project created, billing account linked", "Account owner"],
    ["2", "IAM role grant on the project — run.admin, artifactregistry.admin, secretmanager.admin, cloudbuild.builds.editor, iam.serviceAccountUser, logging.viewer (or Owner, as a single grant covering all of the above)", "Account owner → Oscar"],
    ["3", "OAuth consent screen — Internal, scoped to the id8investments.com Workspace domain, for Drive/Sheets/Gmail access", "Account owner"],
    ["4", "OAuth redirect URI registered once the Cloud Run URL is issued (one-time, post-first-deploy)", "Account owner"],
    ["5", "Cloud SQL Admin API enabled, db-f1-micro instance provisioned in the GCP project — billed, no separate vendor account", "Oscar"],
    ["6", "Existing API credentials confirmed current — Attio, Apollo (master key), Perplexity, Anthropic", "Oscar"],
  ], [500, 6360, 2500]),

  chapter(4, "Migration sequence"),
  table(["Phase", "Scope", "Owner", "Duration"], [
    ["1", "GCP project setup, IAM grant, OAuth consent screen", "Account owner", "~30 min"],
    ["2", "Deploy n8n to Cloud Run, provision the Cloud SQL instance, import existing workflows", "Oscar", "1–2 hrs"],
    ["3", "Deploy the data-pipeline service, re-issue OAuth credentials", "Oscar", "1 hr"],
    ["4", "Build the planned intelligence workflows (Chapter 5)", "Oscar", "2–3 hrs"],
    ["5", "End-to-end test, cut over from the local instance", "Oscar", "1 hr"],
  ], [900, 5260, 2000, 1200]),
  note("Total: 1–2 days to full cloud operation once GCP access is granted. Phases 2–3 cover migration of what already runs locally; Phase 4 is net-new build."),

  chapter(5, "Planned workflows — next build phase"),
  p("Each of the following executes on the infrastructure provisioned in Phases 2–3. None require additional compute provisioning; incremental cost is AI API usage only."),
  table(["Workflow", "Function", "Status"], [
    ["Deal Intelligence", "Two-stage AI scoring and deep-research memo generation on every qualified deal", "In build"],
    ["Daily Deal Digest", "Scans 15+ financial news sources, filters by sector/stage, emails a summary", "Planned"],
    ["Portfolio Monitoring", "Tracks news mentions of portfolio/watchlist companies, logs to Attio", "Planned"],
    ["LP Intelligence", "Weekly SEC 13F filing scan, flags activity from target family offices/RIAs", "Planned"],
    ["Competitive VC Radar", "Weekly summary of what lead VCs in the network are backing", "Planned"],
  ], [2400, 5560, 1400]),

  chapter(6, "Cost structure"),
  table(["Category", "Item", "$/month"], [
    ["Compute", "n8n — Cloud Run, 1 vCPU / 1Gi, min-instances=1", "~$9"],
    ["Compute", "Data-pipeline service — Cloud Run, 1 vCPU / 512Mi, scale-to-zero", "~$1"],
    ["Storage / DB", "Cloud SQL for PostgreSQL — db-f1-micro (shared-core, 0.6GB), 10–20GB SSD + backups", "~$11–13"],
    ["Storage / DB", "Artifact Registry + Secret Manager", "~$0.20"],
    ["", "Subtotal — infrastructure to get current workflows running", "~$21–23"],
    ["AI usage", "Perplexity API — research and enrichment", "~$2–3"],
    ["AI usage", "Anthropic API — Deal Intelligence scoring and synthesis", "Usage-based, ~$2 at current deal volume"],
    ["", "Subtotal — to add the planned workflows (Chapter 5)", "+$2–5"],
    ["", "Total", "~$23–28"],
  ], [1600, 5760, 2000]),
  note("Cloud SQL has no free tier — this is a real increase over Neon's ~$0/mo, traded for keeping all fund data (automation config, chatbot logs, research, skill history) inside ID8's own GCP project rather than split across a third-party host. db-f1-micro is shared-core and not SLA-covered; if logged volume grows past what it can hold, the next tier (db-g1-small, 1.7GB) runs ~$26/mo and is a config change, not a migration."),
  note("Reference comparator: a single Zapier Business seat is $69/mo; Make or n8n Cloud run $50–300/mo. None include an AI scoring layer or a database to build further tooling on — those would be separate, additional costs on top of their base price."),

  ...closing(),
];

build(__dirname + "/../docs/ID8_Workflows_and_Platforms_Onepager.docx", "Workflows & Platforms", children)
  .then(() => console.log("Workflows & Platforms brief (v2) written."));
