"""
RAG Generator — sends retrieved context to an LLM and returns an AIAnalysis.

Supports three providers:
  1. Anthropic Claude  (recommended — best instruction-following for structured output)
  2. OpenAI GPT        (alternative cloud provider)
  3. Ollama            (local/free — any model installed on the machine)

Functional principle: each generate_* function is PURE from the caller's perspective.
  - Input: SearchBundle + credentials
  - Output: AIAnalysis (frozen dataclass)
  - No global state mutation, no side effects beyond the API call itself.
"""

from __future__ import annotations
import re
from datetime import datetime
from dataclasses import replace

from modules.rag.models import SearchBundle, AIAnalysis
from modules.rag.prompts import build_prompt_pair


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def _parse_risk_level(text: str) -> str:
    """
    Pure function: extract the highest-mentioned risk level from the LLM response.
    Scans for the structured 'Risk Level:' label first, then falls back to keyword scan.
    """
    # Try structured extraction first (e.g. "**Overall Risk Level: HIGH**")
    match = re.search(
        r'risk\s+level[:\s*_]+([A-Z]+)',
        text, re.IGNORECASE
    )
    if match:
        candidate = match.group(1).upper()
        if candidate in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            return candidate

    # Fallback: highest-severity keyword found anywhere in the text
    for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if level in text.upper():
            return level

    return "UNKNOWN"


def _extract_cited_urls(text: str, items: tuple) -> tuple[str, ...]:
    """
    Pure function: find which source URLs were actually cited in the LLM response.
    Matches [Source N] patterns and maps them to the corresponding NewsItem URL.
    """
    cited_indices = {
        int(m) - 1
        for m in re.findall(r'\[Source\s+(\d+)\]', text)
    }
    return tuple(
        items[i].url
        for i in sorted(cited_indices)
        if 0 <= i < len(items)
    )


def _make_error_analysis(target: str, model: str, error: str) -> AIAnalysis:
    """Pure function: builds a failed AIAnalysis when an LLM call throws an exception."""
    return AIAnalysis(
        target        = target,
        summary       = "",
        risk_level    = "UNKNOWN",
        cited_sources = (),
        timestamp     = datetime.now().isoformat(),
        model         = model,
        source_count  = 0,
        error         = error,
    )


def _make_analysis(target: str, text: str, model: str, items: tuple) -> AIAnalysis:
    """Pure function: builds a successful AIAnalysis from the raw LLM response text."""
    return AIAnalysis(
        target        = target,
        summary       = text,
        risk_level    = _parse_risk_level(text),
        cited_sources = _extract_cited_urls(text, items),
        timestamp     = datetime.now().isoformat(),
        model         = model,
        source_count  = len(items),
    )


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def generate_with_claude(
    bundle:    SearchBundle,
    api_key:   str,
    model:     str = "claude-sonnet-4-6",
    max_tokens: int = 3000,
) -> AIAnalysis:
    """
    Pure function: RAG Generator using Anthropic Claude API.
    Requires: pip install anthropic
    """
    target = bundle.target
    model_id = model or "claude-sonnet-4-6"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt, user_prompt = build_prompt_pair(target, bundle.items)

        response = client.messages.create(
            model      = model_id,
            max_tokens = max_tokens,
            system     = system_prompt,
            messages   = [{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text
        return _make_analysis(target, text, model_id, bundle.items)

    except Exception as exc:
        return _make_error_analysis(target, model_id, str(exc))


def generate_with_openai(
    bundle:    SearchBundle,
    api_key:   str,
    model:     str = "gpt-4o",
    max_tokens: int = 3000,
) -> AIAnalysis:
    """
    Pure function: RAG Generator using OpenAI API.
    Requires: pip install openai
    """
    target   = bundle.target
    model_id = model or "gpt-4o"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system_prompt, user_prompt = build_prompt_pair(target, bundle.items)

        response = client.chat.completions.create(
            model      = model_id,
            max_tokens = max_tokens,
            messages   = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )

        text = response.choices[0].message.content
        return _make_analysis(target, text, model_id, bundle.items)

    except Exception as exc:
        return _make_error_analysis(target, model_id, str(exc))


def generate_with_ollama(
    bundle:     SearchBundle,
    model:      str = "llama3.2",
    base_url:   str = "http://localhost:11434",
    timeout:    int = 180,
) -> AIAnalysis:
    """
    Pure function: RAG Generator using a local Ollama instance (free, offline).
    Requires: Ollama installed + model pulled  e.g. `ollama pull llama3.2`
    """
    target   = bundle.target
    model_id = f"ollama/{model}"

    try:
        import requests

        system_prompt, user_prompt = build_prompt_pair(target, bundle.items)
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        resp = requests.post(
            f"{base_url}/api/generate",
            json    = {"model": model, "prompt": full_prompt, "stream": False},
            timeout = timeout,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "")
        return _make_analysis(target, text, model_id, bundle.items)

    except Exception as exc:
        return _make_error_analysis(target, model_id, str(exc))


# ---------------------------------------------------------------------------
# Provider dispatcher
# ---------------------------------------------------------------------------

def generate(
    bundle:       SearchBundle,
    provider:     str,
    api_key:      str  = "",
    model:        str  = "",
    ollama_url:   str  = "http://localhost:11434",
    ollama_model: str  = "llama3.2",
) -> AIAnalysis:
    """
    Pure dispatcher function.
    Selects the right generator based on `provider` string.

    provider options: "claude" | "openai" | "ollama"
    """
    if not bundle.items:
        return _make_error_analysis(
            bundle.target,
            provider,
            "No search results to analyze. Run a search first.",
        )

    dispatch = {
        "claude": lambda b: generate_with_claude(b, api_key, model or "claude-sonnet-4-6"),
        "openai": lambda b: generate_with_openai(b, api_key, model or "gpt-4o"),
        "ollama": lambda b: generate_with_ollama(b, ollama_model or "llama3.2", ollama_url),
    }

    fn = dispatch.get(provider.lower())
    if fn is None:
        return _make_error_analysis(
            bundle.target,
            provider,
            f"Unknown provider '{provider}'. Use: claude, openai, or ollama.",
        )

    return fn(bundle)
