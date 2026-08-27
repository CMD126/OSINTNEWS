"""
Immutable data models for the RAG pipeline.

Functional Programming Principle: Immutability
- All models are frozen dataclasses — once created, they cannot be mutated.
- Transformations always produce NEW objects, never modify existing ones.
- This makes the entire pipeline predictable, thread-safe, and easy to test.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NewsItem:
    """
    Immutable representation of a single news/search result.
    Equivalent to a C++ `const struct` — values are fixed at construction.
    """
    title:    str
    url:      str
    snippet:  str
    category: str
    target:   str
    query:    str

    def with_snippet(self, new_snippet: str) -> "NewsItem":
        """Functional update: returns a NEW NewsItem with a different snippet."""
        from dataclasses import replace
        return replace(self, snippet=new_snippet)


@dataclass(frozen=True)
class SearchBundle:
    """
    Immutable collection of NewsItems for one search run.
    Uses tuple (not list) to enforce immutability of the collection.
    """
    items:     tuple[NewsItem, ...]
    target:    str
    timestamp: str

    @property
    def count(self) -> int:
        return len(self.items)

    def filtered(self, predicate) -> "SearchBundle":
        """Pure filter: returns a NEW bundle with only items matching predicate."""
        from dataclasses import replace
        return replace(self, items=tuple(i for i in self.items if predicate(i)))

    def by_category(self) -> dict[str, tuple[NewsItem, ...]]:
        """Pure grouping: returns a new dict grouped by category."""
        groups: dict[str, list] = {}
        for item in self.items:
            groups.setdefault(item.category, []).append(item)
        return {cat: tuple(items) for cat, items in groups.items()}


@dataclass(frozen=True)
class AIAnalysis:
    """
    Immutable AI-generated intelligence report.
    Produced by the Generator step of the RAG pipeline.
    """
    target:         str
    summary:        str          # Full markdown report from LLM
    risk_level:     str          # LOW / MEDIUM / HIGH / CRITICAL / UNKNOWN
    cited_sources:  tuple[str, ...]  # URLs cited in the analysis
    timestamp:      str
    model:          str          # e.g. "claude-sonnet-5", "gpt-5", "ollama/llama3.2"
    source_count:   int          # Number of sources fed to the LLM
    error:          Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and bool(self.summary)

    @property
    def risk_color_hex(self) -> str:
        return {
            "LOW":      "#3fb950",
            "MEDIUM":   "#d29922",
            "HIGH":     "#f78166",
            "CRITICAL": "#f85149",
        }.get(self.risk_level, "#8b949e")
