"""
RAG Pipeline — functional composition of Retriever + Generator.

Architecture:
  ┌──────────────┐    ┌───────────────────┐    ┌──────────────┐
  │  raw_results │ ─▶ │  RETRIEVER        │ ─▶ │  GENERATOR   │
  │  (list[dict])│    │  • convert        │    │  • build ctx │
  │              │    │  • deduplicate    │    │  • call LLM  │
  │              │    │  • filter         │    │  • parse     │
  │              │    │  • sort           │    │  • return    │
  └──────────────┘    └───────────────────┘    └──────────────┘
        │                    │                        │
        │              SearchBundle             AIAnalysis
        │             (immutable)               (immutable)
        └────────────────────┴───────────────────────┘
                          PipelineResult

Functional principle:
  The full pipeline is a pure function composition.
  No global state. No mutation. Same inputs → same outputs.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from modules.rag.models    import SearchBundle, AIAnalysis
from modules.rag.retriever import raws_to_bundle, build_retrieval_pipeline
from modules.rag.generator import generate


# ---------------------------------------------------------------------------
# Pipeline result (immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PipelineResult:
    """
    Immutable output of the full RAG pipeline.
    Contains both the retrieved data and the AI analysis.
    """
    bundle:   SearchBundle
    analysis: AIAnalysis

    @property
    def succeeded(self) -> bool:
        return self.analysis.succeeded

    @property
    def target(self) -> str:
        return self.bundle.target

    @property
    def result_count(self) -> int:
        return self.bundle.count

    @property
    def cited_count(self) -> int:
        return len(self.analysis.cited_sources)


# ---------------------------------------------------------------------------
# Pipeline steps as named pure functions
# ---------------------------------------------------------------------------

def retrieval_step(
    raw_results:      list[dict],
    target:           str,
    keyword_filter:   str  = "",
    dedup:            bool = True,
    max_snippet:      int  = 500,
    min_target_words: int  = 2,
    filter_cjk:       bool = True,
) -> SearchBundle:
    """
    Pure function — Retriever step.
    Converts raw dicts → immutable SearchBundle, applies post-processing pipeline.
    """
    bundle   = raws_to_bundle(raw_results, target)
    pipeline = build_retrieval_pipeline(keyword_filter, dedup, max_snippet, min_target_words, filter_cjk)
    return pipeline(bundle)


def generation_step(
    bundle:       SearchBundle,
    provider:     str,
    api_key:      str = "",
    model:        str = "",
    max_tokens:   int = 4000,
    ollama_url:   str = "http://localhost:11434",
    ollama_model: str = "llama3.2",
    on_token           = None,
) -> AIAnalysis:
    """
    Pure function — Generator step.
    Takes a SearchBundle → calls LLM → returns immutable AIAnalysis.

    on_token : callable(str) | None — streaming callback, see generate() docs.
    """
    return generate(
        bundle       = bundle,
        provider     = provider,
        api_key      = api_key,
        model        = model,
        max_tokens   = max_tokens,
        ollama_url   = ollama_url,
        ollama_model = ollama_model,
        on_token     = on_token,
    )


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    raw_results:      list[dict],
    target:           str,
    provider:         str,
    api_key:          str  = "",
    model:            str  = "",
    max_tokens:       int  = 4000,
    keyword_filter:   str  = "",
    ollama_url:       str  = "http://localhost:11434",
    ollama_model:     str  = "llama3.2",
    dedup:            bool = True,
    max_snippet:      int  = 500,
    min_target_words: int  = 2,
    filter_cjk:       bool = True,
    on_token               = None,
) -> PipelineResult:
    """
    Full RAG pipeline: raw_results → PipelineResult.

    Steps:
      1. retrieval_step  — convert + clean + filter results
      2. generation_step — send to LLM, parse response

    on_token : callable(str) | None — enables streaming AI output.

    filter_cjk : bool
        If True (default), removes results containing Chinese/Japanese/Korean
        characters or from known CJK portals (zhihu.com, baidu.com, etc.).
        Set to False only when the search target itself is a CJK subject.

    min_target_words : int
        Minimum significant target-name words required in a result's
        title/snippet for it to be kept. Set to 0 to disable.

    Returns PipelineResult containing both SearchBundle and AIAnalysis.
    Neither input nor intermediate data is mutated.
    """
    bundle   = retrieval_step(raw_results, target, keyword_filter, dedup, max_snippet, min_target_words, filter_cjk)
    analysis = generation_step(bundle, provider, api_key, model, max_tokens, ollama_url, ollama_model, on_token=on_token)
    return PipelineResult(bundle=bundle, analysis=analysis)


def run_multi_target_pipeline(
    raw_results:      list[dict],
    targets:          list[str],
    provider:         str,
    api_key:          str  = "",
    model:            str  = "",
    max_tokens:       int  = 4000,
    keyword_filter:   str  = "",
    ollama_url:       str  = "http://localhost:11434",
    ollama_model:     str  = "llama3.2",
    dedup:            bool = True,
    max_snippet:      int  = 500,
    min_target_words: int  = 2,
    filter_cjk:       bool = True,
    on_token               = None,
) -> list[PipelineResult]:
    """
    Runs the pipeline once per target, splitting results by target field.
    Returns a list of PipelineResults, one per target.

    Functional: uses map() — no loops, no mutation.
    """
    def results_for(target: str) -> list[dict]:
        return [r for r in raw_results if r.get("target", "") == target]

    def pipeline_for(target: str) -> PipelineResult:
        return run_pipeline(
            raw_results      = results_for(target),
            target           = target,
            provider         = provider,
            api_key          = api_key,
            model            = model,
            max_tokens       = max_tokens,
            keyword_filter   = keyword_filter,
            ollama_url       = ollama_url,
            ollama_model     = ollama_model,
            dedup            = dedup,
            max_snippet      = max_snippet,
            min_target_words = min_target_words,
            filter_cjk       = filter_cjk,
            on_token         = on_token,
        )

    return list(map(pipeline_for, targets))
