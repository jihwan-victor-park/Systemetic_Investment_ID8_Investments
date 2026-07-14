"""Research and synthesis helpers. Perplexity for web research, Anthropic for
synthesis and scoring. Both via plain HTTP so there is no SDK dependency."""
import asyncio
import json
import re

from . import config
from .net import session


def _extract_json(text: str):
    """Pull the first valid JSON object or array out of a model response.

    Reasoning models (sonar-reasoning-pro, sonar-deep-research) prepend a
    <think>...</think> chain-of-thought block to message.content before the
    actual answer, and that block routinely contains its own stray braces
    (it's often thinking out loud about the very JSON shape it's about to
    produce) -- strip it first so bracket-matching can't lock onto reasoning
    text instead of the real answer. Also tries every candidate start
    position for the opener, not just the first, so one unparseable brace
    region doesn't abandon the whole search."""
    text = text.strip()
    # strip code fences
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    # strip a reasoning-model chain-of-thought preamble, if present
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = -1
        while True:
            start = text.find(opener, start + 1)
            if start == -1:
                break
            depth = 0
            for i in range(start, len(text)):
                if text[i] == opener:
                    depth += 1
                elif text[i] == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break  # try the next opener position instead of giving up
    return None


# ── Perplexity ───────────────────────────────────────────────────────────────
def perplexity(prompt: str, model: str = None, timeout: int = 90, temperature: float = None,
                reasoning_effort: str = None, search_context_size: str = None, max_tokens: int = None) -> tuple:
    """Returns (content, citations) - citations is the list of source URLs
    Perplexity grounded its answer in, straight off the API response.

    temperature: pass 0 for scoring (cuts run-to-run wobble that can flip a
    boundary deal across the gate); leave None to use the API default.

    reasoning_effort: "low" | "medium" | "high" -- how hard a reasoning-
    capable model (sonar-reasoning-pro, sonar-deep-research) works before
    answering. search_context_size: "low" | "medium" | "high" -- how much web
    context it pulls in per query (API default is "low"). Both None leaves
    the API default in place; pass "high"/"high" for max-depth research.

    max_tokens: explicit output cap. Leave None for the API default -- pass it
    explicitly for any response with a lot of required structure (e.g. Stage
    1's per-subcategory findings), since a low silent default can truncate a
    long JSON response mid-object and break extract_json()."""
    if not config.PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY not set")
    payload = {"model": model or config.STAGE1_RESEARCH_MODEL,
               "messages": [{"role": "user", "content": prompt}]}
    if temperature is not None:
        payload["temperature"] = temperature
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort
    if search_context_size is not None:
        payload["web_search_options"] = {"search_context_size": search_context_size}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    headers = {"Authorization": f"Bearer {config.PERPLEXITY_API_KEY}",
               "Content-Type": "application/json"}
    r = session.post(config.PERPLEXITY_URL, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations") or []
    return content, citations


async def perplexity_async(prompt: str, model: str = None, timeout: int = 90, temperature: float = None,
                            reasoning_effort: str = None, search_context_size: str = None,
                            max_tokens: int = None) -> tuple:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: perplexity(prompt, model, timeout, temperature, reasoning_effort,
                                  search_context_size, max_tokens))


# ── Anthropic (Claude) ───────────────────────────────────────────────────────
def claude(system: str, prompt: str, model: str = None, max_tokens: int = 4000, timeout: int = 120) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    payload = {"model": model or config.SYNTH_MODEL, "max_tokens": max_tokens,
               "system": system, "messages": [{"role": "user", "content": prompt}]}
    headers = {"x-api-key": config.ANTHROPIC_API_KEY,
               "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    r = session.post(config.ANTHROPIC_URL, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    parts = r.json().get("content", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


async def claude_async(system: str, prompt: str, model: str = None, max_tokens: int = 4000) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: claude(system, prompt, model, max_tokens))


def extract_json(text: str):
    return _extract_json(text)
