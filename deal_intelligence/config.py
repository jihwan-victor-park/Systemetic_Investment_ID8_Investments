"""Configuration for the deal intelligence layer.

All secrets come from environment variables. Field slugs marked TODO must be
confirmed against the live Attio Deals object before the write-back is enabled.
"""
import os
from dotenv import load_dotenv

# Load .env first so local secrets are in os.environ before _secrets runs.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Populate any still-missing keys from GCP Secret Manager (Cloud Run).
from deal_intelligence import _secrets  # noqa: F401, E402

# ── Secrets ──────────────────────────────────────────────────────────────────
ATTIO_API_KEY = os.getenv("ATTIO_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ── GitHub hub push (Cloud Run) ───────────────────────────────────────────────
# GH_TOKEN: fine-grained PAT with Contents: Read & Write on GH_REPO.
# Create at github.com/settings/tokens → Fine-grained → repo: id8-intelligence.
# Store in Secret Manager: gcloud secrets create GH_TOKEN --data-file=-
GH_REPO = os.getenv("GH_REPO", "ocachin/id8-intelligence")

# ── Endpoints ────────────────────────────────────────────────────────────────
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ATTIO_BASE = "https://api.attio.com/v2"

# ── Models ───────────────────────────────────────────────────────────────────
# Stage 1 now runs on Perplexity's deepest research model, at max reasoning
# effort and max search context -- every qualified deal gets the full-power
# read, not the cheap pass v2.1 used. Stage 2's model is unchanged for now.
STAGE1_RESEARCH_MODEL = os.getenv("DI_STAGE1_MODEL", "sonar-deep-research")
STAGE2_RESEARCH_MODEL = os.getenv("DI_STAGE2_MODEL", "sonar-reasoning-pro")
# Stage 2 runs eleven angle queries per deal, but only for deals that already
# cleared the Stage 1 gate -- a small enough set that "high" search context
# (deepest grounding the API offers) is affordable per angle, unlike Stage 1
# which runs on every qualified deal. See deep_research()'s comment for why
# this differs from Stage 1's reasoning_effort caution.
STAGE2_SEARCH_CONTEXT_SIZE = os.getenv("DI_STAGE2_SEARCH_CONTEXT_SIZE", "high")
SYNTH_MODEL = os.getenv("DI_SYNTH_MODEL", "claude-opus-4-8")        # memo synthesis
SCORE_MODEL = os.getenv("DI_SCORE_MODEL", "claude-haiku-4-5-20251001")  # rubric scoring
# Research-chat's Stage 1 intent parsing (deal_intelligence/chat_intent.py) --
# extracting a company name out of a short chat message doesn't need
# sonar-deep-research's depth (or web search at all -- see disable_search in
# that module), so this defaults to Perplexity's cheapest model. Deliberately
# a Perplexity model, not a Claude one -- Stage 1 has no Anthropic dependency.
CHAT_INTENT_MODEL = os.getenv("DI_CHAT_INTENT_MODEL", "sonar")

# sonar-deep-research runs iterative multi-step search and can take several
# minutes per deal -- both knobs below only apply to Stage 1's perplexity()
# call (see stage1_fit.py). reasoning_effort/search_context_size are Perplexity
# API params (low/medium/high).
#
# NOT "high" -- confirmed via production logs that "high" reliably fails on
# this prompt: it drove the model to 40 search queries and 100K+ reasoning
# tokens, exhausting its generation budget on reasoning before ever writing
# the JSON answer (finish_reason="length", completion_tokens=0, every single
# attempt). "Max depth" that never produces an answer isn't more powerful,
# it's broken. "medium" is still far deeper than the original sonar-pro
# baseline and actually completes.
STAGE1_REASONING_EFFORT = os.getenv("DI_STAGE1_REASONING_EFFORT", "medium")
# Tried raising this to "high" on 2026-07-15 on the theory that v4's 35-item
# checklist needed more page content per search than "medium" was returning.
# Reverted same day -- Research Chat (same score_deal() call, see
# chat_intent.py/pipeline/app.py's /research-chat) stopped completing at all
# after that change, consistent with the exact failure mode documented above
# for reasoning_effort="high": more content pulled per search plus v4's
# already-larger prompt pushes total token usage past the point where the
# model ever gets to writing the JSON answer within STAGE1_TIMEOUT_SECONDS/
# STAGE1_MAX_TOKENS. "medium" is the confirmed-working value; do not raise
# this without a live way to test it first.
STAGE1_SEARCH_CONTEXT_SIZE = os.getenv("DI_STAGE1_SEARCH_CONTEXT_SIZE", "medium")
STAGE1_TIMEOUT_SECONDS = int(os.getenv("DI_STAGE1_TIMEOUT_SECONDS", "600"))
# The three-tier rationale (point -> dimension -> deal) asks for 35 grounded
# subcategory findings+scores (v4: six equally-weighted dimensions, 2-10
# fixed subcategories each) plus six dimension syntheses plus a deal-level
# rationale, all in one JSON response.
# History: 4000 too low -> 8000 -> 10000 for v3.1's fifth checklist -- and
# 10000 STILL truncated in production (Research Chat, 2026-07-14: the raw
# response was 24000+ characters and still cut off mid-sentence inside the
# Terms dimension's evidence field, after already writing all five scored
# dimensions). The root cause wasn't an unlucky ceiling, it was that
# "one tight sentence" per finding is not a real constraint -- the model was
# actually writing 30-50+ word findings, not the ~12 words that phrase implies.
# prompts/stage1_fit.md now puts a hard, explicit word cap on every field
# (<=12 words/finding, <=25 words/evidence, <=40 words/rationale) instead of
# relying on "keep it tight" as a vibe, which should bring a compliant
# response down to roughly 2000-3500 tokens of actual JSON content.
#
# v4 regression (2026-07-15): the rubric injected into {rubric} roughly
# doubled in length (35 subcategories each rendered as a full 4-row anchor
# table, vs. v3.1's 50 one-line checklist bullets) even though the expected
# JSON output got smaller (35 scored items, not 50). At least one production
# run (Research Chat, "Nous Research") came back as a full markdown research
# report -- "# Evaluating Nous Research as an ID8 Investments Opportunity:
# A Rubric-Based Scientific Analysis..." -- that never once opened a JSON
# object, and got cut off mid-sentence at the token ceiling. That is not the
# v3.1 failure mode (valid-looking JSON truncated mid-object); the model
# abandoned the JSON contract entirely and free-wrote prose instead, almost
# certainly because a much longer, more essay-like rubric block primed it
# toward answering in kind. The real fix is prompt-side (prompts/stage1_fit.md
# now states the "single JSON object, no report" constraint both before and
# after the rubric, not just once at the end) -- raising this ceiling is only
# headroom behind that fix, not a substitute for it; a model that's decided
# to write a report will not be stopped by a bigger budget, just cut off later.
STAGE1_MAX_TOKENS = int(os.getenv("DI_STAGE1_MAX_TOKENS", "14000"))

# ── Gate ─────────────────────────────────────────────────────────────────────
# fit_score is the rubric's weighted average, 1-4 scale. v2.1 decision bands
# (see prompts/rubric.md): >= STRONG_GO_THRESHOLD is "Strong Go"; >= FIT_THRESHOLD
# (the deep-research gate, "Go / IC Review") through STRONG_GO_THRESHOLD is
# "Go / IC Review"; >= MORE_DILIGENCE_THRESHOLD through FIT_THRESHOLD is
# "More Diligence"; below that is "Pass". A hard_auto_pass or watch_list flag
# from stage1_fit overrides these bands entirely (see stage1_fit.py).
#
# Renamed from VERY_HIGH_QUALITY_THRESHOLD / BORDERLINE_THRESHOLD when the rubric
# went from 4 tiers to 5 (v2.1) -- if either old env var is set anywhere outside
# this repo (Cloud Run, n8n), it will silently stop applying; use the new names.
FIT_THRESHOLD = float(os.getenv("DI_FIT_THRESHOLD", "3.0"))
STRONG_GO_THRESHOLD = float(os.getenv("DI_STRONG_GO_THRESHOLD", "3.5"))
MORE_DILIGENCE_THRESHOLD = float(os.getenv("DI_MORE_DILIGENCE_THRESHOLD", "2.5"))

# ── Concurrency ──────────────────────────────────────────────────────────────
# sonar-deep-research has a much tighter rate limit than sonar-pro (as low as
# 5 requests/min on a fresh Perplexity account, scaling with usage tier) --
# defaulting lower than v2.1's 6 to avoid 429s the first time this runs.
# Raise via env var once the account's actual Perplexity tier is confirmed.
STAGE1_PARALLEL = int(os.getenv("DI_STAGE1_PARALLEL", "2"))
STAGE2_PARALLEL = int(os.getenv("DI_STAGE2_PARALLEL", "3"))
# attio_io.list_all_deals()'s per-deal Company domain lookups -- plain GETs
# against Attio's API, not an LLM call, so this can run much higher than the
# Stage 1/2 knobs above without hitting a research-model rate limit.
ATTIO_IMPORT_PARALLEL = int(os.getenv("DI_ATTIO_IMPORT_PARALLEL", "8"))

# ── Attio Deals schema ───────────────────────────────────────────────────────
DEALS_OBJECT = os.getenv("DI_DEALS_OBJECT", "deals")
STAGE_SLUG = os.getenv("DI_STAGE_SLUG", "stage")          # the deal-stage attribute
QUALIFIED_VALUE = os.getenv("DI_QUALIFIED_VALUE", "Qualified")

# Value slugs to read off a deal for research context.
# Confirmed against pipeline/app.py's FIELD_MAP/build_attio_values -- the code
# that actually writes these Deal records, so it's ground truth for what the
# real api_slugs are. round/hq were wrong here (guessed "round"/"hq_location",
# real slugs are "series"/"location") -- every deal re-screened via
# attio_io.get_qualified_deals() (the /screen-deals backlog path, as opposed to
# a brand-new deal scored fresh off n8n via pipeline/app.py's own dict, which
# was never affected by this) got round=None/hq=None every single time,
# starving Stage 1 of the two facts its Stage/Geography gate needs most.
# domain has no fix here -- see get_qualified_deals(), it isn't a Deal
# attribute at all, it only exists on the linked Company record.
READ_SLUGS = {
    "name": os.getenv("DI_SLUG_NAME", "name"),
    "domain": os.getenv("DI_SLUG_DOMAIN", "domain"),       # not a real Deal attribute; see get_qualified_deals()
    "round": os.getenv("DI_SLUG_ROUND", "series"),
    "hq": os.getenv("DI_SLUG_HQ", "location"),
    "lead_investors": "lead_investors",                    # text slug (see memory)
}

# Write-back slugs. Leave unset (None) to skip that write until the field exists.
WRITE_SLUGS = {
    "fit_score": os.getenv("DI_SLUG_FIT_SCORE"),           # number, 1-4     TODO create in Attio
    "fit_gate": os.getenv("DI_SLUG_FIT_GATE"),             # select Yes/No   TODO
    "fit_rationale": os.getenv("DI_SLUG_FIT_RATIONALE"),   # text            TODO
    "hub_url": os.getenv("DI_SLUG_HUB_URL"),               # text/url — link to the hub research page  TODO
    "memo_url": os.getenv("DI_SLUG_MEMO_URL"),             # text/url        TODO
    "final_score": os.getenv("DI_SLUG_FINAL_SCORE"),       # number          TODO
}

MEMO_DIR = os.getenv("DI_MEMO_DIR", "deal_intelligence/output/memos")

# ── Hub publishing ───────────────────────────────────────────────────────────
# Where stage-1 company pages (.md) and their downloadable .docx land in the hub.
HUB_COMPANIES_DIR = os.getenv("DI_HUB_COMPANIES_DIR", "hub/docs/research/companies")
HUB_DOCX_DIR = os.getenv("DI_HUB_DOCX_DIR", "hub/static/research/companies")
# Public base URL of the deployed hub, used to compose the per-company research
# link written onto the Attio deal. The page path is /docs/qualified-deals/<slug>.
# This is hub-next's real Cloud Run URL, not the old Docusaurus hub
# (molten-crowbar-498920-q8.web.app) that intel.id8investments.com still
# resolves to -- that custom domain was never actually remapped to hub-next
# (see docs/HUB_NEXT_ACCESS_REQUESTS.md's DNS checklist), so defaulting to it
# here sent every email link to a dead page on the old site.
HUB_BASE_URL = os.getenv("DI_HUB_BASE_URL", "https://id8-hub-next-bkq2vtg6qq-uc.a.run.app")

# ── hub-next (Firestore + Cloud Storage) ──────────────────────────────────────
# Same GCP project as everything else here. The Cloud Run service account
# running this pipeline needs roles/datastore.user (Firestore) and, once
# DI_DOCX_BUCKET is set, roles/storage.objectAdmin scoped to that bucket.
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "molten-crowbar-498920-q8")
# Bucket for per-screen .docx files hub-next's docx route reads from. Unset =
# Firestore write still happens, just no docx uploaded/linked for that screen.
DI_DOCX_BUCKET = os.getenv("DI_DOCX_BUCKET")
