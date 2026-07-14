"""Constrained NLU for the research-chat tool.

This chat does exactly ONE thing today: extract a company (plus whatever
optional context is mentioned) from a free-text message, to kick off Stage 1
research. It is deliberately not a general-purpose agent -- no other intent,
no tool-calling, no multi-turn memory. Stage 2 (deal screening) chat support
is a separate, later addition; until then Stage 2 keeps using the plain
structured form in ResearchChat.jsx, untouched by this module.
"""
from . import config, research

_SYSTEM = (
    "You extract a company-research request from a short chat message for an "
    "internal venture capital tool. This tool does exactly one thing: kick off "
    "Stage 1 research (a fit-check screen) on ONE named company. Never do "
    "anything else, and never invent information that isn't in the message.\n\n"
    "Return only JSON, no prose:\n"
    '{"name": "<company name, or empty string if none is identifiable>", '
    '"domain": "<company website/domain if mentioned, else empty>", '
    '"round": "<funding round if mentioned, e.g. \\"Series C\\", else empty>", '
    '"lead_investors": "<lead investor(s) if mentioned, else empty>", '
    '"hq": "<HQ location if mentioned, else empty>", '
    '"needs_clarification": true or false, '
    '"clarification_question": "<one short question, only if needs_clarification>"}\n\n'
    "Set needs_clarification to true ONLY when no company name is identifiable at "
    "all -- e.g. small talk, or a question with no named company. Do NOT ask for "
    "domain/round/lead investor/HQ just because they're absent; those are optional "
    "and Stage 1 research works fine without them."
)


def parse_investigate_message(message: str) -> dict:
    """Returns {name, domain, round, lead_investors, hq, needs_clarification,
    clarification_question}. domain/round/lead_investors/hq are None (not
    empty string) when absent, matching DealInput's own convention.

    Perplexity, not Claude -- Stage 1 (scoring and now this parsing step) is
    deliberately Anthropic-free; ANTHROPIC_API_KEY isn't required anywhere in
    the Stage 1 path. disable_search=True: this is parsing structure out of
    text already in the message, not a research question -- a web search
    here would just add cost and latency for nothing."""
    raw, _ = research.perplexity(message, model=config.CHAT_INTENT_MODEL, system=_SYSTEM,
                                  temperature=0, max_tokens=300, disable_search=True)
    parsed = research.extract_json(raw) or {}
    return {
        "name": str(parsed.get("name") or "").strip(),
        "domain": str(parsed.get("domain") or "").strip() or None,
        "round": str(parsed.get("round") or "").strip() or None,
        "lead_investors": str(parsed.get("lead_investors") or "").strip() or None,
        "hq": str(parsed.get("hq") or "").strip() or None,
        "needs_clarification": bool(parsed.get("needs_clarification")) and not str(parsed.get("name") or "").strip(),
        "clarification_question": str(parsed.get("clarification_question") or "").strip(),
    }
