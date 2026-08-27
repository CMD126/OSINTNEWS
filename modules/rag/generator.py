"""
RAG Generator — sends retrieved context to an LLM and returns an AIAnalysis.

Supports four providers:
  1. Anthropic Claude  (recommended — best instruction-following for structured output)
  2. OpenAI GPT        (alternative cloud provider)
  3. Google Gemini     (NEW — fast and cost-effective)
  4. Ollama            (local/free — any model installed on the machine, now with streaming)

Upgrades (v2):
  - Ollama now supports streaming via /api/generate with stream=True
  - Google Gemini provider added
  - max_tokens is a configurable parameter (not hardcoded at 3000)
  - Cleaner error messages with provider name in the model field
  - Type annotations improved throughout

Upgrades (v2.1):
  - Per-provider default models centralised in DEFAULT_MODELS and refreshed
    (claude-sonnet-5 / gpt-5 / gemini-2.5-flash / llama3.2)
  - Non-streaming Claude path handles refusals and non-text leading blocks
"""

from __future__ import annotations
import re
import json
from datetime import datetime
from typing import Callable

from modules.rag.models import SearchBundle, AIAnalysis
from modules.rag.prompts import build_prompt_pair


# ---------------------------------------------------------------------------
# Default model per provider — single source of truth.
# Override at call time by passing an explicit `model=` (GUI Settings / CLI).
# ---------------------------------------------------------------------------
DEFAULT_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-5",       # current Claude 5 family (was claude-sonnet-4-6)
    "openai": "gpt-5",                 # was gpt-4o
    "gemini": "gemini-2.5-flash",      # was gemini-1.5-flash
    "ollama": "llama3.2",              # local default — change to any pulled model
}


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def _parse_risk_level(text: str) -> str:
    """
    Pure function: extract the highest-mentioned risk level from the LLM response.
    Scans for the structured 'Risk Level:' label first, then falls back to keyword scan.
    """
    match = re.search(
        r'risk\s+level[:\s*_]+([A-Z]+)',
        text, re.IGNORECASE
    )
    if match:
        candidate = match.group(1).upper()
        if candidate in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            return candidate

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
    bundle:      SearchBundle,
    api_key:     str,
    model:       str                      = "",
    max_tokens:  int                      = 4000,
    on_token:    Callable[[str], None] | None = None,
) -> AIAnalysis:
    """
    Pure function: RAG Generator using Anthropic Claude API.
    Supports optional streaming via on_token callback.
    Requires: pip install anthropic
    """
    target   = bundle.target
    model_id = model or DEFAULT_MODELS["claude"]

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        system_prompt, user_prompt = build_prompt_pair(target, bundle.items)

        if on_token is not None:
            collected: list[str] = []
            with client.messages.stream(
                model      = model_id,
                max_tokens = max_tokens,
                system     = system_prompt,
                messages   = [{"role": "user", "content": user_prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    collected.append(chunk)
                    on_token(chunk)
            text = "".join(collected)
        else:
            response = client.messages.create(
                model      = model_id,
                max_tokens = max_tokens,
                system     = system_prompt,
                messages   = [{"role": "user", "content": user_prompt}],
            )
            if response.stop_reason == "refusal":
                return _make_error_analysis(
                    target, model_id, "Model declined to answer (safety refusal)."
                )
            # content may lead with a non-text block — pick the first text block
            text = next(
                (b.text for b in response.content if getattr(b, "type", None) == "text"),
                "",
            )

        return _make_analysis(target, text, model_id, bundle.items)

    except Exception as exc:
        return _make_error_analysis(target, model_id, str(exc))


def generate_with_openai(
    bundle:     SearchBundle,
    api_key:    str,
    model:      str                      = "",
    max_tokens: int                      = 4000,
    on_token:   Callable[[str], None] | None = None,
) -> AIAnalysis:
    """
    Pure function: RAG Generator using OpenAI API.
    Supports optional streaming via on_token callback.
    Requires: pip install openai
    """
    target   = bundle.target
    model_id = model or DEFAULT_MODELS["openai"]

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        system_prompt, user_prompt = build_prompt_pair(target, bundle.items)

        if on_token is not None:
            collected: list[str] = []
            stream = client.chat.completions.create(
                model      = model_id,
                max_tokens = max_tokens,
                stream     = True,
                messages   = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    collected.append(delta)
                    on_token(delta)
            text = "".join(collected)
        else:
            response = client.chat.completions.create(
                model      = model_id,
                max_tokens = max_tokens,
                messages   = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            )
            text = response.choices[0].message.content or ""

        return _make_analysis(target, text, model_id, bundle.items)

    except Exception as exc:
        return _make_error_analysis(target, model_id, str(exc))


def generate_with_gemini(
    bundle:     SearchBundle,
    api_key:    str,
    model:      str                      = "",
    max_tokens: int                      = 4000,
    on_token:   Callable[[str], None] | None = None,
) -> AIAnalysis:
    """
    Pure function: RAG Generator using Google Gemini API.
    Supports optional streaming via on_token callback.
    Requires: pip install google-generativeai
    """
    target   = bundle.target
    model_id = model or DEFAULT_MODELS["gemini"]

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        system_prompt, user_prompt = build_prompt_pair(target, bundle.items)

        gen_model = genai.GenerativeModel(
            model_name   = model_id,
            system_instruction = system_prompt,
            generation_config  = genai.GenerationConfig(max_output_tokens=max_tokens),
        )

        if on_token is not None:
            collected: list[str] = []
            response = gen_model.generate_content(user_prompt, stream=True)
            for chunk in response:
                delta = chunk.text or ""
                if delta:
                    collected.append(delta)
                    on_token(delta)
            text = "".join(collected)
        else:
            response = gen_model.generate_content(user_prompt)
            text = response.text or ""

        return _make_analysis(target, text, f"gemini/{model_id}", bundle.items)

    except Exception as exc:
        return _make_error_analysis(target, f"gemini/{model_id}", str(exc))


def generate_with_ollama(
    bundle:     SearchBundle,
    model:      str                      = DEFAULT_MODELS["ollama"],
    base_url:   str                      = "http://localhost:11434",
    timeout:    int                      = 180,
    on_token:   Callable[[str], None] | None = None,
) -> AIAnalysis:
    """
    Pure function: RAG Generator using a local Ollama instance (free, offline).
    Now supports streaming via on_token callback.
    Requires: Ollama installed + model pulled  e.g. `ollama pull llama3.2`
    """
    target   = bundle.target
    model_id = f"ollama/{model}"

    try:
        import requests

        system_prompt, user_prompt = build_prompt_pair(target, bundle.items)
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        payload = {
            "model":  model,
            "prompt": full_prompt,
            "stream": on_token is not None,
        }

        if on_token is not None:
            # Streaming: Ollama sends one JSON object per line
            collected: list[str] = []
            with requests.post(
                f"{base_url}/api/generate",
                json    = payload,
                timeout = timeout,
                stream  = True,
            ) as resp:
                resp.raise_for_status()
                for raw_line in resp.iter_lines():
                    if not raw_line:
                        continue
                    try:
                        obj = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    chunk = obj.get("response", "")
                    if chunk:
                        collected.append(chunk)
                        on_token(chunk)
                    if obj.get("done"):
                        break
            text = "".join(collected)
        else:
            resp = requests.post(
                f"{base_url}/api/generate",
                json    = {**payload, "stream": False},
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
    max_tokens:   int  = 4000,
    ollama_url:   str  = "http://localhost:11434",
    ollama_model: str  = "",
    on_token:     Callable[[str], None] | None = None,
) -> AIAnalysis:
    """
    Pure dispatcher function.
    Selects the right generator based on `provider` string.

    Parameters
    ----------
    provider   : "claude" | "openai" | "gemini" | "ollama"
    max_tokens : max tokens to generate (default 4000)
    on_token   : callable(str) | None — enables streaming mode for all providers.
    """
    if not bundle.items:
        return _make_error_analysis(
            bundle.target,
            provider,
            "No search results to analyze. Run a search first.",
        )

    dispatch = {
        "claude": lambda b: generate_with_claude(
            b, api_key, model or DEFAULT_MODELS["claude"], max_tokens, on_token
        ),
        "openai": lambda b: generate_with_openai(
            b, api_key, model or DEFAULT_MODELS["openai"], max_tokens, on_token
        ),
        "gemini": lambda b: generate_with_gemini(
            b, api_key, model or DEFAULT_MODELS["gemini"], max_tokens, on_token
        ),
        "ollama": lambda b: generate_with_ollama(
            b,
            model    = ollama_model or DEFAULT_MODELS["ollama"],
            base_url = ollama_url,
            on_token = on_token,
        ),
    }

    fn = dispatch.get(provider.lower())
    if fn is None:
        return _make_error_analysis(
            bundle.target,
            provider,
            f"Unknown provider '{provider}'. Use: claude, openai, gemini, or ollama.",
        )

    return fn(bundle)
