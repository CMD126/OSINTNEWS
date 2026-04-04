"""
OSINTNEWS — CLI Mode
====================
Interactive OSINT identity search: usernames, emails, phones, people.
Powered by DuckDuckGo Google-dork queries across social media, forums,
breach sites, company records and more.

Usage (direct):
  python osintnews.py --cli
  python osintnews.py --cli --mode username --target johndoe
  python osintnews.py --cli --mode email    --target john@example.com
  python osintnews.py --cli --mode phone    --target "+351 912 345 678"
  python osintnews.py --cli --mode person   --target "John Doe"
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import argparse
import threading
from datetime import datetime

# ── Colour palette ────────────────────────────────────────────────────────────
_CY  = "\033[96m"
_GR  = "\033[92m"
_YL  = "\033[93m"
_BL  = "\033[94m"
_WH  = "\033[97m"
_GY  = "\033[90m"
_RD  = "\033[91m"
_MG  = "\033[95m"
_RS  = "\033[0m"
_BO  = "\033[1m"

# ── Modes that involve personal identifiers (require consent check) ───────────
_SENSITIVE_MODES = {"email", "phone", "person"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _banner():
    print(f"""
{_CY}{_BO}
  ██████╗ ███████╗██╗███╗  ██╗████████╗███╗  ██╗███████╗██╗    ██╗███████╗
 ██╔═══██╗██╔════╝██║████╗ ██║╚══██╔══╝████╗ ██║██╔════╝██║    ██║██╔════╝
 ██║   ██║███████╗██║██╔██╗██║   ██║   ██╔██╗██║█████╗  ██║ █╗ ██║███████╗
 ██║   ██║╚════██║██║██║╚████║   ██║   ██║╚████║██╔══╝  ██║███╗██║╚════██║
 ╚██████╔╝███████║██║██║ ╚███║   ██║   ██║ ╚███║███████╗╚███╔███╔╝███████║
  ╚═════╝ ╚══════╝╚═╝╚═╝  ╚══╝   ╚═╝   ╚═╝  ╚══╝╚══════╝ ╚══╝╚══╝ ╚══════╝
{_RS}{_GY}                        OSINT Identity Search — CLI Mode{_RS}
""")


def _section(title: str):
    width = 62
    print(f"\n{_YL}{'─' * width}{_RS}")
    print(f"{_YL}  {title}{_RS}")
    print(f"{_YL}{'─' * width}{_RS}")


def _prompt(msg: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"  {_WH}{msg}{hint}{_RS}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val if val else default


def _choose(options: list[tuple[str, str]], title: str = "Choose an option") -> str:
    _section(title)
    keys = []
    for i, (key, label) in enumerate(options, 1):
        print(f"  {_CY}{i}.{_RS} {label}")
        keys.append(key)
    while True:
        raw = _prompt("Enter number")
        if raw.isdigit() and 1 <= int(raw) <= len(keys):
            return keys[int(raw) - 1]
        print(f"  {_RD}Invalid — pick 1–{len(keys)}.{_RS}")


def _multi_choose(options: list[tuple[str, str]], title: str = "Select categories") -> list[str]:
    _section(title)
    keys = []
    for i, (key, label) in enumerate(options, 1):
        print(f"  {_CY}{i}.{_RS} {label}")
        keys.append(key)

    print(f"\n  {_GY}Enter numbers separated by commas, or press Enter for ALL{_RS}")
    while True:
        raw = _prompt("Selection", "all").lower().strip()
        if raw in ("all", "a", ""):
            return keys
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        chosen = []
        valid  = True
        for p in parts:
            if p.isdigit() and 1 <= int(p) <= len(keys):
                chosen.append(keys[int(p) - 1])
            else:
                print(f"  {_RD}Invalid entry: '{p}'. Try again.{_RS}")
                valid = False
                break
        if valid and chosen:
            return chosen


# ── Consent gate ──────────────────────────────────────────────────────────────

def _consent_check(mode: str, target: str) -> bool:
    """
    For sensitive modes (email, phone, person), require the user to confirm
    they are researching themselves or have explicit consent from the subject.
    Returns True if the search may proceed, False otherwise.
    """
    if mode not in _SENSITIVE_MODES:
        return True

    _section("⚠  Consent & Legal Check")
    print(f"""
  {_YL}You are about to search for personal identifier data:{_RS}
  {_WH}Mode:{_RS}   {mode.upper()}
  {_WH}Target:{_RS} {target}

  {_GY}This tool queries only publicly indexed information.
  Searching personal identifiers (email, phone, full name) without
  consent may violate GDPR and local privacy laws.{_RS}

  Please confirm ONE of the following applies:
  {_CY}1.{_RS} This is {_WH}my own{_RS} data — personal footprint audit
  {_CY}2.{_RS} I have {_WH}explicit written consent{_RS} from the subject
  {_CY}3.{_RS} This is a {_WH}journalistic / cybersecurity investigation{_RS} with lawful basis
  {_CY}0.{_RS} {_RD}Cancel — do not proceed{_RS}
""")
    raw = _prompt("Confirm (1/2/3 to proceed, 0 to cancel)").strip()
    if raw in ("1", "2", "3"):
        return True
    print(f"\n  {_RD}Search cancelled. No data was queried.{_RS}\n")
    return False


# ── Audit log ─────────────────────────────────────────────────────────────────

def _audit_log(mode: str, target: str, categories: list[str], result_count: int, data_dir: str):
    """
    Append a record to data/audit.log.
    The target is stored as a SHA-256 hash for privacy — not in plaintext.
    """
    try:
        os.makedirs(data_dir, exist_ok=True)
        log_path    = os.path.join(data_dir, "audit.log")
        target_hash = hashlib.sha256(target.encode()).hexdigest()[:16]
        timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"{timestamp} | mode={mode} | target_hash={target_hash} "
            f"| categories={','.join(categories)} | results={result_count}\n"
        )
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(entry)
    except Exception:
        pass   # audit log is non-critical


# ── Mode selection ─────────────────────────────────────────────────────────────

_MODE_OPTIONS = [
    ("username", "Username / Handle  — social media, forums, gaming"),
    ("email",    "Email Address      — breaches, social, professional"),
    ("phone",    "Phone Number       — directories, classifieds, leaks"),
    ("person",   "Full Name          — news, legal, academic, social"),
]


def _select_mode() -> str:
    return _choose(_MODE_OPTIONS, "Search Mode")


# ── Category selection ─────────────────────────────────────────────────────────

def _select_categories(mode: str) -> list[str]:
    from modules.dorker_osint import categories_for_mode
    cats    = categories_for_mode(mode)
    options = [(k, f"{v['name']}  — {v['description']}") for k, v in cats.items()]
    return _multi_choose(options, f"Select search categories for [{mode.upper()}]")


# ── Progress display ───────────────────────────────────────────────────────────

_spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_spin_idx       = 0
_spin_lock      = threading.Lock()


def _on_status(msg: str):
    global _spin_idx
    with _spin_lock:
        frame = _spinner_frames[_spin_idx % len(_spinner_frames)]
        _spin_idx += 1
    print(f"\r  {_CY}{frame}{_RS} {_GY}{msg[:78]}{_RS}    ", end="", flush=True)


def _on_progress(done: int, total: int):
    pct = int(done / total * 100) if total else 100
    bar = ("█" * (pct // 5)).ljust(20)
    print(f"\r  {_GR}[{bar}]{_RS} {_WH}{pct}%{_RS} ({done}/{total})    ",
          end="", flush=True)


# ── Username correlation ───────────────────────────────────────────────────────

def _username_correlation(results: list, target: str):
    """
    After a username search, print a correlation summary:
    which platforms confirmed a presence, which found nothing.
    """
    from modules.dorker_osint import categories_for_mode
    cats = categories_for_mode("username")

    hits: dict[str, list] = {}
    for r in results:
        cat = r.get("category", "Unknown")
        hits.setdefault(cat, []).append(r)

    _section("Username Correlation Summary")
    print(f"\n  {_WH}Target:{_RS} {_CY}{target}{_RS}\n")

    confirmed = []
    empty     = []

    for key, meta in cats.items():
        name = meta["name"]
        found = hits.get(name, [])
        if found:
            confirmed.append((name, found))
        else:
            empty.append(name)

    if confirmed:
        print(f"  {_GR}● Presence detected on:{_RS}")
        for name, items in confirmed:
            urls = [r.get("href", "") for r in items if r.get("href")]
            print(f"    {_WH}{name}{_RS}  ({len(items)} result{'s' if len(items) != 1 else ''})")
            for url in urls[:2]:
                print(f"      {_BL}{url}{_RS}")
    else:
        print(f"  {_GY}● No confirmed presence found on any searched platform.{_RS}")

    if empty:
        print(f"\n  {_GY}○ No results on:{_RS} {', '.join(empty)}")

    # Risk assessment
    count = len(confirmed)
    if count == 0:
        level, colour = "LOW",      _GR
    elif count <= 3:
        level, colour = "MEDIUM",   _YL
    elif count <= 6:
        level, colour = "HIGH",     _MG
    else:
        level, colour = "CRITICAL", _RD

    print(f"\n  {_WH}Exposure level:{_RS} {colour}{_BO}{level}{_RS}  "
          f"{_GY}({count} platform{'s' if count != 1 else ''} with results){_RS}")

    if count >= 4:
        print(f"\n  {_YL}⚠  Consider reviewing and limiting your public footprint.{_RS}")
        print(f"  {_GY}Tip: Use different usernames per platform to prevent cross-correlation.{_RS}")


# ── Export helpers ─────────────────────────────────────────────────────────────

def _save_spiderfoot_json(results: list, target: str, path: str) -> str:
    """
    Export results in SpiderFoot-compatible JSON format.
    SpiderFoot expects a list of events with type, data, source, confidence.
    """
    events = []
    for r in results:
        url     = r.get("href",     "")
        title   = r.get("title",    "")
        body    = r.get("body",     "") or ""
        cat     = r.get("category", "OSINT")
        mode    = r.get("mode",     "username")

        # Map OSINTNEWS mode to SpiderFoot event types
        sf_type_map = {
            "username": "SOCIAL_MEDIA",
            "email":    "EMAILADDR_COMPROMISED",
            "phone":    "PHONE_NUMBER",
            "person":   "HUMAN_NAME",
        }
        sf_type = sf_type_map.get(mode, "LINKED_URL_INTERNAL")

        events.append({
            "type":       sf_type,
            "data":       url or title,
            "source":     "OSINTNEWS-CLI",
            "module":     f"osintnews_{cat.lower().replace(' ', '_')}",
            "confidence": 75,
            "visibility": 1,
            "risk":       "INFO",
            "generated":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target":     target,
            "title":      title,
            "snippet":    body[:300],
            "url":        url,
        })

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(events, fh, indent=2, ensure_ascii=False)
    return path


def _offer_export(results: list, target: str, reports_dir: str):
    if not results:
        return

    _section("Export Results")
    print(f"  {_GY}Choose export formats (comma-separated numbers, or Enter to skip):{_RS}\n")
    print(f"  {_CY}1.{_RS} HTML       (styled dark-theme report)")
    print(f"  {_CY}2.{_RS} JSON       (standard)")
    print(f"  {_CY}3.{_RS} CSV")
    print(f"  {_CY}4.{_RS} Markdown")
    print(f"  {_CY}5.{_RS} SpiderFoot JSON  (compatible with SpiderFoot / theHarvester pipelines)")

    raw = _prompt("Formats", "").lower().strip()
    if not raw:
        print(f"\n  {_GY}Skipped export.{_RS}")
        return

    from modules.reporter import save_report, save_json, save_csv, save_markdown

    os.makedirs(reports_dir, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in target)

    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        if part == "1":
            path = os.path.join(reports_dir, f"osint_{safe}_{ts}.html")
            save_report(results, target, output_dir=reports_dir)
            print(f"  {_GR}✔{_RS} HTML       → {_BL}{path}{_RS}")
        elif part == "2":
            path = os.path.join(reports_dir, f"osint_{safe}_{ts}.json")
            save_json(results, path)
            print(f"  {_GR}✔{_RS} JSON       → {_BL}{path}{_RS}")
        elif part == "3":
            path = os.path.join(reports_dir, f"osint_{safe}_{ts}.csv")
            save_csv(results, path)
            print(f"  {_GR}✔{_RS} CSV        → {_BL}{path}{_RS}")
        elif part == "4":
            path = os.path.join(reports_dir, f"osint_{safe}_{ts}.md")
            save_markdown(results, path)
            print(f"  {_GR}✔{_RS} Markdown   → {_BL}{path}{_RS}")
        elif part == "5":
            path = os.path.join(reports_dir, f"osint_{safe}_{ts}_spiderfoot.json")
            _save_spiderfoot_json(results, target, path)
            print(f"  {_GR}✔{_RS} SpiderFoot → {_BL}{path}{_RS}")
            print(f"     {_GY}Load in SpiderFoot: Investigations → Import Data → JSON{_RS}")


# ── History helpers ────────────────────────────────────────────────────────────

def _save_history(target: str, mode: str, result_count: int, data_dir: str):
    try:
        from modules.history import HistoryManager
        hist = HistoryManager(os.path.join(data_dir, "osint_history.json"))
        hist.add({
            "target":       target,
            "mode":         mode,
            "result_count": result_count,
        })
    except Exception:
        pass


# ── Core search flow ───────────────────────────────────────────────────────────

def _run_search(mode: str, target: str, category_keys: list[str],
                reports_dir: str, data_dir: str, skip_consent: bool = False):
    # Consent check for sensitive modes
    if not skip_consent and not _consent_check(mode, target):
        return

    from modules.dorker_osint import build_osint_dorks
    from modules.searcher     import run_searches_with_callback
    from modules.reporter     import print_results

    dorks = build_osint_dorks(target, category_keys)
    if not dorks:
        print(f"\n  {_RD}[!] No dork templates found for the selected categories.{_RS}")
        return

    _section(f"Searching  [{mode.upper()}]  target: {target}")
    print(f"  {_GY}Querying {len(dorks)} dork(s) across {len(category_keys)} "
          f"categorie(s)…{_RS}\n")

    stop_event = threading.Event()
    results: list = []

    try:
        results = run_searches_with_callback(
            dorks,
            max_results = 10,
            delay       = 1.2,
            on_status   = _on_status,
            on_progress = _on_progress,
            max_workers = 3,
            stop_event  = stop_event,
        )
    except KeyboardInterrupt:
        stop_event.set()
        print(f"\n\n  {_YL}[!] Search cancelled by user.{_RS}")

    print("\n")

    # Standard result display
    print_results(results, target)

    # Username correlation summary (only for username mode)
    if mode == "username" and results:
        _username_correlation(results, target)

    # Audit log (target stored as hash, not plaintext)
    _audit_log(mode, target, category_keys, len(results), data_dir)

    # History
    _save_history(target, mode, len(results), data_dir)

    # Export
    _offer_export(results, target, reports_dir)


# ── Interactive loop ───────────────────────────────────────────────────────────

def _interactive(reports_dir: str, data_dir: str):
    while True:
        _banner()

        mode   = _select_mode()
        target = _prompt(f"Enter {mode} to search")
        if not target:
            print(f"  {_RD}Target cannot be empty.{_RS}")
            continue

        category_keys = _select_categories(mode)

        _run_search(mode, target, category_keys, reports_dir, data_dir)

        print()
        again = _prompt("Run another search? [y/N]", "n").lower()
        if again not in ("y", "yes"):
            print(f"\n  {_CY}Goodbye!{_RS}\n")
            break


# ── Argument-driven entry point ────────────────────────────────────────────────

def main():
    base_dir    = os.path.dirname(os.path.abspath(__file__))
    reports_dir = os.path.join(base_dir, "reports")
    data_dir    = os.path.join(base_dir, "data")

    parser = argparse.ArgumentParser(
        prog        = "osintnews --cli",
        description = "OSINTNEWS CLI — OSINT Identity Search",
        add_help    = True,
    )
    parser.add_argument("--mode",   choices=["username", "email", "phone", "person"])
    parser.add_argument("--target", help="Target value to search for")
    parser.add_argument("--all-categories", action="store_true")
    parser.add_argument("--ai",      action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--skip-consent", action="store_true",
                        help="Skip consent prompt (use only when you have confirmed consent)")

    args, _ = parser.parse_known_args()

    if args.mode and args.target:
        from modules.dorker_osint import categories_for_mode
        keys = list(categories_for_mode(args.mode).keys())
        _banner()
        _run_search(args.mode, args.target, keys, reports_dir, data_dir,
                    skip_consent=args.skip_consent)
        return

    try:
        _interactive(reports_dir, data_dir)
    except KeyboardInterrupt:
        print(f"\n\n  {_CY}Exiting OSINTNEWS CLI.{_RS}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
