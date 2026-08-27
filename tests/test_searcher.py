"""
Search engine — retry/error classifiers, interruptible sleep, and the
parallel orchestration in run_searches_with_callback (DDGS stubbed out, so
no network access).
"""

import threading
import time

import pytest

import modules.searcher as searcher
from modules.searcher import (
    DDGSException,
    RatelimitException,
    TimeoutException,
    _interruptible_sleep,
    _is_no_results,
    _is_ratelimit,
    run_searches_with_callback,
)


# ---------------------------------------------------------------------------
# classifiers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exc", [
    RatelimitException("hit the limit"),
    Exception("HTTP 429 Too Many Requests"),
    Exception("403 blocked"),
    Exception("Ratelimit, try again later"),
])
def test_is_ratelimit_true(exc):
    assert _is_ratelimit(exc)


@pytest.mark.parametrize("exc", [
    Exception("connection reset"),
    DDGSException("No results found."),
    TimeoutException("read timed out"),
])
def test_is_ratelimit_false(exc):
    assert not _is_ratelimit(exc)


@pytest.mark.parametrize("exc, expected", [
    (DDGSException("No results found."), True),
    (Exception("no results"), True),
    (Exception("some other failure"), False),
    (RatelimitException("429"), False),
])
def test_is_no_results(exc, expected):
    assert _is_no_results(exc) is expected


# ---------------------------------------------------------------------------
# interruptible sleep
# ---------------------------------------------------------------------------

def test_interruptible_sleep_runs_full_duration():
    start = time.monotonic()
    _interruptible_sleep(0.3)
    assert 0.25 <= time.monotonic() - start < 1.0


def test_interruptible_sleep_wakes_early_on_event():
    ev = threading.Event()
    threading.Timer(0.1, ev.set).start()
    start = time.monotonic()
    _interruptible_sleep(5.0, ev)
    assert time.monotonic() - start < 1.0


# ---------------------------------------------------------------------------
# run_searches_with_callback — orchestration with DDGS stubbed
# ---------------------------------------------------------------------------

@pytest.fixture
def stub_search(monkeypatch):
    """Replace _search_with_retry with a canned, offline responder."""
    calls = []

    def fake(query, max_results, timelimit, proxy, max_attempts, **kw):
        calls.append(query)
        if "boom" in query:
            raise RuntimeError("simulated backend failure")
        if "empty" in query:
            return []
        # two rows, one of them a cross-query duplicate URL
        return [
            {"title": f"r for {query}", "href": "https://dup.example/1", "body": "b"},
            {"title": f"r2 for {query}", "href": f"https://uniq.example/{len(calls)}", "body": "b"},
        ]

    monkeypatch.setattr(searcher, "_search_with_retry", fake)
    return calls


def _dorks(*queries):
    return [{"category": f"C{i}", "query": q, "target": "t"}
            for i, q in enumerate(queries, 1)]


def test_dedupes_urls_across_queries(stub_search):
    out = run_searches_with_callback(_dorks("alpha", "beta"), delay=0, max_workers=2)
    hrefs = [r["href"] for r in out]
    assert hrefs.count("https://dup.example/1") == 1          # deduped
    assert len(out) == 3                                       # 1 shared + 2 unique


def test_enriches_rows_with_category_and_target(stub_search):
    out = run_searches_with_callback(_dorks("alpha"), delay=0, max_workers=1)
    assert all(r["target"] == "t" for r in out)
    assert {r["category"] for r in out} == {"C1"}


def test_one_failing_query_does_not_kill_the_run(stub_search):
    out = run_searches_with_callback(
        _dorks("good", "boom", "alsogood"), delay=0, max_workers=3,
    )
    # 'boom' raises, the other two still return their unique rows + shared url
    assert len(out) >= 3
    assert any("good" in r["title"] for r in out)


def test_progress_and_status_callbacks_fire(stub_search):
    seen = {"progress": [], "status": 0}
    run_searches_with_callback(
        _dorks("a", "b", "empty"), delay=0, max_workers=2,
        on_progress=lambda d, t: seen["progress"].append((d, t)),
        on_status=lambda m: seen.__setitem__("status", seen["status"] + 1),
    )
    assert seen["progress"][-1] == (3, 3)
    assert seen["status"] > 0


def test_stop_event_short_circuits(stub_search):
    ev = threading.Event()
    ev.set()
    out = run_searches_with_callback(_dorks("a", "b"), delay=0, stop_event=ev)
    assert out == []


def test_empty_dork_list_returns_empty(stub_search):
    assert run_searches_with_callback([], delay=0) == []
