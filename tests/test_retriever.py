"""
RAG retriever — pure filter/transform functions (no network).
"""

from modules.rag.models import NewsItem, SearchBundle
from modules.rag.retriever import (
    _has_cjk,
    _is_blocked_domain,
    build_retrieval_pipeline,
    deduplicate,
    filter_raw_results,
    no_cjk,
    pipe,
    raw_to_news_item,
    raws_to_bundle,
    target_relevance,
    truncate_snippets,
)


def _raw(title="", body="", href="https://example.com/x", target="John Doe",
         category="Web", query="q"):
    return {"title": title, "body": body, "href": href,
            "target": target, "category": category, "query": query}


# ---------------------------------------------------------------------------
# CJK detection
# ---------------------------------------------------------------------------

def test_has_cjk():
    assert _has_cjk("这是中文")
    assert _has_cjk("日本語のテキスト")
    assert _has_cjk("한국어")
    assert not _has_cjk("plain ascii text")
    assert not _has_cjk("acentos português e español")


def test_is_blocked_domain():
    assert _is_blocked_domain("https://www.zhihu.com/question/1")
    assert _is_blocked_domain("http://baidu.com")
    assert not _is_blocked_domain("https://github.com/torvalds")


def test_no_cjk_predicate():
    pred = no_cjk()
    assert pred(raw_to_news_item(_raw(title="Normal English Result")))
    assert not pred(raw_to_news_item(_raw(title="中文标题")))
    assert not pred(raw_to_news_item(_raw(href="https://weibo.com/u/123")))


# ---------------------------------------------------------------------------
# target relevance
# ---------------------------------------------------------------------------

def test_target_relevance_requires_min_words():
    pred = target_relevance(min_words=2)
    hit  = raw_to_news_item(_raw(title="Miguel Sousa arrested", target="Miguel Sousa"))
    miss = raw_to_news_item(_raw(title="Miguel's blog about cats", target="Miguel Sousa"))
    assert pred(hit)
    assert not pred(miss)


def test_target_relevance_lowers_threshold_for_short_targets():
    # single significant word -> required drops to 1
    pred = target_relevance(min_words=2)
    item = raw_to_news_item(_raw(title="torvalds on GitHub", target="torvalds"))
    assert pred(item)


def test_target_relevance_no_significant_words_passes_through():
    pred = target_relevance(min_words=2)
    # target is all short/stopwords -> filter can't apply, keep the item
    item = raw_to_news_item(_raw(title="unrelated", target="de la"))
    assert pred(item)


# ---------------------------------------------------------------------------
# filter_raw_results (used by CLI/GUI before display)
# ---------------------------------------------------------------------------

def test_filter_raw_results_drops_cjk_and_irrelevant():
    rows = [
        _raw(title="John Doe indicted for fraud", target="John Doe"),   # keep
        _raw(title="中文结果", target="John Doe"),                        # drop: CJK
        _raw(title="Someone else entirely", target="John Doe"),          # drop: relevance
    ]
    kept = filter_raw_results(rows, min_target_words=2)
    assert len(kept) == 1
    assert kept[0]["title"].startswith("John Doe")


def test_filter_raw_results_can_disable_filters():
    rows = [_raw(title="中文", target="John Doe")]
    assert filter_raw_results(rows, min_target_words=0, filter_cjk=False) == rows


# ---------------------------------------------------------------------------
# bundle transforms
# ---------------------------------------------------------------------------

def test_deduplicate_by_url():
    b = SearchBundle(
        items=(
            NewsItem("A", "https://x.com/1", "s", "c", "t", "q"),
            NewsItem("B", "https://x.com/1", "s", "c", "t", "q"),
            NewsItem("C", "https://x.com/2", "s", "c", "t", "q"),
        ),
        target="t", timestamp="now",
    )
    out = deduplicate(b)
    assert [i.url for i in out.items] == ["https://x.com/1", "https://x.com/2"]
    # original untouched (immutability)
    assert len(b.items) == 3


def test_truncate_snippets():
    long = "x" * 900
    b = SearchBundle(items=(NewsItem("t", "u", long, "c", "tg", "q"),),
                     target="tg", timestamp="now")
    out = truncate_snippets(500)(b)
    assert len(out.items[0].snippet) == 501           # 500 + the ellipsis char
    assert out.items[0].snippet.endswith("…")
    assert len(b.items[0].snippet) == 900             # original unchanged


def test_pipe_composes_left_to_right():
    f = pipe(lambda x: x + 1, lambda x: x * 3)
    assert f(2) == 9


def test_build_retrieval_pipeline_end_to_end():
    rows = [
        _raw(title="John Doe fraud case", href="https://a.com/1", target="John Doe"),
        _raw(title="John Doe fraud case", href="https://a.com/1", target="John Doe"),  # dup
        _raw(title="中文", href="https://b.com/2", target="John Doe"),                  # cjk
        _raw(title="nothing relevant here", href="https://c.com/3", target="John Doe"),# relevance
    ]
    bundle = raws_to_bundle(rows, "John Doe")
    pipeline = build_retrieval_pipeline(min_target_words=2)
    out = pipeline(bundle)
    assert out.count == 1
    assert out.items[0].url == "https://a.com/1"
