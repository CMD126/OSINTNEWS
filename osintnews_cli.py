"""
OSINTNEWS — CLI mode.
Run: python osintnews.py --cli
     python osintnews_cli.py
"""

import sys
import argparse

from modules.dorker   import DORK_CATEGORIES, build_dorks
from modules.searcher import run_searches
from modules.reporter import print_results, save_report

try:
    import colorama
    colorama.init()
except ImportError:
    pass

G = "\033[92m"
C = "\033[96m"
Y = "\033[93m"
B = "\033[94m"
W = "\033[97m"
D = "\033[90m"
R = "\033[91m"
X = "\033[0m"

BANNER = f"""
{G}
  ██████╗ ███████╗██╗███╗   ██╗████████╗███╗   ██╗███████╗██╗    ██╗███████╗
 ██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝████╗  ██║██╔════╝██║    ██║██╔════╝
 ██║   ██║███████╗██║██╔██╗ ██║   ██║   ██╔██╗ ██║█████╗  ██║ █╗ ██║███████╗
 ██║   ██║╚════██║██║██║╚██╗██║   ██║   ██║╚██╗██║██╔══╝  ██║███╗██║╚════██║
 ╚██████╔╝███████║██║██║ ╚████║   ██║   ██║ ╚████║███████╗╚███╔███╔╝███████║
  ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═══╝╚══════╝ ╚══╝╚══╝ ╚══════╝
{X}  {C}OSINT News Intelligence Tool{X}  |  {Y}Google Dorking Engine{X}
"""


def pick_categories() -> list:
    print(f"\n{C}  Categories:{X}\n")
    for key, cat in DORK_CATEGORIES.items():
        print(f"    {Y}[{key:>2}]{X}  {cat['name']:35s}  {D}{cat['description']}{X}")
    print(f"    {Y}[ A]{X}  All categories\n")
    print(f"  {C}Select (e.g. 1,3,5  or  A for all):{X} ", end="")
    choice = input().strip().upper()

    if not choice or choice == "A":
        return list(DORK_CATEGORIES.keys())

    sel = [c.strip() for c in choice.split(",") if c.strip() in DORK_CATEGORIES]
    if not sel:
        print(f"  {R}[!] Invalid — using all.{X}")
        return list(DORK_CATEGORIES.keys())
    return sel


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(description="OSINTNEWS CLI")
    parser.add_argument("-t", "--target",      help="Target(s), comma-separated")
    parser.add_argument("-c", "--categories",  help="Categories (e.g. 1,2,4 or A)")
    parser.add_argument("-m", "--max-results", type=int, default=10)
    parser.add_argument("-o", "--output",      default="reports")
    parser.add_argument("--no-report",         action="store_true")
    parser.add_argument("--delay",             type=float, default=1.5)
    args = parser.parse_args()

    # Targets
    if args.target:
        targets = [t.strip() for t in args.target.split(",") if t.strip()]
    else:
        print(f"  {C}Target(s) (comma-separated):{X} ", end="")
        targets = [t.strip() for t in input().split(",") if t.strip()]

    if not targets:
        print(f"\n{R}[!] No target. Exiting.{X}")
        sys.exit(1)

    print(f"\n  {G}[*]{X} Targets: {W}{', '.join(targets)}{X}")

    # Categories
    if args.categories:
        sel = list(DORK_CATEGORIES.keys()) if args.categories.upper() == "A" else \
              [c.strip() for c in args.categories.split(",") if c.strip() in DORK_CATEGORIES]
    else:
        sel = pick_categories()

    print(f"  {G}[*]{X} Categories: {W}{len(sel)}{X}")
    print(f"  {G}[*]{X} Max results : {W}{args.max_results}{X}")

    # Build dorks
    all_dorks = []
    for t in targets:
        all_dorks.extend(build_dorks(t, sel))

    print(f"\n  {G}[*]{X} Running {W}{len(all_dorks)}{X} queries…\n  {D}{'─'*60}{X}")

    results = run_searches(all_dorks, max_results=args.max_results, delay=args.delay)

    for t in targets:
        subset = [r for r in results if r.get("target") == t]
        print_results(subset, t)

    if not args.no_report and results:
        target_str = ", ".join(targets)
        path = save_report(results, target_str, args.output)
        print(f"\n{G}[+]{X} HTML report: {C}{path}{X}")

    print(f"\n{G}[+]{X} Done. Total: {W}{len(results)}{X} results\n")


if __name__ == "__main__":
    main()
