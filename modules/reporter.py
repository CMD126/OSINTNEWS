"""
Reporter module - handles terminal output and HTML report generation.
"""

import os
import html as html_lib
from datetime import datetime

# ANSI colors
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_BLUE   = "\033[94m"
_WHITE  = "\033[97m"
_GREY   = "\033[90m"
_RED    = "\033[91m"
_RESET  = "\033[0m"


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------

def print_results(results: list, target: str) -> None:
    """Print all results to the terminal, grouped by category."""
    if not results:
        print(f"\n{_RED}[!] No results found.{_RESET}")
        return

    print(f"\n{_GREEN}{'=' * 70}{_RESET}")
    print(f"{_CYAN}  Results for: {_WHITE}{target}{_CYAN}  |  Total: {_WHITE}{len(results)}{_RESET}")
    print(f"{_GREEN}{'=' * 70}{_RESET}")

    current_cat = None
    idx = 1

    for r in results:
        cat = r.get("category", "Unknown")

        if cat != current_cat:
            current_cat = cat
            print(f"\n{_YELLOW}  [{cat}]{_RESET}")
            print(f"  {_GREY}{'─' * 60}{_RESET}")

        title = r.get("title", "No title")
        url   = r.get("href",  "")
        body  = r.get("body",  "")

        snippet = (body[:150] + "...") if len(body) > 150 else body

        print(f"\n  {_WHITE}{idx}. {title}{_RESET}")
        print(f"     {_BLUE}{url}{_RESET}")
        if snippet:
            print(f"     {_GREY}{snippet}{_RESET}")

        idx += 1


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def save_report(results: list, target: str, output_dir: str = "reports") -> str:
    """Generate a dark-themed HTML report and return the file path."""
    os.makedirs(output_dir, exist_ok=True)

    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name  = "".join(c if c.isalnum() or c in "-_" else "_" for c in target)
    filename   = os.path.join(output_dir, f"osintnews_{safe_name}_{timestamp}.html")

    with open(filename, "w", encoding="utf-8") as fh:
        fh.write(_generate_html(results, target, timestamp))

    return filename


def _generate_html(results: list, target: str, timestamp: str) -> str:
    # Group results by category
    categories: dict = {}
    for r in results:
        cat = r.get("category", "Uncategorized")
        categories.setdefault(cat, []).append(r)

    # Build cards HTML
    cards_html = ""
    for cat, items in categories.items():
        cards_html += f"""
        <section class="cat-section">
            <h2 class="cat-title">{html_lib.escape(cat)} <span class="badge">{len(items)}</span></h2>
            <div class="cards">
        """
        for item in items:
            title   = html_lib.escape(item.get("title", "No title"))
            url     = html_lib.escape(item.get("href",  "#"))
            body    = html_lib.escape(item.get("body",  "")[:300])
            query   = html_lib.escape(item.get("query", ""))

            cards_html += f"""
                <article class="card">
                    <a class="card-title" href="{url}" target="_blank" rel="noopener">{title}</a>
                    <div class="card-url">{url}</div>
                    <div class="card-body">{body}</div>
                    <span class="card-query">{query}</span>
                </article>
            """
        cards_html += "</div></section>"

    safe_target = html_lib.escape(target)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OSINTNEWS &mdash; {safe_target}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: #0d1117;
    color: #c9d1d9;
    font-family: 'Segoe UI', system-ui, sans-serif;
    padding: 24px;
    line-height: 1.6;
  }}

  header {{
    border-bottom: 1px solid #30363d;
    padding-bottom: 20px;
    margin-bottom: 32px;
  }}

  header h1 {{
    font-size: 1.9rem;
    color: #58a6ff;
    letter-spacing: -0.5px;
  }}

  .meta {{
    color: #8b949e;
    font-size: 0.88rem;
    margin-top: 6px;
  }}

  .meta strong {{ color: #e6edf3; }}

  .stats {{
    display: flex;
    gap: 16px;
    margin-top: 16px;
    flex-wrap: wrap;
  }}

  .stat {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 20px;
    min-width: 110px;
  }}

  .stat-num   {{ font-size: 1.6rem; color: #3fb950; font-weight: 700; }}
  .stat-label {{ font-size: 0.75rem; color: #8b949e; }}

  .cat-section {{ margin-bottom: 44px; }}

  .cat-title {{
    font-size: 1.1rem;
    color: #f78166;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .badge {{
    background: #21262d;
    color: #8b949e;
    font-size: 0.72rem;
    padding: 2px 8px;
    border-radius: 20px;
    font-weight: 400;
  }}

  .cards {{ display: grid; gap: 12px; }}

  .card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px;
    transition: border-color 0.18s;
  }}

  .card:hover {{ border-color: #58a6ff; }}

  .card-title {{
    display: block;
    color: #58a6ff;
    font-size: 0.97rem;
    font-weight: 600;
    text-decoration: none;
    margin-bottom: 5px;
  }}

  .card-title:hover {{ color: #79c0ff; text-decoration: underline; }}

  .card-url {{
    color: #3fb950;
    font-size: 0.72rem;
    margin-bottom: 8px;
    word-break: break-all;
  }}

  .card-body {{
    color: #8b949e;
    font-size: 0.86rem;
    margin-bottom: 8px;
  }}

  .card-query {{
    display: block;
    background: #1c2128;
    border: 1px solid #30363d;
    color: #6e7681;
    font-size: 0.68rem;
    font-family: 'Consolas', monospace;
    padding: 4px 8px;
    border-radius: 4px;
    word-break: break-all;
  }}

  footer {{
    border-top: 1px solid #30363d;
    padding-top: 20px;
    margin-top: 40px;
    color: #484f58;
    font-size: 0.78rem;
    text-align: center;
  }}
</style>
</head>
<body>
<header>
  <h1>&#128269; OSINTNEWS</h1>
  <div class="meta">
    Target: <strong>{safe_target}</strong> &nbsp;&bull;&nbsp; Generated: {timestamp}
  </div>
  <div class="stats">
    <div class="stat">
      <div class="stat-num">{len(results)}</div>
      <div class="stat-label">Total Results</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(categories)}</div>
      <div class="stat-label">Categories</div>
    </div>
  </div>
</header>

{cards_html}

<footer>Generated by OSINTNEWS &mdash; For educational and authorized use only</footer>
</body>
</html>
"""
