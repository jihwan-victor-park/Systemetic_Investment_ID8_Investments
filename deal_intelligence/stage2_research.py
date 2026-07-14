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

# v3.1: eleven angles -- the five core angles every deal needs, then two
# angles that map 1:1 onto the rubric's two newest-at-parity dimensions
# (AI Moat -> ai_score, Return Potential -> return_potential), then the four
# deck-sourced supplementary factors from ID8 Growth Opportunities Fund I's
# "Additional Multi-Factor Analysis for Further Optimization" (p.13), which
# sit alongside the core rubric rather than mapping onto a single dimension.
# Keep this list and ANGLE_DEFINITIONS in sync with prompts/stage2_research.md
# (documentation only -- not loaded by code, same convention as rubric.py
# keeping rubric.md's prose in sync with PARAMS).
ANGLES = [
    "Company", "Market", "Traction", "Round Dynamics", "Risks",
    "AI Moat", "Return Potential",
    "Capital Efficiency", "Lead Conviction", "Institutional Momentum", "Foundational Quality",
]

# Every angle gets a real definition -- a bare angle name with no framing
# produces a generic, shallow Perplexity query. v3.0 only defined the four
# deck-sourced factors and left the five core angles bare; that gap is closed
# here, and the two rubric-parity angles below carry forward the specific
# verification steps (re-up check, source-VC constraint, Setter 30) that
# previously lived only in stage1_fit.md and were never re-checked at the
# deeper Stage 2 pass.
ANGLE_DEFINITIONS = {
    "Company": "What the company does, product architecture, founding team, "
        "headcount trend, and key recent hires -- the baseline facts every "
        "other angle builds on.",
    "Market": "Market size and growth, timing, structural tailwinds, and the "
        "real competitive set -- not just the company's own framing of its category.",
    "Traction": "Revenue scale and growth rate, customer/logo quality, net "
        "dollar retention, and any public or credibly-estimated metrics. Label "
        "anything triangulated as [ESTIMATED] and show the triangulation math "
        "(prior-round multiple carried forward, cross-checked against comp-set "
        "multiples), per the rubric's estimation method -- never fabricate a number.",
    "Round Dynamics": "Who is leading, at what valuation and terms, and the "
        "full prior-round history. Verify -- do not assume -- whether the lead "
        "is genuine new money or a re-up: check cap table history, prior fund "
        "disclosures, or press coverage of earlier rounds. Also assess whether "
        "the source VC providing access is structurally pro-rata-constrained "
        "(small fund relative to check size, late fund vintage, concentration-"
        "capped) versus opportunistically selling access it could afford to keep.",
    "Risks": "Competitive, regulatory, key-person, technical, and financing "
        "risk -- and whether any single risk is severe enough to be a "
        "standalone concern rather than a footnote.",
    "AI Moat": "Does AI constitute the company's actual moat, or could this "
        "product become a plugin or default feature of Claude, GPT, or Gemini "
        "without material loss? Look for proprietary architecture or "
        "fine-tuning, a real data flywheel, in-house ML/research headcount and "
        "compute investment, and any independent benchmarks -- versus a thin "
        "wrapper over third-party foundation-model APIs.",
    "Return Potential": "Base-case MOIC/IRR realism at the current entry "
        "price, exit path clarity (IPO readiness, active M&A appetite, "
        "comparable exits), and dilution modeling across at least two future "
        "financing rounds (~20-25% each). Check whether the company appears on "
        "Setter Capital's quarterly \"Setter 30\" or is reported as actively "
        "traded on Forge, Caplight, EquityZen, or similar secondary "
        "marketplaces, as an external, checkable corroboration of the modeled "
        "exit thesis -- not a substitute for it.",
    "Capital Efficiency": "How lean is the preferred capital stack to date? "
        "A lean stack signals robust value creation and a real equity cushion; "
        "a stacked, senior-heavy cap table erodes both.",
    "Lead Conviction": "Who is leading the round, and do they have a track "
        "record plus real capital commitment (skin in the game) -- a specific "
        "partner's reputation and personal co-invest, not just the fund's brand?",
    "Institutional Momentum": "Which Tier 1 investors are already in the cap "
        "table, and are they following on alongside the new lead -- a "
        "distinct, corroborating signal from the new-money lead itself, not "
        "the same fact restated.",
    "Foundational Quality": "Is the founding team reputable, and is the "
        "valuation defensible given the stage and comps (Rule-of-40-style, "
        "growth-adjusted)?",
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
    # 1. gather research angles concurrently. Stage 2 only ever runs on deals
    # that already cleared the Stage 1 gate -- a much smaller, higher-value
    # set than Stage 1's every-qualified-deal pass -- so it can afford to pull
    # more web context per query than the API default ("low"). Unlike Stage
    # 1's reasoning_effort (a token-budget knob with a documented failure mode
    # on sonar-deep-research at "high", see config.py), search_context_size
    # only controls how much grounding material is pulled in, so there's no
    # equivalent risk in raising it here.
    tasks = [research.perplexity_async(_angle_prompt(deal, a), model=config.STAGE2_RESEARCH_MODEL,
                                        search_context_size=config.STAGE2_SEARCH_CONTEXT_SIZE) for a in ANGLES]
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
