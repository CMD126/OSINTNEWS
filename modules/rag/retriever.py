"""
Pure retrieval functions for the RAG pipeline.

Functional Programming Principles applied here:
  - PURE FUNCTIONS: every function takes input, returns output, no side effects.
  - IMMUTABILITY: raw dicts are converted to frozen NewsItem objects immediately.
  - COMPOSITION: small functions are composed into larger pipelines via `pipe()`.
  - HIGHER-ORDER FUNCTIONS: filter/map factories return callable predicates.

Analogy to C++20 std::ranges:
  raw_results | transform(to_news_item) | filter(has_keyword("fraud")) | take(20)
  →  pipe(to_bundle, filter_kw("fraud"), take(20))(raw_results)
"""

from __future__ import annotations
from functools import reduce
from typing import Callable
from datetime import datetime

from modules.rag.models import NewsItem, SearchBundle


# ---------------------------------------------------------------------------
# Pure conversion functions
# ---------------------------------------------------------------------------

def raw_to_news_item(raw: dict) -> NewsItem:
    """Pure function: dict → immutable NewsItem."""
    return NewsItem(
        title    = raw.get("title",    "No title"),
        url      = raw.get("href",     ""),
        snippet  = (raw.get("body",    "") or "").strip(),
        category = raw.get("category", "Unknown"),
        target   = raw.get("target",   ""),
        query    = raw.get("query",    ""),
    )


def raws_to_bundle(raw_results: list[dict], target: str) -> SearchBundle:
    """Pure function: list[dict] → immutable SearchBundle."""
    items = tuple(map(raw_to_news_item, raw_results))
    return SearchBundle(
        items     = items,
        target    = target,
        timestamp = datetime.now().isoformat(),
    )


# ---------------------------------------------------------------------------
# Pure predicate factories (higher-order functions)
# ---------------------------------------------------------------------------

def has_keyword(keyword: str) -> Callable[[NewsItem], bool]:
    """Returns a pure predicate: True if item contains keyword in title or snippet."""
    kw = keyword.lower().strip()
    return lambda item: kw in item.title.lower() or kw in item.snippet.lower()


def in_category(category: str) -> Callable[[NewsItem], bool]:
    """Returns a pure predicate: True if item belongs to given category."""
    return lambda item: item.category.lower() == category.lower()


def has_url(domain: str) -> Callable[[NewsItem], bool]:
    """Returns a pure predicate: True if item URL contains given domain."""
    return lambda item: domain.lower() in item.url.lower()


def min_snippet_length(length: int) -> Callable[[NewsItem], bool]:
    """Returns a pure predicate: True if snippet is at least `length` chars."""
    return lambda item: len(item.snippet) >= length


# ---------------------------------------------------------------------------
# Pure bundle transformations
# ---------------------------------------------------------------------------

def apply_filter(predicate: Callable[[NewsItem], bool]) -> Callable[[SearchBundle], SearchBundle]:
    """Returns a pure function that filters a bundle. Does NOT mutate the input."""
    return lambda bundle: bundle.filtered(predicate)


def deduplicate(bundle: SearchBundle) -> SearchBundle:
    """Pure function: removes duplicate URLs. Returns a new bundle."""
    seen: set[str] = set()
    unique = []
    for item in bundle.items:
        if item.url not in seen:
            seen.add(item.url)
            unique.append(item)
    from dataclasses import replace
    return replace(bundle, items=tuple(unique))


def sort_by_category(bundle: SearchBundle) -> SearchBundle:
    """Pure function: returns new bundle with items sorted by category name."""
    from dataclasses import replace
    return replace(bundle, items=tuple(sorted(bundle.items, key=lambda i: i.category)))


def truncate_snippets(max_chars: int = 500) -> Callable[[SearchBundle], SearchBundle]:
    """
    Returns a pure function that truncates snippets to max_chars.
    Produces new NewsItem objects — never mutates existing ones.
    """
    def _truncate(bundle: SearchBundle) -> SearchBundle:
        from dataclasses import replace
        items = tuple(
            item.with_snippet(item.snippet[:max_chars] + "…")
            if len(item.snippet) > max_chars else item
            for item in bundle.items
        )
        return replace(bundle, items=items)
    return _truncate


# ---------------------------------------------------------------------------
# Functional composition
# ---------------------------------------------------------------------------

def pipe(*fns: Callable) -> Callable:
    """
    Left-to-right function composition.
    pipe(f, g, h)(x)  ==  h(g(f(x)))

    Equivalent to C++20:
      auto pipeline = f | g | h;
      auto result   = pipeline(x);
    """
    return reduce(lambda f, g: lambda x: g(f(x)), fns)


def build_retrieval_pipeline(
    keyword_filter: str = "",
    dedup:          bool = True,
    max_snippet:    int  = 500,
) -> Callable[[SearchBundle], SearchBundle]:
    """
    Composes a reusable retrieval post-processing pipeline.

    Steps (applied left to right):
      1. Deduplicate URLs
      2. Filter by keyword (optional)
      3. Truncate long snippets
      4. Sort by category
    """
    steps: list[Callable] = []

    if dedup:
        steps.append(deduplicate)

    if keyword_filter.strip():
        steps.append(apply_filter(has_keyword(keyword_filter)))

    steps.append(truncate_snippets(max_snippet))
    steps.append(sort_by_category)

    return pipe(*steps) if steps else (lambda b: b)
