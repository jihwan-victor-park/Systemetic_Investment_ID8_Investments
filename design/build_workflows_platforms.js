const { Paragraph, TextRun, BorderStyle } = require("docx");
const L = require("./lib");
const { C, HEAD, BODY, contents, chapter, h2, h3, p, run, bold, code,
  bullet, codeBlock, note, table, check, closing, build } = L;

const titleBlock = [
  new Paragraph({ spacing: { after: 40 }, children: [
    new TextRun({ text: "Workflows & Platforms", font: HEAD, size: 56, bold: true, color: C.CHARCOAL })] }),
  new Paragraph({ spacing: { after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.CHARCOAL, space: 10 } },
    children: [new TextRun({ text: "Technical brief — what's built, what's next, what it costs", font: BODY, size: 24, italics: true, color: C.GREY })] }),
  new Paragraph({ spacing: { after: 360 }, children: [
    new TextRun({ text: "Prepared by Oscar Varas   ·   June 2026   ·   Internal, confidential", font: BODY, size: 18, color: C.GREY })] }),
];

const children = [
  ...titleBlock,
  ...contents(),

  chapter(1, "System overview"),
  p("Three systems, each compounding the others. The pipeline is the CRM layer, Apollo Reach Out is the outbound layer, Deal Intelligence is the proprietary layer. All three run on ID8's own Google Cloud project — no SaaS vendor holds the data or the credentials."),
  ...codeBlock([
    "Google Apps Script (free, runs on Google's servers)",
    "  Drive watch (5 min) / Sheet onChange / daily cron",
    "        │ HTTP POST (webhook)",
    "        ▼",
    "n8n — Cloud Run, us-east4, min=1 max=1, 1 vCPU / 1Gi",
    "  ① PitchBook drop  ② Watchlist drop  ③ Top 10 VC drop",
    "  ④ Jesse's Deals    ⑤–⑧ intelligence workflows (roadmap)",
    "        │ HTTP POST",
    "        ▼",
    "pipeline/app.py — Cloud Run, min=0 max=3, 1 vCPU / 512Mi",
    "  Attio write layer: deals, companies, investors, LPs",
    "        │ REST API                    │",
    "        ▼                             ▼",
    "  Attio CRM                        Gmail (digests, alerts)",
  ]),
  note("Deal Intelligence runs as a separate Python package (deal_intelligence/) invoked on its own schedule, not yet wired into app.py — see Chapter 3."),

  chapter(2, "Live — PitchBook → Attio Pipeline & Apollo Reach Out"),
  h2("PitchBook → Attio Pipeline — endpoints"),
  table(["Endpoint", "Purpose"], [
    ["POST /process", "PitchBook weekly export → Attio deals + companies"],
    ["POST /process-watchlist", "Watchlist export → Attio"],
    ["POST /process-top10", "Top 10 VC export → Attio; new deals land on Radar only"],
    ["POST /process-jesse", "Jesse's Deals sheet → Attio"],
    ["POST /backfill-investors", "One-off investor-link backfill (hits the 30s gunicorn timeout on a large workspace — use the CSV import path instead)"],
    ["POST /update-investors", "Background investor-link update, paginated"],
    ["POST /fix-radar-stages", "Bulk-promotes Qualified → Radar for deals carrying new_investors_7"],
    ["POST /sync-apollo", "Mirrors Attio People into Apollo, parks them in the dormant holding sequence"],
  ], [2800, 6560]),
  h2("Investor link slugs"),
  p("Reference attributes that create the actual link on the Deal record. Different from the FIELD_MAP text slugs (lead_investors, new_investors_7, investors), which only drive display."),
  table(["Category", "Reference slug"], [
    ["Lead investors", "lead_investors_8"],
    ["New investors", "new_investors_5"],
    ["All investors, incl. follow-ons", "investors_5"],
  ], [4200, 5160]),
  h2("Write-format gotchas"),
  p("Attio's write shape differs from its read shape. Writing the read shape fails silently — no error, the field just doesn't set."),
  table(["Type", "Write format"], [
    ["select, single", 'Plain string of the option title — "slug": "Yes". Not [{"option":"Yes"}]'],
    ["multi-select", 'Array of title strings — ["A", "B"]'],
    ["currency", '[{"currency_value": 123}] — money in millions, multiply by 1,000,000'],
    ["record reference", '[{"target_object": "companies", "target_record_id": "..."}]'],
  ], [2200, 7160]),
  h2("Apollo Reach Out — scripts & config"),
  table(["Script / var", "Role"], [
    ["perplexity_lp_screener.py", "Per-firm web research and structured notes"],
    ["lp_screener_hybrid.py", "Applies the 0–100 rubric and tiers firms"],
    ["APOLLO_API_KEY", "Must be a master key — add_contact_ids returns 403 otherwise"],
    ["APOLLO_HOLDING_SEQUENCE_ID", "Dormant sequence, no active email steps"],
  ], [3000, 6360]),
  note("Full filter recipe and API gotchas are in the Apollo Reach Out Guide — not repeated here."),

  chapter(3, "In build — Deal Intelligence"),
  p("Two-stage AI scoring over every qualified deal. Stage 1 is cheap and runs on the whole qualified pipeline; Stage 2 is heavy and only fires for deals that clear the gate."),
  table(["Stage", "Runs on", "Models", "Output"], [
    ["1. Preliminary fit", "Every qualified deal", "sonar-pro research, claude-haiku-4-5 scoring", "Fit score (1–4), gate flag, rationale → Attio"],
    ["2. Deep research", "Deals that clear the gate", "sonar-reasoning-pro research, claude-opus-4-8 synthesis", "Five-angle research memo, final score → Attio + hub"],
  ], [2200, 2200, 2800, 2160]),
  h2("Rubric — five equally weighted parameters"),
  table(["Parameter", "Weight"], [
    ["Lead / round dynamics", "20%"],
    ["AI score", "20%"],
    ["Fundamentals", "20%"],
    ["Return potential", "20%"],
    ["Terms", "20%"],
  ], [5200, 4160]),
  p([run("Scored 1–4 against the anchors in "), code("prompts/rubric.md"), run(". "), code("FIT_THRESHOLD"), run(" = 3.0 clears the gate to Stage 2; "), code("VERY_HIGH_QUALITY_THRESHOLD"), run(" = 3.3 is the second tier surfaced in the Stage 1 rationale.")]),
  h2("Running it"),
  ...codeBlock([
    "python -m deal_intelligence.pipeline            # full run",
    "python -m deal_intelligence.pipeline --dry-run  # no Attio write-back",
    "python -m deal_intelligence.pipeline --stage1   # stage 1 only",
  ]),
  note("Not yet exposed over HTTP for n8n — the pipeline docstring references a /screen-deals endpoint that still needs to be added to app.py. Attio write-back slugs (fit_score, fit_gate, fit_rationale, memo_url, final_score) are unset until those fields exist on the Deals object."),

  chapter(4, "Roadmap — ready to add"),
  p("Infrastructure already supports these; none are in the initial deploy scope. Each rides the existing n8n + app.py stack, so adding one is build time, not new monthly cost."),
  table(["#", "Workflow", "Trigger", "Logic", "Output"], [
    ["⑤", "Daily Deal Digest", "7am ET, Apps Script", "Fetch 15+ RSS feeds, filter by sector/stage", "Email digest"],
    ["⑥", "Portfolio Monitoring", "7am ET, Apps Script", "Google Alerts RSS per portfolio company", "Attio note on company"],
    ["⑦", "LP Intelligence", "Weekly Mon 7am", "SEC EDGAR 13F scan, filter target LPs", "Attio LP note + email"],
    ["⑧", "Competitive VC Radar", "Weekly Mon 7am", "RSS (StrictlyVC, The Information, PEHub)", "Email digest"],
  ], [600, 2400, 1900, 2700, 1760]),
  h2("New app.py endpoints required"),
  table(["Endpoint", "Purpose", "Called by"], [
    ["POST /intel/portfolio-news", "Writes a note to the Attio company record", "Workflow ⑥"],
    ["POST /intel/lp-activity", "Writes a note to the Attio LP record", "Workflow ⑦"],
  ], [3200, 3760, 2400]),
  note("Phase 2, documented not built: Thesis Radar — broader signal aggregation (web pages, hiring, filings, product launches) scored against ID8's theses."),

  chapter(5, "Infrastructure"),
  h2("Cloud Run — n8n"),
  table(["Parameter", "Value"], [
    ["Image", "docker.n8n.io/n8nio/n8n:1.108.2 (pinned)"],
    ["Region / CPU / Memory", "us-east4, 1 vCPU, 1 Gi"],
    ["Min / max instances", "1 / 1 — n8n regular mode requires single-instance"],
    ["Timeout / port", "3600s / 5678"],
  ], [3000, 6360]),
  h2("Cloud Run — app.py"),
  table(["Parameter", "Value"], [
    ["Runtime", "Python 3.12 (Flask)"],
    ["CPU / Memory", "1 vCPU / 512 Mi"],
    ["Min / max instances", "0 / 3 — scales to zero, only called by n8n"],
    ["Timeout", "300s"],
  ], [3000, 6360]),
  h2("Supporting services"),
  table(["Service", "Role"], [
    ["Neon Postgres", "Free tier — n8n config + execution history, ~50–100MB used"],
    ["Artifact Registry", "Docker images for both Cloud Run services, us-east4"],
    ["Secret Manager", "n8n-encryption-key, n8n-database-url, attio-api-key"],
    ["Google Apps Script", "Drive folder watch (5 min), Sheet onChange, daily cron — free"],
  ], [2600, 6760]),
  h2("IAM roles required (Oscar's account)"),
  table(["Role", "Purpose"], [
    ["roles/run.admin", "Deploy and manage Cloud Run services"],
    ["roles/artifactregistry.admin", "Push Docker images"],
    ["roles/secretmanager.admin", "Create and update secrets"],
    ["roles/cloudbuild.builds.editor", "Submit builds via Cloud Build"],
    ["roles/iam.serviceAccountUser", "Deploy as the compute service account"],
    ["roles/logging.viewer", "Read Cloud Run logs for debugging"],
  ], [3600, 5760]),

  chapter(6, "Platforms, cost, and access"),
  h2("Data sources and access"),
  table(["Source", "Used by", "Access"], [
    ["PitchBook", "Pipeline, Deal Intelligence", "MCP"],
    ["Apollo", "Apollo Reach Out", "Master API key"],
    ["Attio", "Pipeline, Apollo", "API key"],
    ["Perplexity", "Apollo enrichment, Deal Intelligence", "API key"],
    ["Anthropic", "Deal Intelligence", "API key"],
  ], [2200, 4360, 2800]),
  h2("Monthly cost"),
  table(["Item", "Config", "$/mo"], [
    ["n8n — Cloud Run", "1 vCPU/1Gi, min=1", "~$9"],
    ["app.py — Cloud Run", "1 vCPU/512Mi, min=0", "~$1"],
    ["Neon Postgres", "Free tier", "$0"],
    ["Artifact Registry", "2 images, ~2GB", "~$0.10"],
    ["Secret Manager", "3 secrets", "~$0.10"],
    ["RSS / SEC EDGAR / GDELT", "Free public APIs", "$0"],
    ["Perplexity (AI usage)", "Pay-as-you-go", "~$2–3"],
    ["Anthropic (AI usage)", "Pay-as-you-go", "Usage-based"],
  ], [3200, 3760, 2400]),
  note("Infrastructure + AI usage totals ~$12–15/mo. Attio, Apollo, and PitchBook are existing firm subscriptions, not new spend. A single Zapier Business seat alone is $69/mo; Make and n8n Cloud run $50–300/mo and would not cover the Deal Intelligence layer at all."),
  h2("Access needed to proceed"),
  check("GCP project created, billing enabled (suggested name: id8-pipeline)"),
  check("Oscar granted Owner IAM role on the project"),
  check("OAuth consent screen configured — Internal, app name \"ID8 Pipeline\""),
  check("OAuth redirect URI added after first deploy (Oscar provides the URL)"),
  check("Neon account — Oscar self-serve, free tier, no action needed from owner"),
  h2("Timeline"),
  table(["Phase", "What", "Who", "Time"], [
    ["1", "GCP project setup + grant access", "Account owner", "30 min"],
    ["2", "Deploy n8n", "Oscar", "1–2 hrs"],
    ["3", "Deploy data pipeline, re-auth credentials", "Oscar", "1 hr"],
    ["4", "Build intelligence workflows ⑤–⑧", "Oscar", "2–3 hrs"],
    ["5", "Test end-to-end, cut over from local", "Oscar", "1 hr"],
  ], [800, 4360, 2200, 2000]),
  p(bold("Total elapsed time to fully operational: 1–2 days.")),

  ...closing(),
];

build(__dirname + "/../docs/ID8_Workflows_and_Platforms_Brief.docx", "Workflows & Platforms", children)
  .then(() => console.log("Workflows & Platforms brief written."));
