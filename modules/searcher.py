"""
Search engine module - executes dork queries via DuckDuckGo.
Supports: proxy, time limit, per-result callbacks, status callbacks.
"""

import time
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


def run_searches(dorks: list, max_results: int = 10, delay: float = 1.5) -> list:
    """Simple blocking search. Returns all results as a list."""
    return run_searches_with_callback(
        dorks, max_results=max_results, delay=delay
    )


def run_searches_with_callback(
    dorks: list,
    max_results: int = 10,
    delay: float = 1.5,
    proxy: str | None = None,
    timelimit: str | None = None,
    on_result=None,
    on_status=None,
) -> list:
    """
    Execute dork queries and return all results.

    Parameters
    ----------
    dorks       : list of dork dicts from dorker.build_dorks()
    max_results : max results per query
    delay       : seconds between queries (polite throttle)
    proxy       : optional proxy URL e.g. "http://127.0.0.1:8080"
    timelimit   : DuckDuckGo time filter — 'd', 'w', 'm', 'y' or None
    on_result   : callable(result_dict) — called for each result in real time
    on_status   : callable(message_str) — called for status updates
    """
    all_results: list = []

    ddgs_kwargs = {}
    if proxy:
        ddgs_kwargs["proxies"] = {"http": proxy, "https": proxy}

    with DDGS(**ddgs_kwargs) as ddgs:
        for i, dork in enumerate(dorks, 1):
            category = dork.get("category", "Unknown")
            query    = dork.get("query", "")
            target   = dork.get("target", "")

            if on_status:
                on_status(f"[{i}/{len(dorks)}] {category} — {target}")

            try:
                search_kwargs = {"max_results": max_results}
                if timelimit:
                    search_kwargs["timelimit"] = timelimit

                results = list(ddgs.text(query, **search_kwargs))

                for r in results:
                    r["category"] = category
                    r["query"]    = query
                    r["target"]   = target
                    all_results.append(r)
                    if on_result:
                        on_result(r)

                if on_status:
                    on_status(f"[{i}/{len(dorks)}] {category} — {len(results)} results")

            except Exception as exc:
                if on_status:
                    on_status(f"[{i}/{len(dorks)}] {category} — ERROR: {exc}")

            if i < len(dorks):
                time.sleep(delay)

    return all_results
