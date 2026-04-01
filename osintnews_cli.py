"""
OSINTNEWS — OSINT Identity CLI
================================
Search social media, forums, leaks and directories for:
  • Usernames / handles
  • Email addresses
  • Phone numbers
  • Full person names

Run:
  python osintnews.py --cli
  python osintnews_cli.py
  python osintnews_cli.py --mode username --target johndoe
  python osintnews_cli.py --mode email    --target john@example.com
  python osintnews_cli.py --mode phone    --target "+1 555 123 4567"
  python osintnews_cli.py --mode person   --target "John Doe"
"""

import sys
import os
import argparse
import time
import json
import csv

# ── Auto-installer ────────────────────────────────────────────────────────────
try:
    from modules.installer import ensure_dependencies
    ensure_dependencies()
except Exception as _e:
    print(f"[setup] Auto-install skipped: {_e}", flush=True)
# ─────────────────────────────────────────────────────────────────────────────

from modules.dorker_osint   import OSINT_CATEGORIES, OSINT_MODES, categories_for_mode, build_osint_dorks
from modules.searcher        import run_searches_with_callback
from modules.rag.retriever   import filter_raw_results

try:
    import colorama
    colorama.init()
except ImportError:
    pass

# ── ANSI colours ─────────────────────────────────────────────────────────────
G = "\033[92m"   # green
C = "\033[96m"   # cyan
Y = "\033[93m"   # yellow
B = "\033[94m"   # blue
W = "\033[97m"   # white
D = "\033[90m"   # dark / grey
R = "\033[91m"   # red
P = "\033[95m"   # purple
X = "\033[0m"    # reset

BANNER = f"""
{G}
   ██████╗ ███████╗██╗███╗   ██╗████████╗     ██████╗██╗     ██╗
  ██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝    ██╔════╝██║     ██║
  ██║   ██║███████╗██║██╔██╗ ██║   ██║       ██║     ██║     ██║
  ██║   ██║╚════██║██║██║╚██╗██║   ██║       ██║     ██║     ██║
  ╚██████╔╝███████║██║██║ ╚████║   ██║       ╚██████╗███████╗██║
   ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝        ╚═════╝╚══════╝╚═╝
{X}  {C}OSINT Identity & Social Intelligence Tool{X}
  {D}Usernames · Emails · Phones · People{X}
"""

MODE_LABELS = {
    "username": f"{C}👤 Username{X}",
    "email":    f"{Y}✉  Email{X}",
    "phone":    f"{G}📞 Phone{X}",
    "person":   f"{P}🔍 Person{X}",
}

MODE_COLORS = {
    "username": C,
    "email":    Y,
    "phone":    G,
    "person":   P,
}


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------

def pick_mode() -> str:
    print(f"\n{C}  Search mode:{X}\n")
    items = list(OSINT_MODES.items())
    for i, (key, label) in enumerate(items, 1):
        print(f"    {Y}[{i}]{X}  {label}")
    print(f"\n  {C}Enter number:{X} ", end="")
    raw = input().strip()
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(items):
            return items[idx][0]
    except ValueError:
        pass
    return "username"


def pick_categories(mode: str) -> list:
    cats = categories_for_mode(mode)
    color = MODE_COLORS.get(mode, C)
    print(f"\n{color}  Categories for {OSINT_MODES[mode]}:{X}\n")
    for key, cat in cats.items():
        print(f"    {Y}[{key:>3}]{X}  {cat['name']:35s}  {D}{cat['description']}{X}")
    print(f"    {Y}[  A]{X}  All categories\n")
    print(f"  {C}Select (e.g. U1,U3  or  A for all):{X} ", end="")
    choice = input().strip().upper()

    all_keys = list(cats.keys())
    if not choice or choice == "A":
        return all_keys
    sel = [c.strip() for c in choice.split(",") if c.strip() in cats]
    return sel if sel else all_keys


# ---------------------------------------------------------------------------
# Output / display
# ---------------------------------------------------------------------------

def _risk_color(risk: str) -> str:
    return {"LOW": G, "MEDIUM": Y, "HIGH": R, "CRITICAL": R}.get(risk, D)


def print_results(results: list, target: str, mode: str) -> None:
    if not results:
        print(f"\n{R}  [!] No results found for: {target}{X}")
        return

    color = MODE_COLORS.get(mode, C)
    cats: dict = {}
    for r in results:
        cats.setdefault(r.get("category", "Unknown"), []).append(r)

    print(f"\n{color}{'═' * 70}{X}")
    print(f"{color}  {OSINT_MODES.get(mode, mode)}: {W}{target}{X}"
          f"  {D}|{X}  {W}{len(results)}{X} results  {D}across {len(cats)} sources{X}")
    print(f"{color}{'═' * 70}{X}")

    idx = 1
    for cat, items in cats.items():
        print(f"\n{Y}  ▸ {cat}{X}  {D}({len(items)}){X}")
        print(f"  {D}{'─' * 60}{X}")
        for r in items:
            title   = r.get("title", "No title")
            url     = r.get("href",  "")
            body    = (r.get("body", "") or "")
            snippet = (body[:180] + "…") if len(body) > 180 else body

            print(f"\n  {D}{idx}.{X} {W}{title}{X}")
            print(f"     {B}{url}{X}")
            if snippet:
                print(f"     {D}{snippet}{X}")
            idx += 1


def save_results(results: list, target: str, mode: str,
                 output_dir: str, fmt: str = "json") -> str:
    os.makedirs(output_dir, exist_ok=True)
    safe   = "".join(c if c.isalnum() or c in "-_" else "_" for c in target)
    ts     = time.strftime("%Y%m%d_%H%M%S")
    path   = os.path.join(output_dir, f"osint_{mode}_{safe}_{ts}.{fmt}")

    if fmt == "json":
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"target": target, "mode": mode,
                       "count": len(results), "results": results},
                      fh, indent=2, ensure_ascii=False)

    elif fmt == "csv":
        fields = ["category", "title", "href", "body", "query"]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)

    elif fmt == "txt":
        cats: dict = {}
        for r in results:
            cats.setdefault(r.get("category", "Unknown"), []).append(r)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"OSINT Report — {OSINT_MODES.get(mode, mode)}: {target}\n")
            fh.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            fh.write("=" * 70 + "\n\n")
            for cat, items in cats.items():
                fh.write(f"\n▸ {cat} ({len(items)})\n")
                fh.write("─" * 60 + "\n")
                for i, r in enumerate(items, 1):
                    fh.write(f"\n{i}. {r.get('title', 'No title')}\n")
                    fh.write(f"   {r.get('href', '')}\n")
                    body = (r.get("body", "") or "")[:200]
                    if body:
                        fh.write(f"   {body}\n")
    return path


# ---------------------------------------------------------------------------
# AI analysis (optional, reuses RAG pipeline)
# ---------------------------------------------------------------------------

def run_ai(results: list, target: str, mode: str,
           provider: str, api_key: str, model: str,
           max_tokens: int, ollama_url: str, ollama_model: str) -> None:
    if not results:
        print(f"\n{R}[!] No results to analyse.{X}")
        return

    print(f"\n{P}[AI]{X} Running intelligence analysis via {W}{provider}{X}…")
    try:
        from modules.rag.pipeline import run_pipeline

        def on_token(chunk):
            print(chunk, end="", flush=True)

        result = run_pipeline(
            raw_results  = results,
            target       = target,
            provider     = provider,
            api_key      = api_key,
            model        = model,
            max_tokens   = max_tokens,
            ollama_url   = ollama_url,
            ollama_model = ollama_model,
            on_token     = on_token if provider in ("claude", "openai", "gemini", "ollama") else None,
        )

        analysis  = result.analysis
        risk_col  = _risk_color(analysis.risk_level)

        if provider not in ("claude", "openai", "gemini", "ollama"):
            print(analysis.summary)

        print(f"\n\n{risk_col}{'═' * 60}{X}")
        print(f"{risk_col}  Risk Level : {analysis.risk_level}{X}")
        print(f"{D}  Model      : {analysis.model}{X}")
        print(f"{D}  Sources    : {analysis.source_count} analysed  ·  "
              f"{len(analysis.cited_sources)} cited{X}")
        if analysis.cited_sources:
            print(f"\n{C}  Cited Sources:{X}")
            for i, url in enumerate(analysis.cited_sources, 1):
                print(f"    {D}[{i}]{X} {B}{url}{X}")
        print(f"{risk_col}{'═' * 60}{X}")

    except Exception as exc:
        print(f"\n{R}[!] AI error: {exc}{X}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(BANNER)

    _root = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(_root, "data"),    exist_ok=True)
    os.makedirs(os.path.join(_root, "reports"), exist_ok=True)

    parser = argparse.ArgumentParser(
        description="OSINTNEWS CLI — OSINT Identity Search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python osintnews_cli.py --mode username --target johndoe
  python osintnews_cli.py --mode email    --target john@example.com
  python osintnews_cli.py --mode phone    --target "+1 555 123 4567"
  python osintnews_cli.py --mode person   --target "John Doe"
  python osintnews_cli.py --mode username --target hacker99 --ai --provider claude
        """,
    )

    # ── Target & mode ──
    parser.add_argument("-t", "--target",     help="Search target")
    parser.add_argument("-m", "--mode",
                        choices=["username", "email", "phone", "person"],
                        help="Search mode (username / email / phone / person)")
    parser.add_argument("-c", "--categories", help="Categories (e.g. U1,U3 or A)")

    # ── Search options ──
    parser.add_argument("--max-results",  type=int,   default=10,
                        help="Max results per category (default: 10)")
    parser.add_argument("--delay",        type=float, default=1.0,
                        help="Seconds between queries (default: 1.0)")
    parser.add_argument("--workers",      type=int,   default=4,
                        help="Parallel search workers (default: 4)")
    parser.add_argument("--no-save",      action="store_true",
                        help="Do not save results to file")
    parser.add_argument("--format",       default="json",
                        choices=["json", "csv", "txt"],
                        help="Output format (default: json)")
    parser.add_argument("-o", "--output", default="reports",
                        help="Output directory (default: reports)")

    # ── AI options ──
    parser.add_argument("--ai",           action="store_true",
                        help="Run AI intelligence analysis on results")
    parser.add_argument("--provider",     default="claude",
                        choices=["claude", "openai", "gemini", "ollama"],
                        help="AI provider (default: claude)")
    parser.add_argument("--api-key",      default="",
                        help="API key (or set ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY)")
    parser.add_argument("--model",        default="",
                        help="Model name (blank = provider default)")
    parser.add_argument("--max-tokens",   type=int, default=4000,
                        help="Max AI output tokens (default: 4000)")
    parser.add_argument("--ollama-url",   default="http://localhost:11434")
    parser.add_argument("--ollama-model", default="llama3.2")

    args = parser.parse_args()

    # ── Resolve API key from env ──
    if not args.api_key:
        env_map = {
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
        }
        env_name = env_map.get(args.provider, "")
        if env_name:
            args.api_key = os.environ.get(env_name, "")

    # ── Interactive: pick mode ──
    if args.mode:
        mode = args.mode
    else:
        mode = pick_mode()

    print(f"\n  {G}[*]{X} Mode     : {MODE_LABELS.get(mode, mode)}")

    # ── Interactive: pick target ──
    if args.target:
        target = args.target.strip()
    else:
        color = MODE_COLORS.get(mode, C)
        prompts = {
            "username": "Username / handle",
            "email":    "Email address",
            "phone":    "Phone number (with country code)",
            "person":   "Full name",
        }
        print(f"\n  {color}{prompts.get(mode, 'Target')}:{X} ", end="")
        target = input().strip()

    if not target:
        print(f"\n{R}[!] No target provided. Exiting.{X}")
        sys.exit(1)

    print(f"  {G}[*]{X} Target   : {W}{target}{X}")

    # ── Pick categories ──
    cats_for_mode = categories_for_mode(mode)
    if args.categories:
        if args.categories.upper() == "A":
            sel = list(cats_for_mode.keys())
        else:
            sel = [c.strip() for c in args.categories.split(",")
                   if c.strip() in cats_for_mode]
            if not sel:
                print(f"  {R}[!] Invalid categories — using all.{X}")
                sel = list(cats_for_mode.keys())
    else:
        sel = pick_categories(mode)

    if not sel:
        print(f"\n{R}[!] No categories selected. Exiting.{X}")
        sys.exit(1)

    print(f"  {G}[*]{X} Sources  : {W}{len(sel)}{X} categories")
    print(f"  {G}[*]{X} Workers  : {W}{args.workers}{X} parallel")

    # ── Build & run dorks ──
    dorks = build_osint_dorks(target, sel)
    print(f"\n  {G}[*]{X} Running {W}{len(dorks)}{X} queries…")
    print(f"  {D}{'─' * 60}{X}")

    t0 = time.perf_counter()

    def on_status(msg):
        print(f"  {D}{msg}{X}")

    results = run_searches_with_callback(
        dorks,
        max_results = args.max_results,
        delay       = args.delay,
        max_workers = args.workers,
        on_status   = on_status,
    )

    elapsed = time.perf_counter() - t0

    # ── Filter irrelevant results ──
    raw_count = len(results)
    results   = filter_raw_results(results, min_target_words=1)
    filtered  = raw_count - len(results)

    print(f"\n  {D}{'─' * 60}{X}")
    print(f"  {G}[✓]{X} Done in {W}{elapsed:.1f}s{X}  ·  "
          f"{W}{len(results)}{X} results", end="")
    if filtered:
        print(f"  {D}({filtered} irrelevant filtered){X}")
    else:
        print()

    # ── Display ──
    print_results(results, target, mode)

    # ── Save ──
    if not args.no_save and results:
        out_dir = args.output
        if not os.path.isabs(out_dir):
            out_dir = os.path.join(_root, out_dir)
        path = save_results(results, target, mode, out_dir, args.format)
        print(f"\n{G}[+]{X} Saved  : {C}{path}{X}")

    # ── AI analysis ──
    if args.ai:
        if args.provider in ("claude", "openai", "gemini") and not args.api_key:
            print(f"\n{R}[!] --api-key required for '{args.provider}'.{X}")
        else:
            run_ai(
                results      = results,
                target       = target,
                mode         = mode,
                provider     = args.provider,
                api_key      = args.api_key,
                model        = args.model,
                max_tokens   = args.max_tokens,
                ollama_url   = args.ollama_url,
                ollama_model = args.ollama_model,
            )

    print(f"\n{G}[+]{X} Total: {W}{len(results)}{X} results  ·  {W}{elapsed:.1f}s{X}\n")


if __name__ == "__main__":
    main()
