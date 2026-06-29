"""Stage 2: deep research and memo. Runs only on deals that cleared the gate.

Several research angles in parallel via Perplexity, then a synthesis pass via
Claude into a structured memo. Writes the memo to disk as markdown.
"""
import asyncio
import os
import re

from . import config, research
from .schemas import DealInput, DealMemo

_PROMPTS = os.path.join(os.path.dirname(__file__), "prompts")

ANGLES = ["Company", "Market", "Traction", "Round dynamics", "Risks",
          "Capital Efficiency", "Lead Conviction", "Institutional Momentum", "Foundational Quality"]

# Definitions for the four additional screening factors (beyond the core
# rubric), for further optimization once a deal has cleared the stage-1 gate.
ANGLE_DEFINITIONS = {
    "Capital Efficiency": "How lean is the preferred capital stack to date? "
        "A lean stack signals robust value creation and a real equity cushion.",
    "Lead Conviction": "Who is leading the round, and do they have a track "
        "record plus real capital commitment (skin in the game)?",
    "Institutional Momentum": "Which Tier 1 investors are already in the cap "
        "table, and do they confirm sustained momentum and market conviction?",
    "Foundational Quality": "Is the founding team reputable, and is the "
        "valuation defensible given the stage and comps?",
}


def _angle_prompt(deal: DealInput, angle: str) -> str:
    ctx = f"{deal.name}" + (f" ({deal.domain})" if deal.domain else "")
    definition = ANGLE_DEFINITIONS.get(angle)
    framing = f" {definition}" if definition else ""
    return (f"Research angle: {angle}.{framing}\nCompany: {ctx}.\n"
            f"Return concise findings with sources. Never fabricate.")


def _load(name: str) -> str:
    with open(os.path.join(_PROMPTS, name), "r", encoding="utf-8") as f:
        return f.read()


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "deal"


async def deep_research(deal: DealInput) -> DealMemo:
    # 1. gather research angles concurrently
    tasks = [research.perplexity_async(_angle_prompt(deal, a), model=config.STAGE2_RESEARCH_MODEL) for a in ANGLES]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    findings = []
    all_citations = []
    for angle, res in zip(ANGLES, results):
        if isinstance(res, Exception):
            findings.append(f"## {angle}\n(research failed: {res})")
            continue
        body, citations = res
        findings.append(f"## {angle}\n{body}")
        all_citations.extend(citations)
    findings_block = "\n\n".join(findings)
    sources = sorted(set(all_citations))

    # 2. persist the raw per-angle research up front, so it survives on disk
    # even if synthesis below fails or the Anthropic key isn't configured
    os.makedirs(config.MEMO_DIR, exist_ok=True)
    slug = _slugify(deal.name)
    raw_path = os.path.join(config.MEMO_DIR, f"{slug}_raw_research.md")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(f"# {deal.name}: Raw Research (Stage 2)\n\n{findings_block}\n")

    if not config.ANTHROPIC_API_KEY:
        return DealMemo(record_id=deal.record_id, name=deal.name,
                        sections={"memo": "(synthesis skipped: ANTHROPIC_API_KEY not set)",
                                  "raw_research": findings_block},
                        sources=sources, markdown_path=raw_path)

    # 3. synthesize the memo with Claude
    memo_prompt = _load("memo_template.md").format(findings=findings_block)
    system = "You are a venture analyst writing an internal ID8 deal memo. Plain language, no hype, no em dashes."
    memo_md = await research.claude_async(system, memo_prompt, model=config.SYNTH_MODEL, max_tokens=4000)

    # 4. pull a final score if the memo states one
    final = None
    m = re.search(r"\b(\d{1,3})\s*/\s*100\b|\bscore[^0-9]{0,12}(\d{1,3})\b", memo_md, re.IGNORECASE)
    if m:
        final = float(next(g for g in m.groups() if g))

    # 5. persist the synthesized memo
    path = os.path.join(config.MEMO_DIR, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {deal.name}: Deal Memo\n\n{memo_md}\n")

    return DealMemo(record_id=deal.record_id, name=deal.name, final_score=final,
                    sections={"memo": memo_md, "raw_research": findings_block},
                    sources=sources, markdown_path=path)


async def run(deals: list) -> list:
    sem = asyncio.Semaphore(config.STAGE2_PARALLEL)

    async def guarded(d):
        async with sem:
            try:
                return await deep_research(d)
            except Exception as e:
                return DealMemo(record_id=d.record_id, name=d.name, sections={"error": str(e)})

    return await asyncio.gather(*[guarded(d) for d in deals])
