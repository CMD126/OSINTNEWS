# Changelog

All notable changes to OSINTNEWS Plus are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.1.0] — 2026-08-27

### 🐛 Fixed
- **`modules/searcher.py`** — proxied searches crashed on every query with
  `ddgs >= 9`. The old `proxies={...}` dict is now sent as `proxy="…"`, so the
  GUI Proxy field works again.
- **`modules/searcher.py`** — `ddgs` raises `DDGSException("No results found.")`
  instead of returning `[]`. This was retried 3× with back-off and logged as an
  ERROR. It is now recognised as a normal empty result (no retry, no error).
- **CLI export** — the HTML export printed a filename that did not exist
  (`save_report` chooses its own timestamped name). It now reports the real path
  returned by the reporter, and each export format is isolated so one failure
  no longer aborts the rest.
- **`modules/dork_common.py`** — phone country-code stripping was greedy:
  `+441234567890` became `441234567890` → `1234567890` lost a digit, and UK
  `+44` was misread as `+441`. Now uses a real ITU-T calling-code table with
  longest-prefix match.
- **`modules/rag/retriever.py`** — the "CJK" filter never matched Korean
  Hangul (`0xAC00–0xD7FF` etc. were missing). Korean-script results now filter
  like Chinese/Japanese ones. *(caught by a new test)*
- **`modules/rag/generator.py`** — non-streaming Claude path read
  `response.content[0].text` blindly; it now skips non-text leading blocks and
  surfaces a `refusal` stop reason as a clean error.

### 🧪 Tests
- New `pytest` suite (`tests/`, 66 cases, no network): retry/rate-limit/
  no-results classifiers + parallel orchestration with `ddgs` stubbed
  (`test_searcher.py`); CJK / relevance / dedup / pipeline filters
  (`test_retriever.py`); dork builders incl. every phone-format case
  (`test_dorker.py`); history persistence + `update()` (`test_history.py`).
  Run with `pytest`.

### 🆕 New
- **CLI `--ai` / `--provider`** now actually run the RAG pipeline over the
  results (streamed to the terminal) and embed the analysis in HTML/Markdown
  exports — previously the flags were parsed and ignored. Interactive mode
  offers the same via a prompt.
- **`.env` support** — the CLI loads `KEY=VALUE` pairs from a project-root
  `.env` on startup (never overrides real env vars). See `.env.example`.
- **`modules/searcher.py`** — optional `region` (e.g. `pt-pt`) and `backend`
  selectors; typed `ddgs` exceptions re-exported for callers/tests.
- **CLI** — target sanity check warns on malformed email / short username /
  single-word name / too-few-digit phone before burning queries.
- **CLI** — `colorama.just_fix_windows_console()` so ANSI colours render on
  legacy Windows terminals.

### ✨ Changed
- **`modules/installer.py`** — `anthropic` and `openai` moved from *required* to
  *optional* (the tool is fully usable without any AI provider, matching
  `requirements.txt`). `pip` calls now have a timeout and never raise. The
  `data/.deps_ok` sentinel is only written once every **required** package is
  importable, so a one-off offline launch no longer disables setup forever.
- **`requirements.txt`** — restructured into Core / Recommended / Optional; `ddgs`
  documented as the real core package.
- **`modules/dork_common.py`** (new) — `dorker.py` and `dorker_osint.py` shared
  three near-identical helpers (`_sanitize`, phone stripping, the
  `{target}` substitution loop). That logic now lives in one module; the two
  builders keep only their category tables. Old private names are kept as
  aliases for compatibility.
- **`modules/rag/generator.py`** — per-provider default models centralised in a
  `DEFAULT_MODELS` dict and refreshed: `claude-sonnet-5`, `gpt-5`,
  `gemini-2.5-flash`, `llama3.2`. Override via the GUI **Model** field or the
  RAG API's `model=` argument.
- **`modules/history.py`** / **GUI** — new `HistoryManager.update(entry_id,
  **fields)`; the GUI no longer reaches into `history.entries[-1]` and calls the
  private `_save()` to tag the AI risk level, so a second search started while
  analysis is still running can't overwrite the wrong row.

---

## [2.0.0] — 2026-04-01

### 🆕 New — CLI becomes a dedicated OSINT Identity Tool
- **CLI completely rewritten** as a focused OSINT identity search tool
- 4 search modes: **username**, **email**, **phone**, **person**
- 32 purpose-built dork templates across all modes (`modules/dorker_osint.py`)
  - Username: Twitter/X, Instagram, TikTok, Reddit, GitHub, LinkedIn, YouTube, Discord, Steam/Twitch, Forums, Paste/Leaks, Web Archive
  - Email: social media, professional, code repos, breach/paste, forums, domain intel, PDFs
  - Phone: social media, people directories, classifieds, leaks, business pages
  - Person: social media, news, court records, company filings, academic, forums, PDFs, leaks
- Interactive guided prompts — run with no arguments for a menu-driven experience
- Results exported as JSON, CSV, or plain TXT
- CLI is now completely separate from the GUI (GUI stays focused on news)

### 🆕 New — Auto-Installer (`modules/installer.py`)
- First-time setup runs automatically on launch — no manual `pip install` needed
- Shows a friendly GUI progress window during installation
- Automatically migrates `duckduckgo-search` → `ddgs` (fixes warning spam)
- Uses a sentinel file so the check is near-instant on subsequent launches
- Falls back to console output if tkinter is unavailable (headless servers)

### 🆕 New — Google Gemini AI provider
- Added `gemini` as a 4th AI provider (`gemini-1.5-flash` default)
- Supports streaming output via `on_token` callback
- Env var: `GOOGLE_API_KEY`
- Available in both GUI (Settings tab) and CLI (`--provider gemini`)

### ✨ Improved — Ollama now supports streaming
- `generate_with_ollama` now streams token-by-token via `/api/generate` with `stream=True`
- Same live output experience as Claude/OpenAI/Gemini

### ✨ Improved — Search engine (`modules/searcher.py`)
- **Adaptive rate-limit detection** — recognises 429 / "rate limit" / "blocked" errors and uses a much longer exponential back-off window
- **Staggered worker start** — workers spread their first request across the delay window to prevent thundering-herd API hits
- **Cross-worker URL deduplication** — duplicate URLs removed in real-time, not just at the end
- New `on_progress(done, total)` callback for live progress tracking
- New `stop_event` parameter for clean, interruptible cancellation
- Interruptible sleep — cancel wakes up mid-sleep instead of waiting for the full delay

### ✨ Improved — GUI (`modules/gui/app.py`)
- **Progress bar** switched from indeterminate spinner to determinate **X/Y%** counter
- **Clickable URLs** — click any green URL in the results pane to open it in the browser
- **Real-time CJK filter** — Chinese/Japanese/Korean results are now filtered before they appear, not just at the end of the search
- **Reports folder fix** — output path is now always absolute (relative to the project root), preventing `PermissionError` when launching from outside the project directory
- Gemini added to the provider dropdown in Settings
- New **Max AI Output Tokens** slider in Settings (1000–8000)
- `stop_event` wired to the Cancel button for clean thread cancellation
- Streaming now enabled for all providers (including Gemini and Ollama)
- Fixed: cancel-flag check was happening after it was already cleared
- Fixed: `ai_error` message handler was incorrectly nested inside `elif primary:`

### ✨ Improved — AI pipeline
- `max_tokens` now configurable throughout (raised default: 3000 → 4000)
- `max_tokens` threaded through `generate()` → `generation_step()` → `run_pipeline()`
- Fixed: Ollama `generate()` dispatch was using positional args in wrong order
- Type annotations added to all generator functions

### ✨ Improved — Retriever (`modules/rag/retriever.py`)
- CJK detection rewritten as early-return loop (was O(n×m) nested generator)

### 📦 Dependencies (`requirements.txt`)
- `duckduckgo-search` → `ddgs>=0.1.0` (package renamed upstream)
- `anthropic` bumped to `>=0.49.0`
- `requests` bumped to `>=2.32.0`
- Added `google-generativeai>=0.8.0` (Gemini)

---

## [1.1.0] — 2025-03-14

### Added
- RAG AI engine with Claude, OpenAI, and Ollama support
- Streaming AI output (token-by-token) for Claude and OpenAI
- Risk assessment badge: LOW / MEDIUM / HIGH / CRITICAL
- Source citations: every AI claim cites `[Source N]`
- Intelligence Gaps section in AI reports
- Search history with persistent JSON storage
- Export: Excel (.xlsx) and Markdown formats
- GUI: AI Analysis tab with streaming text widget
- GUI: History tab with re-run and report access
- GUI: Settings tab with persistent API key and provider config
- CLI: `--ai`, `--provider`, `--api-key`, `--model` flags
- Cancel button to stop a running search mid-way
- GitHub, Academic, Video, and Telegram dork categories (15–18)
- CJK / blocked-domain filter to remove irrelevant foreign results

### Fixed
- Duplicate results across parallel workers
- Progress bar not stopping on error

---

## [1.0.0] — 2025-03-07

### Initial release
- DuckDuckGo dorking engine with 14 news categories
- Parallel search with 4 workers
- Exponential backoff retry on network errors
- Dark-theme tkinter GUI
- CLI mode (`--cli` flag)
- HTML report export (dark theme)
- CSV and JSON export
- Windows desktop notifications via `plyer`
- Date filter, proxy support, keyword filter
- Multiple targets in a single search run
