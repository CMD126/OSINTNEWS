"""
OSINTNEWS - OSINT News Intelligence Tool
Search actual news about any target using Google dorking techniques.
"""

import sys
import argparse

from modules.dorker   import DORK_CATEGORIES, build_dorks
from modules.searcher import run_searches
from modules.reporter import print_results, save_report

# ---------------------------------------------------------------------------
# ANSI colors (works on Windows 10+ with ANSI enabled via colorama init or
# Windows Terminal / newer cmd.exe)
# ---------------------------------------------------------------------------
try:
    import colorama
    colorama.init()
except ImportError:
    pass  # colors will still work in Windows Terminal / VS Code

_GREEN  = "\033[92m"
_CYAN   = "\033[96m"
_YELLOW = "\033[93m"
_GREY   = "\033[90m"
_WHITE  = "\033[97m"
_RED    = "\033[91m"
_RESET  = "\033[0m"

BANNER = f"""
{_GREEN}
  ██████╗ ███████╗██╗███╗   ██╗████████╗███╗   ██╗███████╗██╗    ██╗███████╗
 ██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝████╗  ██║██╔════╝██║    ██║██╔════╝
 ██║   ██║███████╗██║██╔██╗ ██║   ██║   ██╔██╗ ██║█████╗  ██║ █╗ ██║███████╗
 ██║   ██║╚════██║██║██║╚██╗██║   ██║   ██║╚██╗██║██╔══╝  ██║███╗██║╚════██║
 ╚██████╔╝███████║██║██║ ╚████║   ██║   ██║ ╚████║███████╗╚███╔███╔╝███████║
  ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═══╝╚══════╝ ╚══╝╚══╝ ╚══════╝
{_RESET}  {_CYAN}OSINT News Intelligence Tool{_RESET}  |  {_YELLOW}Google Dorking Engine{_RESET}
  {_GREY}For educational and authorized use only{_RESET}
"""


# ---------------------------------------------------------------------------
# Interactive category selection
# ---------------------------------------------------------------------------

def select_categories() -> list:
    print(f"\n{_CYAN}  Available Dork Categories:{_RESET}\n")
    for key, cat in DORK_CATEGORIES.items():
        print(f"    {_YELLOW}[{key:>2}]{_RESET}  {cat['name']:35s}  {_GREY}{cat['description']}{_RESET}")
    print(f"    {_YELLOW}[ A]{_RESET}  All categories\n")

    print(f"  {_CYAN}Select categories (e.g.  1,3,5  or  A  for all):{_RESET} ", end="")
    choice = input().strip().upper()

    if not choice or choice == "A":
        return list(DORK_CATEGORIES.keys())

    selected = [c.strip() for c in choice.split(",") if c.strip() in DORK_CATEGORIES]

    if not selected:
        print(f"  {_RED}[!] Invalid selection — running all categories.{_RESET}")
        return list(DORK_CATEGORIES.keys())

    return selected


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="OSINTNEWS — OSINT News via Google Dorking",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-t", "--target",
        help="Target to search (person, company, topic, keyword)",
    )
    parser.add_argument(
        "-c", "--categories",
        help="Dork categories to run, comma-separated (e.g. 1,2,4) or A for all",
    )
    parser.add_argument(
        "-m", "--max-results",
        type=int, default=10,
        help="Maximum results per category (default: 10)",
    )
    parser.add_argument(
        "-o", "--output",
        default="reports",
        help="Output directory for the HTML report (default: reports/)",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip HTML report generation — print only",
    )
    parser.add_argument(
        "--delay",
        type=float, default=1.5,
        help="Delay in seconds between queries to avoid rate limiting (default: 1.5)",
    )

    args = parser.parse_args()

    # --- Target ---
    if args.target:
        target = args.target.strip()
    else:
        print(f"  {_CYAN}Enter target (name, company, topic):{_RESET} ", end="")
        target = input().strip()

    if not target:
        print(f"\n{_RED}[!] No target provided. Exiting.{_RESET}")
        sys.exit(1)

    print(f"\n  {_GREEN}[*]{_RESET} Target   : {_WHITE}{target}{_RESET}")

    # --- Categories ---
    if args.categories:
        if args.categories.strip().upper() == "A":
            selected = list(DORK_CATEGORIES.keys())
        else:
            selected = [c.strip() for c in args.categories.split(",") if c.strip() in DORK_CATEGORIES]
        if not selected:
            print(f"  {_RED}[!] No valid categories — running all.{_RESET}")
            selected = list(DORK_CATEGORIES.keys())
    else:
        selected = select_categories()

    print(f"  {_GREEN}[*]{_RESET} Categories: {_WHITE}{len(selected)}{_RESET} selected")
    print(f"  {_GREEN}[*]{_RESET} Max results per category: {_WHITE}{args.max_results}{_RESET}")
    print(f"  {_GREEN}[*]{_RESET} Query delay : {_WHITE}{args.delay}s{_RESET}")

    # --- Build dorks ---
    dorks = build_dorks(target, selected)

    print(f"\n  {_GREEN}[*]{_RESET} Starting {len(dorks)} dork quer{'y' if len(dorks)==1 else 'ies'}...")
    print(f"  {_GREY}{'─' * 60}{_RESET}")

    # --- Run searches ---
    results = run_searches(dorks, max_results=args.max_results, delay=args.delay)

    # --- Print to terminal ---
    print_results(results, target)

    # --- Save HTML report ---
    if not args.no_report:
        if results:
            report_path = save_report(results, target, args.output)
            print(f"\n{_GREEN}[+]{_RESET} HTML report saved: {_CYAN}{report_path}{_RESET}")
        else:
            print(f"\n{_YELLOW}[~]{_RESET} No results to write to report.")

    print(f"\n{_GREEN}[+]{_RESET} Done. Total results: {_WHITE}{len(results)}{_RESET}\n")


if __name__ == "__main__":
    main()
