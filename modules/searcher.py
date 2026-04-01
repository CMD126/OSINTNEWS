"""
Search engine module - executes dork queries via DuckDuckGo.

Supports: proxy, time limit, per-result callbacks, status callbacks,
          parallel execution, automatic retry with exponential backoff,
          adaptive rate-limit detection, and search progress tracking.

Upgrades (v2):
  - Adaptive rate-limit detection: detects 429/Ratelimit errors and backs off
    automatically with longer sleep than standard retry
  - Per-worker staggered start delay to prevent thundering-herd on the API
  - Progress counter passed to on_status so GUI can show X/Y percentage
  - Deduplication of results across workers (URL-level) to avoid duplicates
    even when parallel workers query overlapping dorks
  - stop_event support: callers can pass a threading.Event to cancel mid-run
"""

import time
import random
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from ddgs import DDGS
    _DDGS_LEGACY = False
except ImportError:
    # Suppress the noisy "package renamed to ddgs" RuntimeWarning that fires
    # on every single DDGS() instantiation in the old duckduckgo_search package
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning,
                                message=".*renamed.*ddgs.*")
        from duckduckgo_search import DDGS
    _DDGS_LEGACY = True


def _make_ddgs(**kwargs):
    """
    Construct a DDGS instance, suppressing the legacy rename warning
    if the old duckduckgo_search package is installed instead of ddgs.
    Fix: run  pip install ddgs  and  pip uninstall duckduckgo-search
    """
    if _DDGS_LEGACY:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning,
                                    message=".*renamed.*ddgs.*")
            return DDGS(**kwargs)
    return DDGS(**kwargs)


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

_RATELIMIT_SIGNALS = frozenset({
    "ratelimit", "rate limit", "rate_limit", "429", "too many requests",
    "blocked", "temporarily", "403",
})


def _is_ratelimit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(sig in msg for sig in _RATELIMIT_SIGNALS)


def _search_with_retry(
    query:        str,
    max_results:  int,
    timelimit:    str | None,
    proxy:        str | None,
    max_attempts: int   = 3,
    base_delay:   float = 2.0,
    stop_event:   threading.Event | None = None,
) -> list:
    """
    Execute a single DDGS query with exponential backoff on failure.
    Detects rate-limit errors and uses a longer back-off window for those.
    Returns a list of result dicts (may be empty on persistent failure).
    """
    ddgs_kwargs: dict = {}
    if proxy:
        ddgs_kwargs["proxies"] = {"http": proxy, "https": proxy}

    search_kwargs: dict = {"max_results": max_results}
    if timelimit:
        search_kwargs["timelimit"] = timelimit

    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        if stop_event and stop_event.is_set():
            return []
        try:
            with _make_ddgs(**ddgs_kwargs) as ddgs:
                return list(ddgs.text(query, **search_kwargs))
        except Exception as exc:
            last_exc = exc
            if attempt == max_attempts:
                raise

            # Longer back-off for rate-limit errors
            if _is_ratelimit(exc):
                sleep_time = base_delay * (3 ** attempt) + random.uniform(1.0, 3.0)
            else:
                sleep_time = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)

            # Interruptible sleep: wake up early if cancelled
            deadline = time.monotonic() + sleep_time
            while time.monotonic() < deadline:
                if stop_event and stop_event.is_set():
                    return []
                time.sleep(min(0.25, deadline - time.monotonic()))

    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_searches(dorks: list, max_results: int = 10, delay: float = 1.5) -> list:
    """Simple blocking search. Returns all results as a list."""
    return run_searches_with_callback(
        dorks, max_results=max_results, delay=delay
    )


def run_searches_with_callback(
    dorks:        list,
    max_results:  int                      = 10,
    delay:        float                    = 1.0,
    proxy:        str | None               = None,
    timelimit:    str | None               = None,
    on_result                              = None,
    on_status                              = None,
    on_progress                            = None,   # NEW: callable(done, total)
    max_workers:  int                      = 4,
    max_attempts: int                      = 3,
    stop_event:   threading.Event | None   = None,   # NEW: cancellation support
) -> list:
    """
    Execute dork queries in parallel and return all results.

    Parameters
    ----------
    dorks        : list of dork dicts from dorker.build_dorks()
    max_results  : max results per query
    delay        : minimum seconds between queries per worker (polite throttle)
    proxy        : optional proxy URL e.g. "http://127.0.0.1:8080"
    timelimit    : DuckDuckGo time filter — 'd', 'w', 'm', 'y' or None
    on_result    : callable(result_dict) — called for each result in real time
    on_status    : callable(message_str) — called for status updates
    on_progress  : callable(done_count, total_count) — called after each query
    max_workers  : number of parallel search threads (default 4)
    max_attempts : retry attempts per query before giving up (default 3)
    stop_event   : threading.Event — set it to cancel the search cleanly
    """
    all_results: list      = []
    seen_urls:   set[str]  = set()
    lock                   = threading.Lock()
    done_count             = 0
    total                  = len(dorks)

    def _run_one(idx_dork: tuple) -> tuple:
        nonlocal done_count
        idx, dork = idx_dork
        category = dork.get("category", "Unknown")
        query    = dork.get("query",    "")
        target   = dork.get("target",   "")

        # Staggered start: spread workers across the delay window
        # Worker N waits N * (delay / max_workers) before its first request
        stagger = ((idx - 1) % max_workers) * (delay / max(max_workers, 1))
        if stagger > 0:
            if stop_event:
                deadline = time.monotonic() + stagger
                while time.monotonic() < deadline:
                    if stop_event.is_set():
                        return (idx, [], None)
                    time.sleep(min(0.1, deadline - time.monotonic()))
            else:
                time.sleep(stagger)

        # After the first batch, apply normal inter-query delay
        if delay > 0 and idx > max_workers:
            jitter = random.uniform(0, delay * 0.3)
            sleep_time = delay + jitter
            if stop_event:
                deadline = time.monotonic() + sleep_time
                while time.monotonic() < deadline:
                    if stop_event.is_set():
                        return (idx, [], None)
                    time.sleep(min(0.1, deadline - time.monotonic()))
            else:
                time.sleep(sleep_time)

        if stop_event and stop_event.is_set():
            return (idx, [], None)

        if on_status:
            on_status(f"[{idx}/{total}] {category} — {target} …")

        try:
            results = _search_with_retry(
                query, max_results, timelimit, proxy, max_attempts,
                stop_event=stop_event,
            )
            new_results = []
            for r in results:
                r["category"] = category
                r["query"]    = query
                r["target"]   = target
                url = r.get("href", "")
                with lock:
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        new_results.append(r)
                        if on_result:
                            on_result(r)

            if on_status:
                on_status(f"[{idx}/{total}] {category} — {len(new_results)} results")

            with lock:
                done_count += 1
                if on_progress:
                    on_progress(done_count, total)

            return (idx, new_results, None)

        except Exception as exc:
            with lock:
                done_count += 1
                if on_progress:
                    on_progress(done_count, total)
            if on_status:
                on_status(f"[{idx}/{total}] {category} — ERROR: {exc}")
            return (idx, [], str(exc))

    # Submit all dorks to the thread pool
    indexed = list(enumerate(dorks, 1))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_one, item): item for item in indexed}

        for future in as_completed(futures):
            if stop_event and stop_event.is_set():
                # Don't cancel running futures — let them finish their current
                # query so we keep results already in-flight
                pass
            idx, results, error = future.result()
            with lock:
                all_results.extend(results)

    # Sort by original dork order so output is deterministic
    order: dict = {}
    for i, dork in enumerate(dorks):
        cat = dork.get("category", "")
        if cat not in order:
            order[cat] = i
    all_results.sort(key=lambda r: order.get(r.get("category", ""), 999))

    return all_results
