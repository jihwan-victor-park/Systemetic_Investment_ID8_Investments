"""Configuration for the deal intelligence layer.

All secrets come from environment variables. Field slugs marked TODO must be
confirmed against the live Attio Deals object before the write-back is enabled.
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Secrets ──────────────────────────────────────────────────────────────────
ATTIO_API_KEY = os.getenv("ATTIO_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ── Endpoints ────────────────────────────────────────────────────────────────
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ATTIO_BASE = "https://api.attio.com/v2"

# ── Models ───────────────────────────────────────────────────────────────────
# Stage 1 is cheap and runs on every qualified deal. Stage 2 is deep and runs
# only on deals that clear the gate.
STAGE1_RESEARCH_MODEL = os.getenv("DI_STAGE1_MODEL", "sonar-pro")
STAGE2_RESEARCH_MODEL = os.getenv("DI_STAGE2_MODEL", "sonar-reasoning-pro")
SYNTH_MODEL = os.getenv("DI_SYNTH_MODEL", "claude-opus-4-8")        # memo synthesis
SCORE_MODEL = os.getenv("DI_SCORE_MODEL", "claude-haiku-4-5-20251001")  # rubric scoring

# ── Gate ─────────────────────────────────────────────────────────────────────
# fit_score is the rubric's weighted average, 1-4 scale. Deals at or above
# FIT_THRESHOLD (High Quality) go to deep research + memo. VERY_HIGH_QUALITY_
# THRESHOLD is the rubric's second tier, surfaced in the stage-1 rationale.
FIT_THRESHOLD = float(os.getenv("DI_FIT_THRESHOLD", "3.0"))
VERY_HIGH_QUALITY_THRESHOLD = float(os.getenv("DI_VERY_HIGH_QUALITY_THRESHOLD", "3.3"))

# ── Concurrency ──────────────────────────────────────────────────────────────
STAGE1_PARALLEL = int(os.getenv("DI_STAGE1_PARALLEL", "6"))
STAGE2_PARALLEL = int(os.getenv("DI_STAGE2_PARALLEL", "3"))

# ── Attio Deals schema ───────────────────────────────────────────────────────
DEALS_OBJECT = os.getenv("DI_DEALS_OBJECT", "deals")
STAGE_SLUG = os.getenv("DI_STAGE_SLUG", "stage")          # the deal-stage attribute
QUALIFIED_VALUE = os.getenv("DI_QUALIFIED_VALUE", "Qualified")

# Value slugs to read off a deal for research context. Confirm against Attio.
READ_SLUGS = {
    "name": os.getenv("DI_SLUG_NAME", "name"),
    "domain": os.getenv("DI_SLUG_DOMAIN", "domain"),       # TODO confirm
    "round": os.getenv("DI_SLUG_ROUND", "round"),          # TODO confirm
    "hq": os.getenv("DI_SLUG_HQ", "hq_location"),          # TODO confirm
    "lead_investors": "lead_investors",                    # text slug (see memory)
}

# Write-back slugs. Leave unset (None) to skip that write until the field exists.
WRITE_SLUGS = {
    "fit_score": os.getenv("DI_SLUG_FIT_SCORE"),           # number, 1-4     TODO create in Attio
    "fit_gate": os.getenv("DI_SLUG_FIT_GATE"),             # select Yes/No   TODO
    "fit_rationale": os.getenv("DI_SLUG_FIT_RATIONALE"),   # text            TODO
    "memo_url": os.getenv("DI_SLUG_MEMO_URL"),             # text/url        TODO
    "final_score": os.getenv("DI_SLUG_FINAL_SCORE"),       # number          TODO
}

MEMO_DIR = os.getenv("DI_MEMO_DIR", "deal_intelligence/output/memos")

# ── Hub publishing ───────────────────────────────────────────────────────────
# Where stage-1 company pages (.md) and their downloadable .docx land in the hub.
HUB_COMPANIES_DIR = os.getenv("DI_HUB_COMPANIES_DIR", "hub/docs/research/companies")
HUB_DOCX_DIR = os.getenv("DI_HUB_DOCX_DIR", "hub/static/research/companies")
