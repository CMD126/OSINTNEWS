"""
OSINTNEWS Plus - Full GUI Application
Dark-themed desktop interface with integrated RAG Intelligence Engine.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import os
import sys
import webbrowser
from queue import Queue, Empty
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.dorker   import DORK_CATEGORIES, build_dorks
from modules.searcher import run_searches_with_callback
from modules.reporter import save_report, save_report_to, save_csv, save_json, save_excel
from modules.history  import HistoryManager
from modules.notifier import notify

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
BG     = "#0d1117"
PANEL  = "#161b22"
PANEL2 = "#21262d"
BORDER = "#30363d"
ACCENT = "#58a6ff"
GREEN  = "#3fb950"
YELLOW = "#d29922"
RED_C  = "#f85149"
PURPLE = "#bc8cff"
TEXT   = "#c9d1d9"
MUTED  = "#8b949e"
WHITE  = "#f0f6fc"

FN      = ("Segoe UI", 10)
FN_BOLD = ("Segoe UI", 10, "bold")
FN_MONO = ("Consolas",  9)
FN_SM   = ("Segoe UI",  9)

SETTINGS_PATH = os.path.join(ROOT, "data", "settings.json")
HISTORY_PATH  = os.path.join(ROOT, "data", "history.json")

# ---------------------------------------------------------------------------
# Widget helpers
# ---------------------------------------------------------------------------

def btn(parent, text, cmd, bg=PANEL2, fg=TEXT, font=FN, padx=10, pady=6, **kw):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=bg, fg=fg,
        activebackground=BORDER, activeforeground=WHITE,
        relief="flat", cursor="hand2",
        font=font, padx=padx, pady=pady, bd=0, **kw,
    )

def lbl(parent, text, fg=MUTED, font=FN_SM, **kw):
    return tk.Label(parent, text=text, bg=BG, fg=fg, font=font, **kw)

def sep(parent, color=BORDER):
    return tk.Frame(parent, bg=color, height=1)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class OSINTNewsApp:
    def __init__(self, root: tk.Tk):
        self.root    = root
        self.results: list = []
        self.queue:    Queue = Queue()
        self.ai_queue: Queue = Queue()
        self._search_thread: threading.Thread | None = None
        self._ai_thread:     threading.Thread | None = None
        self.history        = HistoryManager(HISTORY_PATH)
        self.settings       = self._load_settings()
        self._last_analysis = None   # latest AIAnalysis object

        self._setup_window()
        self._setup_styles()
        self._build_ui()
        self._poll_queue()
        self._poll_ai_queue()

    # ------------------------------------------------------------------
    # Window / style setup
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.root.title("OSINTNEWS Plus — OSINT Intelligence Engine")
        self.root.geometry("1200x820")
        self.root.minsize(980, 660)
        self.root.configure(bg=BG)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEXT, font=FN,
                    bordercolor=BORDER, focuscolor=ACCENT)
        s.configure("TFrame",    background=BG)
        s.configure("TLabel",    background=BG, foreground=TEXT)
        s.configure("TLabelframe",       background=BG, foreground=MUTED, bordercolor=BORDER)
        s.configure("TLabelframe.Label", background=BG, foreground=MUTED, font=FN_SM)
        s.configure("TNotebook",         background=PANEL, bordercolor=BORDER, tabmargins=[2,2,0,0])
        s.configure("TNotebook.Tab",     background=PANEL, foreground=MUTED, padding=[16,8], font=FN)
        s.map("TNotebook.Tab",
            background=[("selected", BG),     ("active", PANEL2)],
            foreground=[("selected", ACCENT),  ("active", TEXT)],
        )
        s.configure("TButton",      background=PANEL2, foreground=TEXT, padding=[8,4])
        s.map("TButton",            background=[("active", BORDER)])
        s.configure("TCheckbutton", background=BG, foreground=TEXT)
        s.map("TCheckbutton",       background=[("active", BG)])
        s.configure("TEntry",
            fieldbackground=PANEL, foreground=TEXT,
            bordercolor=BORDER, insertcolor=TEXT)
        s.configure("TCombobox",
            fieldbackground=PANEL, background=PANEL2,
            foreground=TEXT, selectbackground=ACCENT, arrowcolor=MUTED)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)])
        s.configure("Treeview",
            background=PANEL, foreground=TEXT, fieldbackground=PANEL,
            rowheight=28, bordercolor=BORDER)
        s.configure("Treeview.Heading",
            background=PANEL2, foreground=MUTED, bordercolor=BORDER, relief="flat")
        s.map("Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", WHITE)])
        s.configure("TProgressbar",
            troughcolor=PANEL, background=ACCENT,
            bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)
        s.configure("TScrollbar",
            background=PANEL2, troughcolor=PANEL,
            arrowcolor=MUTED, bordercolor=BORDER)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=PANEL, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  OSINTNEWS Plus", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=10, pady=10)
        tk.Label(hdr, text="OSINT Intelligence + RAG Engine", bg=PANEL, fg=MUTED,
                 font=FN_SM).pack(side="left", pady=18)
        sep(self.root).pack(fill="x")

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True)

        self.tab_search   = ttk.Frame(self.nb)
        self.tab_results  = ttk.Frame(self.nb)
        self.tab_ai       = ttk.Frame(self.nb)
        self.tab_history  = ttk.Frame(self.nb)
        self.tab_settings = ttk.Frame(self.nb)

        self.nb.add(self.tab_search,   text="  Search  ")
        self.nb.add(self.tab_results,  text="  Results  ")
        self.nb.add(self.tab_ai,       text="  AI Analysis  ")
        self.nb.add(self.tab_history,  text="  History  ")
        self.nb.add(self.tab_settings, text="  Settings  ")

        self._build_search_tab()
        self._build_results_tab()
        self._build_ai_tab()
        self._build_history_tab()
        self._build_settings_tab()

        sep(self.root).pack(fill="x")
        sb = tk.Frame(self.root, bg=PANEL, height=30)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(sb, textvariable=self.status_var, bg=PANEL, fg=MUTED,
                 font=FN_SM, anchor="w").pack(side="left", padx=12, fill="x", expand=True)
        self.progress = ttk.Progressbar(sb, mode="indeterminate", length=160)
        self.progress.pack(side="right", padx=10, pady=4)

    # ==================================================================
    # SEARCH TAB
    # ==================================================================

    def _build_search_tab(self):
        p    = self.tab_search
        left = tk.Frame(p, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=20, pady=16)
        right = tk.Frame(p, bg=BG, width=255)
        right.pack(side="right", fill="y", padx=20, pady=16)
        right.pack_propagate(False)

        lbl(left, "Target(s)  —  one per line for multiple targets").pack(anchor="w")
        self.target_text = tk.Text(
            left, height=4, bg=PANEL, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=FN, wrap="word",
            highlightbackground=BORDER, highlightthickness=1,
        )
        self.target_text.pack(fill="x", pady=(4, 14))

        cat_hdr = tk.Frame(left, bg=BG)
        cat_hdr.pack(fill="x")
        lbl(cat_hdr, "Dork Categories").pack(side="left")
        btn(cat_hdr, "None", self._cats_none, bg=PANEL2, fg=MUTED, font=FN_SM, padx=6, pady=2).pack(side="right", padx=(4, 0))
        btn(cat_hdr, "All",  self._cats_all,  bg=PANEL2, fg=MUTED, font=FN_SM, padx=6, pady=2).pack(side="right")

        cat_wrap = tk.Frame(left, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        cat_wrap.pack(fill="x", pady=(4, 14))

        self.cat_vars: dict[str, tk.BooleanVar] = {}
        for i, (key, cat) in enumerate(DORK_CATEGORIES.items()):
            var = tk.BooleanVar(value=True)
            self.cat_vars[key] = var
            row, col = divmod(i, 2)
            tk.Checkbutton(
                cat_wrap, text=f"[{key:>2}]  {cat['name']}",
                variable=var, bg=PANEL, fg=TEXT, selectcolor=PANEL2,
                activebackground=PANEL, activeforeground=TEXT, font=FN_SM, anchor="w",
            ).grid(row=row, column=col, sticky="w", padx=12, pady=3)

        cat_wrap.columnconfigure(0, weight=1)
        cat_wrap.columnconfigure(1, weight=1)

        self.run_btn = tk.Button(
            left, text="  ▶  RUN SEARCH  ", command=self.run_search,
            bg=ACCENT, fg=WHITE, activebackground="#388bfd", activeforeground=WHITE,
            relief="flat", cursor="hand2", font=("Segoe UI", 12, "bold"), pady=10, bd=0,
        )
        self.run_btn.pack(fill="x")

        def opt(text):
            lbl(right, text).pack(anchor="w", pady=(14, 2))

        opt("Date Filter")
        self.date_var = tk.StringVar(value="Any time")
        ttk.Combobox(right, textvariable=self.date_var,
                     values=["Any time", "Past day", "Past week", "Past month", "Past year"],
                     state="readonly", font=FN).pack(fill="x")

        opt("Max Results per Category")
        max_row = tk.Frame(right, bg=BG)
        max_row.pack(fill="x")
        self.max_var = tk.IntVar(value=int(self.settings.get("max_results", 10)))
        self.max_lbl = tk.Label(max_row, text=str(self.max_var.get()),
                                bg=BG, fg=ACCENT, font=FN_BOLD, width=3)
        self.max_lbl.pack(side="right")
        ttk.Scale(max_row, from_=3, to=50, variable=self.max_var, orient="horizontal",
                  command=lambda v: self.max_lbl.config(text=str(int(float(v))))).pack(fill="x", expand=True)

        opt("Delay between queries (s)")
        self.delay_var = tk.DoubleVar(value=float(self.settings.get("delay", 1.5)))
        ttk.Entry(right, textvariable=self.delay_var, font=FN).pack(fill="x")

        opt("Proxy (optional)")
        lbl(right, "e.g. http://127.0.0.1:8080", font=("Segoe UI", 8)).pack(anchor="w")
        self.proxy_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.proxy_var, font=FN_MONO).pack(fill="x")

        opt("Keyword Filter")
        self.kw_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.kw_var, font=FN).pack(fill="x")

        opt("After Search")
        self.auto_ai_var = tk.BooleanVar(value=self.settings.get("auto_ai", False))
        tk.Checkbutton(right, text="Auto-run AI Analysis",
                       variable=self.auto_ai_var, bg=BG, fg=TEXT, selectcolor=PANEL2,
                       activebackground=BG, activeforeground=TEXT, font=FN_SM).pack(anchor="w")

    def _cats_all(self):
        for v in self.cat_vars.values(): v.set(True)

    def _cats_none(self):
        for v in self.cat_vars.values(): v.set(False)

    # ==================================================================
    # RESULTS TAB
    # ==================================================================

    def _build_results_tab(self):
        p  = self.tab_results
        tb = tk.Frame(p, bg=PANEL, height=46)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        self.res_count_var = tk.StringVar(value="No results yet")
        tk.Label(tb, textvariable=self.res_count_var, bg=PANEL, fg=MUTED,
                 font=FN_SM).pack(side="left", padx=14, pady=14)

        self.ai_btn = tk.Button(
            tb, text="✦ Generate AI Analysis", command=self.run_ai_analysis,
            bg=PURPLE, fg=WHITE, activebackground="#a371f7", activeforeground=WHITE,
            relief="flat", cursor="hand2", font=FN_SM, padx=10, pady=10, bd=0,
        )
        self.ai_btn.pack(side="right", padx=8)

        for label_text, cmd, color in [
            ("Excel", self.export_excel, GREEN),
            ("JSON",  self.export_json,  ACCENT),
            ("CSV",   self.export_csv,   YELLOW),
            ("HTML",  self.export_html,  RED_C),
        ]:
            btn(tb, f"Export {label_text}", cmd, bg=PANEL2, fg=color, font=FN_SM, padx=10, pady=10).pack(side="right", padx=2)

        sep(p).pack(fill="x")
        wrap = tk.Frame(p, bg=BG)
        wrap.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(wrap)
        vsb.pack(side="right", fill="y")

        self.res_text = tk.Text(
            wrap, bg=BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=FN, wrap="word",
            yscrollcommand=vsb.set, cursor="arrow", state="disabled",
            padx=22, pady=16,
        )
        self.res_text.pack(fill="both", expand=True)
        vsb.config(command=self.res_text.yview)

        self.res_text.tag_configure("cat",   foreground=YELLOW, font=("Segoe UI", 11, "bold"))
        self.res_text.tag_configure("tgt",   foreground=MUTED,  font=FN_SM)
        self.res_text.tag_configure("sep",   foreground=PANEL2)
        self.res_text.tag_configure("num",   foreground=MUTED)
        self.res_text.tag_configure("title", foreground=ACCENT, font=FN_BOLD)
        self.res_text.tag_configure("url",   foreground=GREEN,  font=FN_MONO)
        self.res_text.tag_configure("body",  foreground=MUTED,  font=FN_SM)

    def _display_results(self, results: list):
        self.res_text.config(state="normal")
        self.res_text.delete("1.0", "end")
        if not results:
            self.res_text.insert("end", "\n  No results yet…", "body")
            self.res_text.config(state="disabled")
            return

        cats: dict = {}
        for r in results:
            cats.setdefault(r.get("category", "Unknown"), []).append(r)

        idx = 1
        for cat, items in cats.items():
            self.res_text.insert("end", f"\n  [{cat}]", "cat")
            self.res_text.insert("end", f"  ({len(items)} results)\n", "tgt")
            self.res_text.insert("end", "  " + "─" * 68 + "\n", "sep")
            for r in items:
                title = r.get("title", "No title")
                url   = r.get("href",  "")
                body  = (r.get("body", "") or "")
                snip  = (body[:200] + "…") if len(body) > 200 else body
                tgt   = r.get("target", "")
                self.res_text.insert("end", f"\n  {idx}. ", "num")
                self.res_text.insert("end", title + "\n", "title")
                if tgt:
                    self.res_text.insert("end", f"     ↳ {tgt}\n", "tgt")
                self.res_text.insert("end", f"     {url}\n", "url")
                if snip:
                    self.res_text.insert("end", f"     {snip}\n", "body")
                idx += 1

        self.res_text.config(state="disabled")
        self.res_count_var.set(f"{len(results)} results  ·  {len(cats)} categories")

    # ==================================================================
    # AI ANALYSIS TAB
    # ==================================================================

    def _build_ai_tab(self):
        p  = self.tab_ai
        tb = tk.Frame(p, bg=PANEL, height=46)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        self.ai_status_var = tk.StringVar(value="No analysis yet — run a search first.")
        tk.Label(tb, textvariable=self.ai_status_var, bg=PANEL, fg=MUTED,
                 font=FN_SM).pack(side="left", padx=14, pady=14)

        self.risk_badge_var = tk.StringVar(value="")
        self.risk_badge_lbl = tk.Label(tb, textvariable=self.risk_badge_var,
                                       bg=PANEL, fg=MUTED, font=FN_BOLD, padx=12, pady=6)
        self.risk_badge_lbl.pack(side="right", padx=12)

        btn(tb, "Export AI Report", self.export_ai_report, bg=PANEL2, fg=ACCENT, font=FN_SM, pady=8).pack(side="right", padx=4)
        btn(tb, "✦ Run Analysis",  self.run_ai_analysis,   bg=PURPLE, fg=WHITE,  font=FN_SM, pady=8).pack(side="right", padx=4)

        sep(p).pack(fill="x")
        wrap = tk.Frame(p, bg=BG)
        wrap.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(wrap)
        vsb.pack(side="right", fill="y")

        self.ai_text = tk.Text(
            wrap, bg=BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=("Segoe UI", 10), wrap="word",
            yscrollcommand=vsb.set, cursor="arrow", state="disabled",
            padx=28, pady=20,
        )
        self.ai_text.pack(fill="both", expand=True)
        vsb.config(command=self.ai_text.yview)

        self.ai_text.tag_configure("h2",    foreground="#f78166", font=("Segoe UI", 12, "bold"))
        self.ai_text.tag_configure("h3",    foreground=YELLOW,    font=("Segoe UI", 11, "bold"))
        self.ai_text.tag_configure("body",  foreground=TEXT,      font=("Segoe UI", 10))
        self.ai_text.tag_configure("bold",  foreground=WHITE,     font=("Segoe UI", 10, "bold"))
        self.ai_text.tag_configure("cite",  foreground=ACCENT,    font=FN_MONO)
        self.ai_text.tag_configure("url",   foreground=GREEN,     font=FN_MONO)
        self.ai_text.tag_configure("muted", foreground=MUTED,     font=FN_SM)
        self.ai_text.tag_configure("error", foreground=RED_C,     font=FN_MONO)

    def _display_ai_analysis(self, analysis):
        import re
        self.ai_text.config(state="normal")
        self.ai_text.delete("1.0", "end")

        if not analysis.succeeded:
            self.ai_text.insert("end", "\n  ✗ AI Analysis Failed\n\n", "error")
            self.ai_text.insert("end", f"  {analysis.error or 'Unknown error'}\n", "error")
            self.ai_text.config(state="disabled")
            return

        for line in analysis.summary.split("\n"):
            ls = line.strip()
            if ls.startswith("## "):
                self.ai_text.insert("end", "\n" + ls[3:] + "\n", "h2")
            elif ls.startswith("### "):
                self.ai_text.insert("end", "\n" + ls[4:] + "\n", "h3")
            elif ls.startswith("- ") or ls.startswith("• "):
                self.ai_text.insert("end", "  • ", "muted")
                self._insert_inline(ls[2:])
                self.ai_text.insert("end", "\n", "body")
            elif ls == "":
                self.ai_text.insert("end", "\n", "body")
            else:
                self._insert_inline(ls)
                self.ai_text.insert("end", "\n", "body")

        if analysis.cited_sources:
            self.ai_text.insert("end", "\n\nCited Sources\n", "h3")
            self.ai_text.insert("end", "─" * 60 + "\n", "muted")
            for i, url in enumerate(analysis.cited_sources, 1):
                self.ai_text.insert("end", f"  [{i}] ", "cite")
                self.ai_text.insert("end", url + "\n", "url")

        self.ai_text.insert("end",
            f"\n\nModel: {analysis.model}  ·  Sources analysed: {analysis.source_count}\n", "muted")
        self.ai_text.config(state="disabled")

    def _insert_inline(self, text: str):
        import re
        pattern = re.compile(r'(\*\*[^*]+\*\*|\[Source\s+\d+\])')
        for part in pattern.split(text):
            if part.startswith("**") and part.endswith("**"):
                self.ai_text.insert("end", part[2:-2], "bold")
            elif part.startswith("[Source"):
                self.ai_text.insert("end", part, "cite")
            else:
                self.ai_text.insert("end", part, "body")

    # ==================================================================
    # HISTORY TAB
    # ==================================================================

    def _build_history_tab(self):
        p  = self.tab_history
        tb = tk.Frame(p, bg=PANEL, height=46)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="Search History", bg=PANEL, fg=TEXT, font=FN_BOLD).pack(side="left", padx=14, pady=14)
        btn(tb, "Clear All", self._hist_clear,   bg=PANEL2, fg=RED_C, font=FN_SM, pady=8).pack(side="right", padx=8)
        btn(tb, "Refresh",   self._hist_refresh, bg=PANEL2, fg=MUTED, font=FN_SM, pady=8).pack(side="right")
        sep(p).pack(fill="x")

        wrap = tk.Frame(p, bg=BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=12)

        cols = ("date", "targets", "cats", "results", "risk", "report")
        self.hist_tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for col, heading, width in [
            ("date",    "Date / Time",  160),
            ("targets", "Target(s)",    220),
            ("cats",    "Categories",   100),
            ("results", "Results",       80),
            ("risk",    "AI Risk",       90),
            ("report",  "Report",        80),
        ]:
            self.hist_tree.heading(col, text=heading)
            self.hist_tree.column(col, width=width, anchor="w")

        vsb = ttk.Scrollbar(wrap, orient="vertical",   command=self.hist_tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.hist_tree.xview)
        self.hist_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.hist_tree.pack(fill="both", expand=True)
        self.hist_tree.bind("<Double-1>", lambda e: self._hist_open_report())

        abf = tk.Frame(p, bg=BG)
        abf.pack(fill="x", padx=16, pady=(0, 12))
        btn(abf, "Re-run Selected", self._hist_rerun,       bg=ACCENT, fg=WHITE, font=FN_SM, padx=12, pady=6).pack(side="left", padx=(0, 6))
        btn(abf, "Open Report",     self._hist_open_report, bg=PANEL2, fg=GREEN, font=FN_SM, padx=12, pady=6).pack(side="left", padx=(0, 6))
        btn(abf, "Delete Selected", self._hist_delete,      bg=PANEL2, fg=RED_C, font=FN_SM, padx=12, pady=6).pack(side="left")
        self._hist_refresh()

    def _hist_refresh(self):
        for item in self.hist_tree.get_children():
            self.hist_tree.delete(item)
        for e in self.history.all():
            self.hist_tree.insert("", "end", iid=e["id"], values=(
                e.get("date", ""),
                e.get("targets", ""),
                str(e.get("categories", "")),
                str(e.get("result_count", 0)),
                e.get("risk_level", "—"),
                "Open" if (e.get("report_path") and os.path.exists(e.get("report_path", ""))) else "—",
            ))

    def _hist_clear(self):
        if messagebox.askyesno("Clear History", "Delete all search history?", parent=self.root):
            self.history.clear()
            self._hist_refresh()

    def _hist_delete(self):
        sel = self.hist_tree.selection()
        if sel:
            self.history.delete(sel[0])
            self._hist_refresh()

    def _hist_open_report(self):
        sel = self.hist_tree.selection()
        if not sel:
            return
        e = self.history.get(sel[0])
        if e and e.get("report_path") and os.path.exists(e["report_path"]):
            webbrowser.open(f"file:///{os.path.abspath(e['report_path'])}")
        else:
            messagebox.showinfo("No Report", "Report file not found.", parent=self.root)

    def _hist_rerun(self):
        sel = self.hist_tree.selection()
        if not sel:
            return
        e = self.history.get(sel[0])
        if e:
            self.target_text.delete("1.0", "end")
            self.target_text.insert("end", e.get("targets", ""))
            self.nb.select(self.tab_search)

    # ==================================================================
    # SETTINGS TAB
    # ==================================================================

    def _build_settings_tab(self):
        p = self.tab_settings

        canvas = tk.Canvas(p, bg=BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        fr = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=fr, anchor="nw")
        fr.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        f = tk.Frame(fr, bg=BG)
        f.pack(fill="both", expand=True, padx=44, pady=24)

        def section(text, color=MUTED):
            tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=(20, 0))
            tk.Label(f, text=text, bg=BG, fg=color, font=FN_BOLD).pack(anchor="w", pady=(8, 4))

        def opt(text, hint=""):
            lbl(f, text).pack(anchor="w", pady=(12, 2))
            if hint:
                lbl(f, hint, font=("Segoe UI", 8)).pack(anchor="w")

        # ── General ──
        section("General Settings", ACCENT)

        opt("Output Directory")
        od = tk.Frame(f, bg=BG)
        od.pack(fill="x")
        self.out_var = tk.StringVar(value=self.settings.get("output_dir", "reports"))
        ttk.Entry(od, textvariable=self.out_var, font=FN_MONO).pack(side="left", fill="x", expand=True)
        btn(od, "Browse", self._browse_dir, bg=PANEL2, fg=MUTED, font=FN_SM, padx=8, pady=4).pack(side="right", padx=(8, 0))

        opt("Default Delay between queries (s)")
        self.def_delay = tk.DoubleVar(value=self.settings.get("delay", 1.5))
        ttk.Entry(f, textvariable=self.def_delay, font=FN, width=10).pack(anchor="w")

        opt("Default Max Results per Category")
        self.def_max = tk.IntVar(value=self.settings.get("max_results", 10))
        ttk.Entry(f, textvariable=self.def_max, font=FN, width=10).pack(anchor="w")

        opt("Notifications")
        self.notif_var = tk.BooleanVar(value=self.settings.get("notifications", True))
        tk.Checkbutton(f, text="Enable Windows desktop notifications",
                       variable=self.notif_var, bg=BG, fg=TEXT, selectcolor=PANEL2,
                       activebackground=BG, activeforeground=TEXT, font=FN).pack(anchor="w")

        self.auto_open_var = tk.BooleanVar(value=self.settings.get("auto_open", True))
        tk.Checkbutton(f, text="Auto-open HTML report after search",
                       variable=self.auto_open_var, bg=BG, fg=TEXT, selectcolor=PANEL2,
                       activebackground=BG, activeforeground=TEXT, font=FN).pack(anchor="w")

        # ── AI / RAG ──
        section("AI / RAG Intelligence Engine", PURPLE)
        lbl(f, "Connects to an LLM to generate executive summaries with source citations.", fg=TEXT).pack(anchor="w", pady=(4, 0))

        opt("Provider")
        self.ai_provider_var = tk.StringVar(value=self.settings.get("ai_provider", "claude"))
        provider_cb = ttk.Combobox(f, textvariable=self.ai_provider_var,
                     values=["claude", "openai", "ollama"],
                     state="readonly", font=FN, width=20)
        provider_cb.pack(anchor="w")
        self.ai_provider_var.trace_add("write", self._on_provider_change)

        opt("API Key", "Stored in data/settings.json — sent only to the chosen provider API.")
        self.ai_key_var = tk.StringVar(value=self.settings.get("ai_api_key", ""))
        self.key_entry  = ttk.Entry(f, textvariable=self.ai_key_var, font=FN_MONO, show="•")
        self.key_entry.pack(fill="x")

        opt("Model", "Leave blank for defaults: claude-sonnet-4-6 / gpt-4o / llama3.2")
        self.ai_model_var = tk.StringVar(value=self.settings.get("ai_model", ""))
        ttk.Entry(f, textvariable=self.ai_model_var, font=FN_MONO).pack(fill="x")

        self.ollama_frame = tk.Frame(f, bg=BG)
        lbl(self.ollama_frame, "Ollama Base URL").pack(anchor="w", pady=(12, 2))
        self.ollama_url_var = tk.StringVar(value=self.settings.get("ollama_url", "http://localhost:11434"))
        ttk.Entry(self.ollama_frame, textvariable=self.ollama_url_var, font=FN_MONO).pack(fill="x")
        lbl(self.ollama_frame, "Ollama Model").pack(anchor="w", pady=(8, 2))
        self.ollama_model_var = tk.StringVar(value=self.settings.get("ollama_model", "llama3.2"))
        ttk.Entry(self.ollama_frame, textvariable=self.ollama_model_var, font=FN_MONO).pack(fill="x")

        opt("Auto-run after search")
        self.auto_ai_s_var = tk.BooleanVar(value=self.settings.get("auto_ai", False))
        tk.Checkbutton(f, text="Automatically run AI analysis after each search",
                       variable=self.auto_ai_s_var, bg=BG, fg=TEXT, selectcolor=PANEL2,
                       activebackground=BG, activeforeground=TEXT, font=FN).pack(anchor="w")

        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=(20, 0))
        btn(f, "Save Settings", self._save_settings,
            bg=GREEN, fg=WHITE, font=FN_BOLD, padx=16, pady=8).pack(anchor="w", pady=(16, 0))

        self._on_provider_change()

    def _on_provider_change(self, *_):
        if hasattr(self, "ollama_frame"):
            if self.ai_provider_var.get() == "ollama":
                self.ollama_frame.pack(fill="x")
            else:
                self.ollama_frame.pack_forget()

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get(), parent=self.root)
        if d:
            self.out_var.set(d)

    def _save_settings(self):
        self.settings.update({
            "output_dir":    self.out_var.get(),
            "delay":         self.def_delay.get(),
            "max_results":   self.def_max.get(),
            "notifications": self.notif_var.get(),
            "auto_open":     self.auto_open_var.get(),
            "ai_provider":   self.ai_provider_var.get(),
            "ai_api_key":    self.ai_key_var.get(),
            "ai_model":      self.ai_model_var.get(),
            "ollama_url":    self.ollama_url_var.get(),
            "ollama_model":  self.ollama_model_var.get(),
            "auto_ai":       self.auto_ai_s_var.get(),
        })
        self._write_settings()
        messagebox.showinfo("Settings", "Settings saved.", parent=self.root)

    # ==================================================================
    # SEARCH LOGIC
    # ==================================================================

    def run_search(self):
        if self._search_thread and self._search_thread.is_alive():
            messagebox.showwarning("Busy", "A search is already running.", parent=self.root)
            return

        raw_targets = self.target_text.get("1.0", "end").strip()
        if not raw_targets:
            messagebox.showwarning("Input Required", "Enter at least one target.", parent=self.root)
            return

        targets  = [t.strip() for t in raw_targets.splitlines() if t.strip()]
        sel_cats = [k for k, v in self.cat_vars.items() if v.get()]
        if not sel_cats:
            messagebox.showwarning("Categories", "Select at least one category.", parent=self.root)
            return

        max_results = int(self.max_var.get())
        delay       = float(self.delay_var.get() or 1.5)
        proxy       = self.proxy_var.get().strip() or None
        kw_filter   = self.kw_var.get().strip().lower()
        timelimit   = {"Any time": None, "Past day": "d", "Past week": "w",
                       "Past month": "m", "Past year": "y"}.get(self.date_var.get())

        all_dorks = []
        for t in targets:
            all_dorks.extend(build_dorks(t, sel_cats))

        self.results = []
        self._display_results([])
        self.res_count_var.set("Searching…")
        self.run_btn.config(state="disabled", text="  ⏳  SEARCHING…  ", bg=MUTED)
        self.progress.start(12)
        self.status_var.set(f"Running {len(all_dorks)} queries…")
        self.nb.select(self.tab_results)

        def _worker():
            def on_result(r): self.queue.put(("result", r))
            def on_status(m): self.queue.put(("status", m))
            try:
                results = run_searches_with_callback(
                    all_dorks, max_results=max_results, delay=delay,
                    proxy=proxy, timelimit=timelimit,
                    on_result=on_result, on_status=on_status,
                )
                if kw_filter:
                    results = [r for r in results
                               if kw_filter in (r.get("title","") + r.get("body","")).lower()]
                self.queue.put(("done", (results, targets, sel_cats)))
            except Exception as exc:
                self.queue.put(("error", str(exc)))

        self._search_thread = threading.Thread(target=_worker, daemon=True)
        self._search_thread.start()

    def _poll_queue(self):
        try:
            while True:
                msg_type, payload = self.queue.get_nowait()
                if msg_type == "result":
                    self.results.append(payload)
                    self._display_results(self.results)
                elif msg_type == "status":
                    self.status_var.set(payload)
                elif msg_type == "done":
                    results, targets, cats = payload
                    self.results = results
                    self._on_search_done(results, targets, cats)
                elif msg_type == "error":
                    self.progress.stop()
                    self.run_btn.config(state="normal", text="  ▶  RUN SEARCH  ", bg=ACCENT)
                    messagebox.showerror("Search Error", payload, parent=self.root)
                    self.status_var.set("Error.")
        except Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _on_search_done(self, results: list, targets: list, cats: list):
        self.progress.stop()
        self.run_btn.config(state="normal", text="  ▶  RUN SEARCH  ", bg=ACCENT)
        self._display_results(results)
        self.status_var.set(f"Done  ·  {len(results)} results  ·  {len(targets)} target(s)")

        report_path = None
        if results:
            out_dir     = self.settings.get("output_dir", "reports")
            target_str  = ", ".join(targets)
            report_path = save_report(results, target_str, out_dir)
            if self.settings.get("auto_open", True):
                webbrowser.open(f"file:///{os.path.abspath(report_path)}")

        self.history.add({
            "targets":      ", ".join(targets),
            "categories":   len(cats),
            "result_count": len(results),
            "report_path":  report_path or "",
            "risk_level":   "—",
        })
        self._hist_refresh()

        if self.settings.get("notifications", True):
            notify("OSINTNEWS Plus — Search Complete",
                   f"{len(results)} results for: {', '.join(targets)}")

        if self.settings.get("auto_ai", False) or self.auto_ai_var.get():
            self.root.after(600, self.run_ai_analysis)

    # ==================================================================
    # AI ANALYSIS LOGIC
    # ==================================================================

    def run_ai_analysis(self):
        if not self.results:
            messagebox.showwarning("No Results", "Run a search first.", parent=self.root)
            return
        if self._ai_thread and self._ai_thread.is_alive():
            messagebox.showwarning("Busy", "AI analysis is already running.", parent=self.root)
            return

        provider     = self.settings.get("ai_provider",  "claude")
        api_key      = self.settings.get("ai_api_key",   "")
        model        = self.settings.get("ai_model",     "")
        ollama_url   = self.settings.get("ollama_url",   "http://localhost:11434")
        ollama_model = self.settings.get("ollama_model", "llama3.2")

        if provider in ("claude", "openai") and not api_key:
            messagebox.showerror("API Key Required",
                f"Set your {provider.title()} API key in Settings → AI/RAG section.",
                parent=self.root)
            self.nb.select(self.tab_settings)
            return

        targets    = list({r.get("target", "") for r in self.results if r.get("target")})
        target_str = ", ".join(targets) if targets else "Unknown"

        self.nb.select(self.tab_ai)
        self.ai_status_var.set(f"Running AI analysis via {provider}…")
        self.risk_badge_var.set("")
        self.progress.start(12)
        self.status_var.set(f"AI analysis via {provider} ({len(self.results)} sources)…")

        self.ai_text.config(state="normal")
        self.ai_text.delete("1.0", "end")
        self.ai_text.insert("end", f"\n  Analysing {len(self.results)} sources via {provider}…\n", "muted")
        self.ai_text.config(state="disabled")

        raw = self.results[:]

        def _ai_worker():
            try:
                from modules.rag.pipeline import run_multi_target_pipeline
                pipeline_results = run_multi_target_pipeline(
                    raw_results  = raw,
                    targets      = targets if targets else [target_str],
                    provider     = provider,
                    api_key      = api_key,
                    model        = model,
                    ollama_url   = ollama_url,
                    ollama_model = ollama_model,
                )
                self.ai_queue.put(("ai_done", pipeline_results))
            except Exception as exc:
                self.ai_queue.put(("ai_error", str(exc)))

        self._ai_thread = threading.Thread(target=_ai_worker, daemon=True)
        self._ai_thread.start()

    def _poll_ai_queue(self):
        try:
            while True:
                msg_type, payload = self.ai_queue.get_nowait()

                if msg_type == "ai_done":
                    self.progress.stop()
                    pipeline_results = payload
                    primary = pipeline_results[0] if pipeline_results else None

                    if primary and primary.analysis.succeeded:
                        analysis = primary.analysis
                        self._last_analysis = analysis
                        self.risk_badge_var.set(f"  {analysis.risk_level}  ")
                        self.risk_badge_lbl.config(fg=analysis.risk_color_hex)
                        self.ai_status_var.set(
                            f"Complete  ·  {analysis.source_count} sources  ·  "
                            f"{len(analysis.cited_sources)} cited  ·  {analysis.model}"
                        )
                        self._display_ai_analysis(analysis)
                        self.status_var.set(f"AI analysis complete — Risk: {analysis.risk_level}")

                        # Update latest history entry with risk level
                        if self.history.entries:
                            self.history.entries[-1]["risk_level"] = analysis.risk_level
                            self.history._save()
                            self._hist_refresh()

                        if self.settings.get("notifications", True):
                            notify("OSINTNEWS Plus — AI Analysis Complete",
                                   f"Risk: {analysis.risk_level}  ·  {analysis.source_count} sources")

                    elif primary:
                        self._display_ai_analysis(primary.analysis)
                        self.ai_status_var.set(f"Failed: {primary.analysis.error}")
                        self.status_var.set("AI analysis failed.")

                elif msg_type == "ai_error":
                    self.progress.stop()
                    messagebox.showerror("AI Error", payload, parent=self.root)
                    self.ai_status_var.set("Error.")
                    self.status_var.set("AI error.")

        except Empty:
            pass
        self.root.after(150, self._poll_ai_queue)

    # ==================================================================
    # EXPORTS
    # ==================================================================

    def _check_results(self) -> bool:
        if not self.results:
            messagebox.showinfo("Export", "No results to export.", parent=self.root)
            return False
        return True

    def export_html(self):
        if not self._check_results(): return
        path = filedialog.asksaveasfilename(parent=self.root,
            defaultextension=".html", filetypes=[("HTML", "*.html")],
            initialfile="osintnews_export.html")
        if path:
            save_report_to(self.results, "Export", path, self._last_analysis)
            messagebox.showinfo("Export", f"HTML saved:\n{path}", parent=self.root)

    def export_csv(self):
        if not self._check_results(): return
        path = filedialog.asksaveasfilename(parent=self.root,
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="osintnews_export.csv")
        if path:
            save_csv(self.results, path)
            messagebox.showinfo("Export", f"CSV saved:\n{path}", parent=self.root)

    def export_json(self):
        if not self._check_results(): return
        path = filedialog.asksaveasfilename(parent=self.root,
            defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile="osintnews_export.json")
        if path:
            save_json(self.results, path)
            messagebox.showinfo("Export", f"JSON saved:\n{path}", parent=self.root)

    def export_excel(self):
        if not self._check_results(): return
        path = filedialog.asksaveasfilename(parent=self.root,
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile="osintnews_export.xlsx")
        if path:
            try:
                save_excel(self.results, path)
                messagebox.showinfo("Export", f"Excel saved:\n{path}", parent=self.root)
            except ImportError:
                messagebox.showerror("Missing Dependency", "Run: pip install openpyxl", parent=self.root)

    def export_ai_report(self):
        if not self._last_analysis:
            messagebox.showinfo("No Analysis", "Run AI analysis first.", parent=self.root)
            return
        if not self.results:
            return
        path = filedialog.asksaveasfilename(parent=self.root,
            defaultextension=".html", filetypes=[("HTML", "*.html")],
            initialfile="osintnews_ai_report.html")
        if path:
            save_report_to(self.results, self._last_analysis.target, path, self._last_analysis)
            webbrowser.open(f"file:///{os.path.abspath(path)}")

    # ==================================================================
    # Settings persistence
    # ==================================================================

    def _load_settings(self) -> dict:
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                pass
        return {"output_dir": "reports", "delay": 1.5, "max_results": 10,
                "notifications": True, "auto_open": True, "auto_ai": False,
                "ai_provider": "claude", "ai_api_key": "", "ai_model": "",
                "ollama_url": "http://localhost:11434", "ollama_model": "llama3.2"}

    def _write_settings(self):
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(self.settings, fh, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def launch():
    root = tk.Tk()
    OSINTNewsApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
