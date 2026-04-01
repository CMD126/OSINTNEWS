"""
OSINTNEWS — Entry Point
========================

Two tools in one:

  ┌─────────────────────────────────────────────────────────────┐
  │  GUI (default)   python osintnews.py                        │
  │  → News Intelligence — Google Dorking + RAG AI engine       │
  │    Search news, press releases, financial/gov docs,         │
  │    academic papers, leaks, social mentions for any target.  │
  ├─────────────────────────────────────────────────────────────┤
  │  CLI             python osintnews.py --cli                  │
  │  → OSINT Identity Search — usernames, emails, phones,       │
  │    people across social media, forums, breach sites,        │
  │    company records and more.                                │
  └─────────────────────────────────────────────────────────────┘

Examples (CLI):
  python osintnews.py --cli --mode username --target johndoe
  python osintnews.py --cli --mode email    --target john@example.com
  python osintnews.py --cli --mode phone    --target "+1 555 123 4567"
  python osintnews.py --cli --mode person   --target "John Doe"
  python osintnews.py --cli --mode username --target h4ck3r --ai --provider claude
"""

import sys

# ── Auto-installer: runs before everything else ──────────────────────────────
# Checks for missing/outdated packages and installs them automatically.
# Shows a friendly progress window on first run — no pip knowledge needed.
try:
    from modules.installer import ensure_dependencies
    ensure_dependencies()
except Exception as _e:
    print(f"[setup] Auto-install skipped: {_e}", flush=True)
# ─────────────────────────────────────────────────────────────────────────────


def main():
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        from osintnews_cli import main as cli_main
        cli_main()
    else:
        try:
            import tkinter as tk
        except ImportError:
            print("[!] tkinter not available. Falling back to CLI OSINT mode.")
            from osintnews_cli import main as cli_main
            cli_main()
            return

        from modules.gui.app import launch
        launch()


if __name__ == "__main__":
    main()
