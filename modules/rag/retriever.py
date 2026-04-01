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
# CJK / non-Latin script detection
# ---------------------------------------------------------------------------

# Unicode ranges that indicate CJK (Chinese/Japanese/Korean) or other
# non-Latin scripts that are irrelevant for most OSINT targets.
_CJK_RANGES = (
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs (core Chinese/Japanese/Korean)
    (0x3000, 0x303F),   # CJK Symbols and Punctuation
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0xFF00, 0xFFEF),   # Halfwidth and Fullwidth Forms
    (0x3400, 0x4DBF),   # CJK Extension A
    (0x20000, 0x2A6DF), # CJK Extension B
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0x2E80, 0x2EFF),   # CJK Radicals Supplement
    (0x31C0, 0x31EF),   # CJK Strokes
)

# Domains known to produce CJK/irrelevant results for Western OSINT targets
_BLOCKED_DOMAINS = frozenset({
    "zhihu.com",
    "baidu.com",
    "weibo.com",
    "sina.com.cn",
    "163.com",
    "qq.com",
    "sohu.com",
    "douban.com",
    "bilibili.com",
    "csdn.net",
    "jianshu.com",
    "cnblogs.com",
    "sspai.com",
    "juejin.cn",
    "segmentfault.com",
    "v2ex.com",
    "tianya.cn",
    "weixin.qq.com",
    "mp.weixin.qq.com",
    "naver.com",
    "daum.net",
    "blog.naver.com",
    "cafe.naver.com",
    "2ch.net",
    "5ch.net",
    "nicovideo.jp",
    "ameba.jp",
    "fc2.com",
    "pixiv.net",
})


def _has_cjk(text: str) -> bool:
    """Return True if text contains any CJK / non-Latin script character."""
    for ch in text:
        cp = ord(ch)
        for lo, hi in _CJK_RANGES:
            if lo <= cp <= hi:
                return True
    return False


def _is_blocked_domain(url: str) -> bool:
    """Return True if the URL belongs to a known CJK/irrelevant domain."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in _BLOCKED_DOMAINS)


def no_cjk() -> Callable[[NewsItem], bool]:
    """
    Returns a pure predicate: True if the result's title, snippet, and URL
    do NOT contain CJK characters AND the domain is not on the blocklist.

    This eliminates Chinese/Japanese/Korean language results that may
    transliterate the target's name but are irrelevant for Western OSINT.
    """
    def _check(item: NewsItem) -> bool:
        if _is_blocked_domain(item.url):
            return False
        text = item.title + " " + item.snippet
        return not _has_cjk(text)
    return _check


def not_blocked_domain() -> Callable[[NewsItem], bool]:
    """Returns a pure predicate: True if URL is not on the blocked domain list."""
    return lambda item: not _is_blocked_domain(item.url)


# Common short words to ignore when checking target relevance
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to",
    "da", "de", "do", "dos", "das", "du", "di", "e", "y", "el", "la",
    "van", "von", "le", "les", "les", "des",
})

def target_relevance(min_words: int = 2) -> Callable[[NewsItem], bool]:
    """
    Returns a pure predicate: True if at least `min_words` significant
    words from the target appear in the result's title or snippet.

    'Significant' = length > 3 chars and not a stopword.
    Handles full names like 'Miguel Angelo da Cunha e Sousa' — stops
    results that only match 'Miguel' from unrelated pages.

    If the target has fewer significant words than `min_words`, the
    threshold is lowered to match all significant words that exist.
    """
    def _check(item: NewsItem) -> bool:
        sig_words = [
            w for w in item.target.lower().split()
            if len(w) > 3 and w not in _STOPWORDS
        ]
        if not sig_words:
            return True  # can't apply filter — no significant words
        haystack = (item.title + " " + item.snippet).lower()
        required = min(min_words, len(sig_words))
        matched  = sum(1 for w in sig_words if w in haystack)
        return matched >= required
    return _check


def filter_raw_results(
    raw_results:      list[dict],
    min_target_words: int = 2,
    filter_cjk:       bool = True,
) -> list[dict]:
    """
    Pure function: filter a list of raw result dicts by relevance quality.
    Converts each dict to a temporary NewsItem for each check, then returns
    only the dicts that pass ALL active filters.

    Filters applied (in order):
      1. CJK / blocked-domain filter (default ON) — eliminates Chinese,
         Japanese, Korean language pages and known CJK portals such as
         zhihu.com, baidu.com, weibo.com, etc.
      2. Target relevance filter (default ON, requires min_target_words ≥ 1)
         — keeps only results where ≥ min_target_words significant words
         from the target name appear in the title or snippet.

    Used by CLI/GUI display before the RAG pipeline runs so the user
    never sees irrelevant results.

    Parameters
    ----------
    raw_results      : list of dicts from run_searches_with_callback
    min_target_words : same semantics as target_relevance(min_words)
                       — set to 0 to disable target-word filter
    filter_cjk       : if True (default), remove results with CJK chars
                       or from blocked CJK domains
    """
    cjk_pred     = no_cjk() if filter_cjk else None
    target_pred  = target_relevance(min_target_words) if min_target_words > 0 else None

    filtered = []
    for r in raw_results:
        item = raw_to_news_item(r)
        if cjk_pred    is not None and not cjk_pred(item):
            continue
        if target_pred is not None and not target_pred(item):
            continue
        filtered.append(r)
    return filtered


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
    keyword_filter:   str  = "",
    dedup:            bool = True,
    max_snippet:      int  = 500,
    min_target_words: int  = 2,
    filter_cjk:       bool = True,
) -> Callable[[SearchBundle], SearchBundle]:
    """
    Composes a reusable retrieval post-processing pipeline.

    Steps (applied left to right):
      1. CJK / blocked-domain filter (default ON) — removes Chinese,
         Japanese, Korean language pages and known CJK portals such as
         zhihu.com, baidu.com, weibo.com, etc.
      2. Deduplicate URLs
      3. Target relevance filter — drop results whose title+snippet
         don't contain at least `min_target_words` significant words
         from the target name
      4. Filter by keyword (optional)
      5. Truncate long snippets
      6. Sort by category

    Parameters
    ----------
    filter_cjk       : bool
        If True (default), remove results with CJK characters or from
        blocked CJK domains. Set to False only if targeting CJK subjects.
    min_target_words : int
        Minimum number of significant target words that must appear
        in the result's title or snippet. Set to 0 to disable.
    """
    steps: list[Callable] = []

    # CJK filter runs first — cheapest rejection before heavier checks
    if filter_cjk:
        steps.append(apply_filter(no_cjk()))

    if dedup:
        steps.append(deduplicate)

    if min_target_words > 0:
        steps.append(apply_filter(target_relevance(min_target_words)))

    if keyword_filter.strip():
        steps.append(apply_filter(has_keyword(keyword_filter)))

    steps.append(truncate_snippets(max_snippet))
    steps.append(sort_by_category)

    return pipe(*steps) if steps else (lambda b: b)
