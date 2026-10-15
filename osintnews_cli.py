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
import re
import sys
import json
import hashlib
import argparse
import threading
from datetime import datetime

# ── Make ANSI escape codes work on legacy Windows consoles ────────────────────
try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass

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
        # .lstrip("﻿") drops a UTF-8 BOM that some shells prepend on the
        # first piped line, so an empty Enter is still read as empty.
        val = input(f"  {_WH}{msg}{hint}{_RS}: ").lstrip("﻿").strip()
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


# ── .env loader (no third-party dependency) ───────────────────────────────────

def _load_dotenv(base_dir: str):
    """
    Load KEY=VALUE lines from a .env file in the project root into os.environ.
    Existing environment variables are never overwritten. Silently does nothing
    if the file is absent or unreadable.
    """
    path = os.path.join(base_dir, ".env")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except FileNotFoundError:
        pass
    except Exception:
        pass


# ── Target sanity check ──────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _target_warning(mode: str, target: str) -> str:
    """
    Return a human-readable warning if the target looks malformed for the mode,
    or an empty string if it looks fine. Never blocks — just advises.
    """
    t = target.strip()
    if mode == "email" and not _EMAIL_RE.match(t):
        return "That doesn't look like an email address (expected name@domain.tld)."
    if mode == "phone" and len(re.sub(r"\D", "", t)) < 6:
        return "That doesn't look like a phone number (too few digits)."
    if mode == "username" and len(t) < 3:
        return "Usernames under 3 characters produce very noisy, low-signal results."
    if mode == "person" and " " not in t:
        return "Name searches work best with a first and last name."
    return ""


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


# ── Phase 2 — live verification ───────────────────────────────────────────────

_CONF_STYLE = {
    "VERIFIED":       ("✔", "\033[92m"),   # green
    "LIKELY":         ("~", "\033[96m"),   # cyan
    "UNVERIFIABLE":   ("?", "\033[90m"),   # grey
    "FALSE_POSITIVE": ("✘", "\033[93m"),   # yellow
    "ERROR":          ("!", "\033[91m"),   # red
}


def _verify_results(results: list, mode: str) -> list:
    """Run the verifier over the raw results and print a verdict breakdown."""
    from modules import verifier

    _section("Verifying results  (live HTTP checks)")
    print(f"  {_GY}Checking {len(results)} URL(s). Login-walled sites "
          f"(Twitter/X, Instagram, LinkedIn, …) are not requested.{_RS}\n")

    stop_event = threading.Event()
    try:
        results = verifier.verify_results(
            results,
            on_status   = _on_status,
            on_progress = _on_progress,
            stop_event  = stop_event,
        )
    except KeyboardInterrupt:
        stop_event.set()
        print(f"\n\n  {_YL}[!] Verification cancelled — showing what completed.{_RS}")

    print("\n")
    counts = verifier.summarize(results)
    for level in verifier.CONFIDENCE_ORDER:
        mark, colour = _CONF_STYLE[level]
        print(f"  {colour}{mark} {level:<15}{_RS} {counts.get(level, 0)}")
        if level == "UNVERIFIABLE" and counts.get(level):
            for label, n, hosts in verifier.unverifiable_breakdown(results):
                detail = ", ".join(f"{h}×{c}" for h, c in hosts)
                print(f"      {_GY}↳ {n} {label}"
                      f"{('  (' + detail + ')') if detail else ''}{_RS}")

    if not counts.get("VERIFIED") and not counts.get("LIKELY"):
        alt = {"username": "email / person", "email": "username / person",
               "phone": "person", "person": "username"}.get(mode, "another mode")
        print(f"\n  {_YL}Nothing could be verified.{_RS} {_GY}Login-walled platforms "
              f"can't be checked without an account — try {_WH}--mode {alt}{_RS}{_GY}, "
              f"or a target with a GitHub / Reddit / paste presence.{_RS}")
    return results


def _exposure_line(results: list):
    """One-line exposure verdict using the documented verifier formula."""
    from modules import verifier

    level, points, breakdown = verifier.exposure_level(results)
    colour = {"LOW": _GR, "MEDIUM": _YL, "HIGH": _MG, "CRITICAL": _RD}.get(level, _GY)
    print(f"\n  {_WH}Exposure level:{_RS} {colour}{_BO}{level}{_RS}  "
          f"{_GY}({points} pts){_RS}")
    for line in breakdown:
        print(f"    {_GY}· {line}{_RS}")


# ── Cross-correlation (chained, Maltego-transform style) ──────────────────────

def _cross_correlation(results: list) -> tuple:
    """
    Link identifiers that surfaced during verification and run one chained pass:
    extracted emails re-checked against the paste/leak URLs already in the run
    (no new dork searches). Returns (correlations, chained_findings).
    """
    from modules import verifier

    correlations = verifier.correlate(results)
    recheck = verifier.build_email_recheck_targets(results)
    chained: list = []

    if recheck:
        n_emails = len({t["target"] for t in recheck})
        n_urls   = len({t["href"] for t in recheck})
        _section("Cross-correlation")
        print(f"  {_GY}Re-checking {n_emails} extracted email(s) against "
              f"{n_urls} paste/leak URL(s)…{_RS}\n")
        stop_event = threading.Event()
        try:
            rechecked = verifier.verify_results(
                recheck, on_status=_on_status, on_progress=_on_progress,
                stop_event=stop_event, max_checks=40,
            )
        except KeyboardInterrupt:
            stop_event.set()
            rechecked = []
            print(f"\n  {_YL}[!] Cross-check cancelled.{_RS}")
        print("\n")
        for r in rechecked:
            if r.get("confidence") in ("VERIFIED", "LIKELY"):
                chained.append({
                    "email":      r.get("target", ""),
                    "url":        r.get("href", ""),
                    "confidence": r["confidence"],
                    "context":    (r.get("evidence") or {}).get("context", ""),
                })
    elif any(r.get("confidence") for r in results):
        _section("Cross-correlation")

    if not correlations and not chained:
        if any(r.get("confidence") for r in results):
            print(f"  {_GY}No identifier appeared on two or more sources.{_RS}")
        return correlations, chained

    if correlations:
        print(f"  {_GR}● Identifiers linked across platforms:{_RS}")
        for c in correlations:
            col = _MG if c["confidence"] == "HIGH" else _YL
            print(f"    {col}{c['type'].upper():<7}{_RS} {_WH}{c['value']}{_RS}  "
                  f"{_GY}— {len(c['found_on'])} sources: {', '.join(c['found_on'])}{_RS}")
    if chained:
        print(f"\n  {_RD}● Extracted emails also found on paste/leak sites:{_RS}")
        for f in chained:
            print(f"    {_WH}{f['email']}{_RS}  {_BL}{f['url']}{_RS}")
            if f["context"]:
                print(f"      {_GY}{f['context'][:160]}{_RS}")

    return correlations, chained


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

    verified_run = any(r.get("confidence") for r in results)

    if confirmed:
        print(f"  {_GR}● Presence detected on:{_RS}")
        for name, items in confirmed:
            if verified_run:
                v = sum(1 for r in items if r.get("confidence") == "VERIFIED")
                lk = sum(1 for r in items if r.get("confidence") == "LIKELY")
                tag = (f"  {_GR}{v} verified{_RS}, {_CY}{lk} likely{_RS}"
                       if (v or lk) else f"  {_GY}none confirmed{_RS}")
            else:
                tag = ""
            print(f"    {_WH}{name}{_RS}  ({len(items)} result"
                  f"{'s' if len(items) != 1 else ''}){tag}")
            # when verified, lead with the strongest hits
            show = sorted(items, key=lambda r: (
                {"VERIFIED": 0, "LIKELY": 1}.get(r.get("confidence"), 2)))
            for r in show[:2]:
                if r.get("href"):
                    print(f"      {_BL}{r['href']}{_RS}")
    else:
        print(f"  {_GY}● No confirmed presence found on any searched platform.{_RS}")

    if empty:
        print(f"\n  {_GY}○ No results on:{_RS} {', '.join(empty)}")

    # Risk assessment — prefer the verified exposure formula when Phase 2 ran
    if any(r.get("confidence") for r in results):
        _exposure_line(results)
        count = sum(1 for r in results if r.get("confidence") in ("VERIFIED", "LIKELY"))
    else:
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

def _save_spiderfoot_json(results: list, target: str, path: str,
                          correlations: list | None = None) -> str:
    """
    Export results in SpiderFoot-compatible JSON format.
    SpiderFoot expects a list of events with type, data, source, confidence.
    """
    # Verification verdict → SpiderFoot confidence (0-100). Default 75 when the
    # result was never verified (--verify not used).
    sf_conf_map = {
        "VERIFIED": 100, "LIKELY": 75, "UNVERIFIABLE": 50,
        "FALSE_POSITIVE": 15, "ERROR": 40,
    }

    events = []
    for r in results:
        url     = r.get("href",     "")
        title   = r.get("title",    "")
        body    = r.get("body",     "") or ""
        cat     = r.get("category", "OSINT")
        mode    = r.get("mode",     "username")
        conf    = r.get("confidence")

        # Skip results the live check actively disproved
        if conf == "FALSE_POSITIVE":
            continue

        # Map OSINTNEWS mode to SpiderFoot event types
        sf_type_map = {
            "username": "SOCIAL_MEDIA",
            "email":    "EMAILADDR_COMPROMISED",
            "phone":    "PHONE_NUMBER",
            "person":   "HUMAN_NAME",
        }
        sf_type = sf_type_map.get(mode, "LINKED_URL_INTERNAL")

        evidence = r.get("evidence") or {}
        events.append({
            "type":       sf_type,
            "data":       url or title,
            "source":     "OSINTNEWS-CLI",
            "module":     f"osintnews_{cat.lower().replace(' ', '_')}",
            "confidence": sf_conf_map.get(conf, 75),
            "verified":   conf or "NOT_CHECKED",
            "visibility": 1,
            "risk":       "INFO",
            "generated":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target":     target,
            "title":      title,
            "snippet":    (evidence.get("context") or body)[:300],
            "url":        url,
        })

    # Cross-correlation records → SpiderFoot affiliate/associated events
    sf_corr_type = {"email": "AFFILIATE_EMAILADDR",
                    "handle": "USERNAME", "phone": "PHONE_NUMBER"}
    for c in (correlations or []):
        events.append({
            "type":       sf_corr_type.get(c["type"], "RAW_RIR_DATA"),
            "data":       c["value"],
            "source":     "OSINTNEWS-CLI/correlation",
            "module":     "osintnews_correlation",
            "confidence": 90 if c["confidence"] == "HIGH" else 70,
            "visibility": 2,
            "risk":       "INFO",
            "generated":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target":     target,
            "title":      f"{c['value']} — linked across {len(c['found_on'])} sources",
            "snippet":    "found on: " + ", ".join(c["found_on"]),
            "url":        (c["sources"][0] if c["sources"] else ""),
        })

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(events, fh, indent=2, ensure_ascii=False)
    return path


def _autosave_watch(results: list, target: str, mode: str, reports_dir: str,
                    correlations: list, chained: list):
    """Silently persist a watch cycle's new hits to reports/watch_<hash>_<ts>.json."""
    try:
        import hashlib
        os.makedirs(reports_dir, exist_ok=True)
        h  = hashlib.sha256(f"{mode}:{target}".encode()).hexdigest()[:12]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(reports_dir, f"watch_{h}_{ts}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({
                "target": target, "mode": mode,
                "captured": datetime.now().isoformat(timespec="seconds"),
                "new_results": results,
                "correlations": correlations,
                "chained_findings": chained,
            }, fh, indent=2, ensure_ascii=False)
        print(f"  {_GR}✔{_RS} new hits saved → {_BL}{path}{_RS}")
    except Exception as exc:
        print(f"  {_YL}(could not auto-save watch delta: {exc}){_RS}")


def _offer_export(results: list, target: str, reports_dir: str, analysis=None,
                  correlations: list | None = None):
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

    try:
        os.makedirs(reports_dir, exist_ok=True)
    except OSError as exc:
        print(f"\n  {_RD}[!] Cannot create reports directory ({exc}). Export aborted.{_RS}")
        return

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in target) or "target"

    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        try:
            if part == "1":
                # save_report picks its own timestamped filename — use what it returns
                path = save_report(results, target, output_dir=reports_dir,
                                   analysis=analysis, correlations=correlations)
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
                save_markdown(results, path, analysis=analysis)
                print(f"  {_GR}✔{_RS} Markdown   → {_BL}{path}{_RS}")
            elif part == "5":
                path = os.path.join(reports_dir, f"osint_{safe}_{ts}_spiderfoot.json")
                _save_spiderfoot_json(results, target, path, correlations=correlations)
                print(f"  {_GR}✔{_RS} SpiderFoot → {_BL}{path}{_RS}")
                print(f"     {_GY}Load in SpiderFoot: Investigations → Import Data → JSON{_RS}")
            else:
                print(f"  {_YL}Skipped unknown option '{part}'.{_RS}")
        except Exception as exc:
            print(f"  {_RD}✘ Export option {part} failed: {exc}{_RS}")


# ── AI analysis (RAG pipeline) ───────────────────────────────────────────────

_AI_ENV_KEYS = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


def _run_ai_analysis(results: list, target: str, provider: str):
    """
    Run the RAG pipeline over the search results and stream a written
    intelligence summary to the terminal. Returns the AIAnalysis object on
    success (for embedding in exports) or None.
    """
    if not results:
        return None

    provider = (provider or "claude").lower()
    try:
        from modules.rag.pipeline import run_pipeline
    except Exception as exc:
        print(f"\n  {_RD}[!] AI pipeline unavailable: {exc}{_RS}")
        return None

    api_key = os.environ.get(_AI_ENV_KEYS.get(provider, ""), "")
    if provider in _AI_ENV_KEYS and not api_key:
        env = _AI_ENV_KEYS[provider]
        print(f"\n  {_RD}[!] No API key for '{provider}'. Set {env} as an "
              f"environment variable or in a .env file, then retry.{_RS}")
        return None

    _section(f"AI Analysis  ({provider})")
    print(f"  {_GY}Analysing {len(results)} sources — streaming below…{_RS}\n")

    try:
        result = run_pipeline(
            raw_results = results,
            target      = target,
            provider    = provider,
            api_key     = api_key,
            on_token    = lambda chunk: print(chunk, end="", flush=True),
        )
    except Exception as exc:
        print(f"\n\n  {_RD}[!] AI analysis failed: {exc}{_RS}")
        return None

    print("\n")
    analysis = result.analysis
    if analysis.succeeded:
        print(f"  {_WH}Risk level:{_RS} {analysis.risk_level}   "
              f"{_GY}({analysis.source_count} sources analysed, "
              f"{len(analysis.cited_sources)} cited){_RS}")
        return analysis

    print(f"  {_RD}[!] {analysis.error or 'AI analysis returned nothing.'}{_RS}")
    return None


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
                reports_dir: str, data_dir: str, skip_consent: bool = False,
                run_ai: bool = False, ai_provider: str = "claude",
                verify: bool = False, watch: bool = False):
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

    # Always audit-log the full run (target stored as a hash)
    _audit_log(mode, target, category_keys, len(results), data_dir)

    # ── Watch mode — diff against the stored baseline, act on new only ──
    watch_is_delta = False   # True once we're past the first (baseline) run
    if watch:
        from modules import watchstore
        diff = watchstore.diff_and_update(data_dir, target, mode, results,
                                          categories=category_keys)
        if diff["first_run"]:
            print(f"  {_CY}Watch baseline established — {len(results)} result(s) "
                  f"recorded. Future runs show only what's new.{_RS}\n")
        else:
            watch_is_delta = True
            since = diff["last_run"] or "last run"
            if not diff["new"]:
                print(f"  {_GR}✓ Nothing new since {since}.{_RS}  "
                      f"{_GY}({diff['known']} known result(s)){_RS}")
                _save_history(target, mode, len(results), data_dir)
                return
            print(f"  {_YL}▲ {len(diff['new'])} NEW result(s) since {since}{_RS}  "
                  f"{_GY}({diff['known']} already seen){_RS}\n")
            results = diff["new"]                     # act on the delta only

    # Phase 2 — live HTTP verification of each candidate URL
    if verify and results:
        results = _verify_results(results, mode)

    # Standard result display
    print_results(results, target)

    # Username correlation summary (only for username mode)
    if mode == "username" and results:
        _username_correlation(results, target)
    elif verify and results:
        _exposure_line(results)

    # Cross-correlation + chained email re-check (only meaningful after --verify)
    correlations, chained = ([], [])
    if verify and results:
        correlations, chained = _cross_correlation(results)

    # History
    _save_history(target, mode, len(results), data_dir)

    # Watch mode never prompts (it may run in a loop / from cron): auto-save the
    # run's results and, on a delta run, fire a desktop notification.
    if watch:
        if watch_is_delta:
            try:
                from modules.notifier import notify
                notify("OSINTNEWS — new results",
                       f"{len(results)} new hit(s) for {target}")
            except Exception:
                pass
        _autosave_watch(results, target, mode, reports_dir, correlations, chained)
        return

    # Optional AI analysis over the results (RAG pipeline)
    analysis = _run_ai_analysis(results, target, ai_provider) if (run_ai and results) else None

    # Export
    _offer_export(results, target, reports_dir, analysis=analysis,
                  correlations=correlations)


# ── Watch mode ────────────────────────────────────────────────────────────────

_MIN_WATCH_INTERVAL = 300   # 5 min — below this DuckDuckGo just rate-limits you


def _watch_loop(run_once, interval: int):
    """
    Repeatedly call `run_once` every `interval` seconds until Ctrl-C.
    `interval <= 0` runs it exactly once (cron / Task Scheduler style).
    """
    from datetime import datetime as _dt
    cycle = 0
    while True:
        cycle += 1
        print(f"\n{_MG}{'═' * 62}{_RS}")
        print(f"{_MG}  watch cycle {cycle}  ·  {_dt.now():%Y-%m-%d %H:%M:%S}{_RS}")
        print(f"{_MG}{'═' * 62}{_RS}")
        try:
            run_once()
        except KeyboardInterrupt:
            print(f"\n  {_CY}Watch stopped.{_RS}\n")
            return
        if interval <= 0:
            return
        print(f"\n  {_GY}Sleeping {interval}s … (Ctrl-C to stop){_RS}")
        try:
            import time as _t
            _t.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n  {_CY}Watch stopped.{_RS}\n")
            return


# ── Interactive loop ───────────────────────────────────────────────────────────

def _interactive(reports_dir: str, data_dir: str):
    while True:
        _banner()

        mode   = _select_mode()
        target = _prompt(f"Enter {mode} to search")
        if not target:
            print(f"  {_RD}Target cannot be empty.{_RS}")
            continue

        warning = _target_warning(mode, target)
        if warning:
            print(f"  {_YL}⚠  {warning}{_RS}")
            if _prompt("Search anyway? [y/N]", "n").lower() not in ("y", "yes"):
                continue

        category_keys = _select_categories(mode)

        verify = _prompt("Verify each result with a live HTTP check afterwards "
                         "(slower)? [y/N]", "n").lower() in ("y", "yes")

        watch = _prompt("Watch this target for NEW results on a schedule? [y/N]",
                        "n").lower() in ("y", "yes")
        interval = 0
        if watch:
            raw = _prompt("Interval in seconds (0 = check once now)", "3600")
            try:
                interval = max(0, int(raw))
            except ValueError:
                interval = 3600
            if 0 < interval < _MIN_WATCH_INTERVAL:
                print(f"  {_YL}Bumping interval to {_MIN_WATCH_INTERVAL}s "
                      f"(DuckDuckGo rate-limits anything faster).{_RS}")
                interval = _MIN_WATCH_INTERVAL

        run_ai      = False
        ai_provider = "claude"
        if not watch:
            run_ai = _prompt("Run AI analysis on the results afterwards? [y/N]",
                             "n").lower() in ("y", "yes")
            if run_ai:
                ai_provider = (_prompt("AI provider (claude/openai/gemini/ollama)",
                                       "claude").lower().strip() or "claude")

        def _once():
            _run_search(mode, target, category_keys, reports_dir, data_dir,
                        run_ai=run_ai, ai_provider=ai_provider, verify=verify,
                        watch=watch)

        if watch:
            _watch_loop(_once, interval)
        else:
            _once()

        print()
        again = _prompt("Run another search? [y/N]", "n").lower()
        if again not in ("y", "yes"):
            print(f"\n  {_CY}Goodbye!{_RS}\n")
            break


# ── Argument-driven entry point ────────────────────────────────────────────────

def main():
    from modules.paths import app_home
    base_dir    = app_home()
    reports_dir = os.path.join(base_dir, "reports")
    data_dir    = os.path.join(base_dir, "data")

    # Pick up API keys / config from a gitignored .env file if present
    _load_dotenv(base_dir)

    parser = argparse.ArgumentParser(
        prog        = "osintnews --cli",
        description = "OSINTNEWS CLI — OSINT Identity Search",
        add_help    = True,
    )
    parser.add_argument("--mode",   choices=["username", "email", "phone", "person"])
    parser.add_argument("--target", help="Target value to search for")
    parser.add_argument("--all-categories", action="store_true")
    parser.add_argument("--verify", action="store_true",
                        help="Phase 2: confirm each result with a live HTTP check")
    parser.add_argument("--watch", action="store_true",
                        help="Watch mode: report only results new since the last run")
    parser.add_argument("--interval", type=int, default=0, metavar="SECONDS",
                        help="With --watch, loop every SECONDS (0 = check once and exit)")
    parser.add_argument("--ai",      action="store_true",
                        help="Run AI (RAG) analysis over the results")
    parser.add_argument("--provider", default="claude",
                        help="AI provider: claude | openai | gemini | ollama")
    parser.add_argument("--skip-consent", action="store_true",
                        help="Skip consent prompt (use only when you have confirmed consent)")

    args, _ = parser.parse_known_args()

    if args.mode and args.target:
        from modules.dorker_osint import categories_for_mode
        keys = list(categories_for_mode(args.mode).keys())
        _banner()
        warning = _target_warning(args.mode, args.target)
        if warning:
            print(f"  {_YL}⚠  {warning}{_RS}\n")

        interval = args.interval
        if args.watch and 0 < interval < _MIN_WATCH_INTERVAL:
            print(f"  {_YL}⚠  --interval bumped to {_MIN_WATCH_INTERVAL}s "
                  f"(DuckDuckGo rate-limits anything faster).{_RS}\n")
            interval = _MIN_WATCH_INTERVAL

        def _once():
            _run_search(args.mode, args.target, keys, reports_dir, data_dir,
                        skip_consent=args.skip_consent,
                        run_ai=args.ai and not args.watch,
                        ai_provider=args.provider,
                        verify=args.verify, watch=args.watch)

        if args.watch:
            _watch_loop(_once, interval)
        else:
            _once()
        return

    try:
        _interactive(reports_dir, data_dir)
    except KeyboardInterrupt:
        print(f"\n\n  {_CY}Exiting OSINTNEWS CLI.{_RS}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
