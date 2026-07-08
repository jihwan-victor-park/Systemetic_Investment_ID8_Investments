"""Research and synthesis helpers. Perplexity for web research, Anthropic for
synthesis and scoring. Both via plain HTTP so there is no SDK dependency."""
import asyncio
import json
import re

from . import config
from .net import session


def _extract_json(text: str):
    """Pull the first JSON object or array out of a model response."""
    text = text.strip()
    # strip code fences
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start != -1:
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
                            break
    return None


# ── Perplexity ───────────────────────────────────────────────────────────────
def perplexity(prompt: str, model: str = None, timeout: int = 90, temperature: float = None) -> tuple:
    """Returns (content, citations) - citations is the list of source URLs
    Perplexity grounded its answer in, straight off the API response.

    temperature: pass 0 for scoring (cuts run-to-run wobble that can flip a
    boundary deal across the gate); leave None to use the API default."""
    if not config.PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY not set")
    payload = {"model": model or config.STAGE1_RESEARCH_MODEL,
               "messages": [{"role": "user", "content": prompt}]}
    if temperature is not None:
        payload["temperature"] = temperature
    headers = {"Authorization": f"Bearer {config.PERPLEXITY_API_KEY}",
               "Content-Type": "application/json"}
    r = session.post(config.PERPLEXITY_URL, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations") or []
    return content, citations


async def perplexity_async(prompt: str, model: str = None, timeout: int = 90, temperature: float = None) -> tuple:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: perplexity(prompt, model, timeout, temperature))


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
