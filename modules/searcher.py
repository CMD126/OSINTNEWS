"""
Search engine module - executes dork queries via DuckDuckGo.
Uses duckduckgo_search library (no API key required).
"""

import time
from duckduckgo_search import DDGS

# ANSI color helpers
_YELLOW = "\033[93m"
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_GREY   = "\033[90m"
_RESET  = "\033[0m"


def run_searches(dorks: list, max_results: int = 10, delay: float = 1.5) -> list:
    """
    Execute each dork query and return all results as a flat list.

    Each result dict contains:
        title, href, body, category, query
    """
    all_results = []

    with DDGS() as ddgs:
        for dork in dorks:
            category = dork["category"]
            query    = dork["query"]

            print(f"\n  {_YELLOW}[~]{_RESET} {category}")
            print(f"      {_GREY}Query: {query[:80]}{'...' if len(query) > 80 else ''}{_RESET}")

            try:
                results = list(ddgs.text(query, max_results=max_results))

                for r in results:
                    r["category"] = category
                    r["query"]    = query

                all_results.extend(results)
                print(f"      {_GREEN}[+]{_RESET} {len(results)} result(s) found")

            except Exception as exc:
                print(f"      {_RED}[!]{_RESET} Error: {exc}")

            # polite delay to avoid rate limiting
            time.sleep(delay)

    return all_results
