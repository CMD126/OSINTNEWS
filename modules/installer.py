"""
OSINTNEWS Auto-Installer
========================
Automatically installs or upgrades all required packages at launch.
No manual pip commands needed — just run osintnews.py.

Features:
  - Shows a simple GUI progress window while installing
  - Migrates the old `duckduckgo-search` package to the new `ddgs` package
  - Falls back to a plain-text console installer if tkinter is unavailable
  - Safe to run on every launch (only installs what's actually missing or outdated)
"""

from __future__ import annotations
import sys
import subprocess
import importlib
import threading


# ---------------------------------------------------------------------------
# Package manifest
# Each entry: (import_name, pip_package, min_version_or_None, notes)
# ---------------------------------------------------------------------------

REQUIRED: list[tuple[str, str, str | None, str]] = [
    ("ddgs",              "ddgs",                  "0.1.0",  "Search engine (new name)"),
    ("colorama",          "colorama",               "0.4.6",  "Terminal colours"),
    ("openpyxl",          "openpyxl",               "3.1.0",  "Excel export"),
    ("anthropic",         "anthropic",              "0.49.0", "Claude AI (optional)"),
    ("openai",            "openai",                 "1.50.0", "OpenAI AI (optional)"),
    ("requests",          "requests",               "2.32.0", "Ollama + HTTP"),
]

# Packages that conflict and must be REMOVED before installing a replacement
MIGRATIONS: list[tuple[str, str, str]] = [
    # (old_import_name, old_pip_package, reason)
    ("duckduckgo_search", "duckduckgo-search",
     "renamed to 'ddgs' — removing old package to stop warning spam"),
]

# Optional packages — missing is fine, only shown in log
OPTIONAL: list[tuple[str, str]] = [
    ("plyer",              "plyer"),           # Windows notifications
    ("google.generativeai","google-generativeai"),  # Gemini AI
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_installed(import_name: str) -> bool:
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def _pip(*args: str, capture: bool = True) -> tuple[int, str]:
    """Run a pip command. Returns (returncode, combined_output)."""
    cmd = [sys.executable, "-m", "pip", *args, "--quiet", "--no-input"]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.returncode, result.stdout or ""


def _pkg_needs_install(import_name: str, pip_package: str,
                       min_ver: str | None) -> bool:
    """Return True if the package is missing or below min_ver."""
    if not _is_installed(import_name):
        return True
    if min_ver is None:
        return False
    try:
        import importlib.metadata as meta
        current = meta.version(pip_package.split("[")[0])  # strip extras
        from packaging.version import Version
        return Version(current) < Version(min_ver)
    except Exception:
        return False  # can't compare — assume OK


# ---------------------------------------------------------------------------
# GUI progress window
# ---------------------------------------------------------------------------

class _InstallerWindow:
    """Minimal tkinter progress window shown during installation."""

    def __init__(self):
        import tkinter as tk
        self._tk = tk
        self.root = tk.Tk()
        self.root.title("OSINTNEWS — Setting up dependencies…")
        self.root.geometry("480x260")
        self.root.resizable(False, False)
        self.root.configure(bg="#0d1117")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)  # disable close

        tk.Label(
            self.root,
            text="OSINTNEWS Plus",
            bg="#0d1117", fg="#58a6ff",
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=(24, 4))

        tk.Label(
            self.root,
            text="First-time setup — installing required packages…",
            bg="#0d1117", fg="#8b949e",
            font=("Segoe UI", 10),
        ).pack()

        self._status = tk.StringVar(value="Checking packages…")
        tk.Label(
            self.root,
            textvariable=self._status,
            bg="#0d1117", fg="#c9d1d9",
            font=("Segoe UI", 10),
            wraplength=440,
        ).pack(pady=(20, 6))

        # Fake progress bar using a canvas
        self._canvas = tk.Canvas(
            self.root, width=420, height=18,
            bg="#161b22", bd=0, highlightthickness=1,
            highlightbackground="#30363d",
        )
        self._canvas.pack()
        self._bar = self._canvas.create_rectangle(
            0, 0, 0, 18, fill="#58a6ff", outline=""
        )

        self._log_text = tk.Text(
            self.root, height=4,
            bg="#161b22", fg="#8b949e",
            font=("Consolas", 8),
            relief="flat", state="disabled",
            highlightthickness=1,
            highlightbackground="#30363d",
        )
        self._log_text.pack(fill="x", padx=30, pady=(10, 0))

        self.root.update()

    def set_status(self, msg: str):
        self._status.set(msg)
        self.root.update()

    def set_progress(self, pct: float):
        """pct: 0.0 – 1.0"""
        w = int(420 * max(0.0, min(1.0, pct)))
        self._canvas.coords(self._bar, 0, 0, w, 18)
        self.root.update()

    def log(self, line: str):
        self._log_text.config(state="normal")
        self._log_text.insert("end", line.strip() + "\n")
        self._log_text.see("end")
        self._log_text.config(state="disabled")
        self.root.update()

    def close(self):
        self.root.destroy()


# ---------------------------------------------------------------------------
# Core installer logic
# ---------------------------------------------------------------------------

def _run_install(ui=None) -> bool:
    """
    Check and install all required packages.
    Returns True if anything was installed (caller may want to restart).
    """

    def status(msg: str):
        if ui:
            ui.set_status(msg)
        else:
            print(f"[setup] {msg}", flush=True)

    def log(msg: str):
        if ui:
            ui.log(msg)
        else:
            print(f"  {msg}", flush=True)

    total_steps = len(MIGRATIONS) + len(REQUIRED)
    step = 0
    anything_installed = False

    # ── Step 1: remove conflicting legacy packages ──
    for import_name, pip_pkg, reason in MIGRATIONS:
        step += 1
        if ui:
            ui.set_progress(step / total_steps)
        if _is_installed(import_name):
            status(f"Removing legacy package: {pip_pkg}")
            log(f"Uninstalling {pip_pkg} ({reason})")
            code, out = _pip("uninstall", pip_pkg, "-y")
            if code == 0:
                log(f"  ✓ Removed {pip_pkg}")
                anything_installed = True
            else:
                log(f"  ! Could not remove {pip_pkg}: {out[:120]}")

    # ── Step 2: install / upgrade required packages ──
    for import_name, pip_pkg, min_ver, notes in REQUIRED:
        step += 1
        if ui:
            ui.set_progress(step / total_steps)

        if _pkg_needs_install(import_name, pip_pkg, min_ver):
            status(f"Installing {pip_pkg}…")
            log(f"Installing {pip_pkg} ({notes})")
            install_arg = f"{pip_pkg}>={min_ver}" if min_ver else pip_pkg
            code, out = _pip("install", install_arg)
            if code == 0:
                log(f"  ✓ {pip_pkg} ready")
                anything_installed = True
            else:
                log(f"  ! Failed to install {pip_pkg}: {out[:200]}")
        else:
            log(f"  ✓ {pip_pkg} already OK")

    # ── Step 3: optional packages (best-effort, no failure) ──
    for import_name, pip_pkg in OPTIONAL:
        if not _is_installed(import_name):
            log(f"Installing optional: {pip_pkg}")
            _pip("install", pip_pkg)

    if ui:
        ui.set_progress(1.0)

    return anything_installed


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ensure_dependencies(force: bool = False) -> None:
    """
    Call this at the very top of osintnews.py before any other imports.

    If any required package is missing (or the old duckduckgo-search is still
    installed), this opens a small progress window, installs everything, then
    closes the window and continues.

    Parameters
    ----------
    force : bool
        If True, always re-check even if the sentinel flag file exists.
    """
    import os

    # Use a sentinel file so we skip the check on every launch after first run
    sentinel = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", ".deps_ok",
    )

    needs_check = force or not os.path.exists(sentinel)

    # Quick check: if ddgs isn't importable we definitely need to install
    if not needs_check and not _is_installed("ddgs"):
        needs_check = True
    # Also check if the legacy package is still installed
    if not needs_check and _is_installed("duckduckgo_search"):
        needs_check = True

    if not needs_check:
        return

    # Try to show a GUI progress window; fall back to console if unavailable
    ui = None
    try:
        import tkinter as tk
        # Test that a display is available (fails on headless servers)
        test = tk.Tk()
        test.withdraw()
        test.destroy()
        ui = _InstallerWindow()
    except Exception:
        print("[OSINTNEWS setup] Installing dependencies (no GUI available)…",
              flush=True)

    try:
        _run_install(ui)
    finally:
        if ui:
            ui.close()

    # Write sentinel so we don't repeat the full check next time
    os.makedirs(os.path.dirname(sentinel), exist_ok=True)
    try:
        with open(sentinel, "w") as fh:
            fh.write("ok")
    except OSError:
        pass
