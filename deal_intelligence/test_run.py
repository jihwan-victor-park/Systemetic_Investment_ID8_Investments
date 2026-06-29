"""Standalone test harness. Runs stage 1 (fit score) and, for deals that
clear the gate, stage 2 (deep research + memo) against hand-entered deals,
bypassing Attio entirely so we can sanity-check output quality directly.

Usage: python -m deal_intelligence.test_run
"""
import asyncio
import json
import time

from . import config, stage1_fit, stage2_research
from .schemas import DealInput

DEALS = [
    DealInput(record_id="test-1", name="Gradial (Seattle, WA; generative AI platform for "
              "enterprise content workflows and customer support)",
              round="Series C", lead_investors="Insight Partners"),
    DealInput(record_id="test-2", name="Twenty (Arlington, VA; cyber-warfighting platform for "
              "real-time offensive cyber operations, defense)",
              round="Series B", lead_investors="Accel"),
    DealInput(record_id="test-3", name="Verse (San Francisco, CA; generative AI energy "
              "infrastructure platform for clean power procurement)",
              round="Series B", lead_investors="Bessemer Venture Partners"),
]


def _log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def main():
    if not config.PERPLEXITY_API_KEY:
        _log("PERPLEXITY_API_KEY not set, aborting")
        return
    if not config.ANTHROPIC_API_KEY:
        _log("ANTHROPIC_API_KEY not set, stage 2 will run the research angles "
             "but skip memo synthesis")

    for deal in DEALS:
        _log(f"=== {deal.name}: stage 1 (fit score) ===")
        t0 = time.time()
        fit = await stage1_fit.score_deal(deal)
        _log(f"stage 1 done in {time.time() - t0:.1f}s, "
             f"fit_score={fit.fit_score}, gate={fit.gate}, tier={fit.quality_tier}")
        print(json.dumps(fit.to_dict(), indent=2))

        if not fit.gate:
            _log(f"{deal.name} did not clear the 3.0 gate, stopping here")
            continue

        _log(f"=== {deal.name}: stage 2 (deep research + memo) ===")
        t0 = time.time()
        memo = await stage2_research.deep_research(deal)
        _log(f"stage 2 done in {time.time() - t0:.1f}s, "
             f"final_score={memo.final_score}, sources={len(memo.sources)}, memo={memo.markdown_path}")
        print(json.dumps(memo.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
