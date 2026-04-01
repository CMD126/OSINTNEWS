# OSINTNEWS Plus

> **Two tools in one** — News Intelligence GUI + OSINT Identity CLI

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]()

---

## What is it?

OSINTNEWS Plus is a free, open-source OSINT toolkit built in Python. It uses **Google Dorking via DuckDuckGo** and an optional **RAG AI engine** (Claude / OpenAI / Gemini / Ollama) to help you gather and analyse open-source intelligence quickly.

It ships as two focused tools that share the same codebase:

| Tool | How to launch | Purpose |
|------|--------------|---------|
| 🖥️ **GUI — News Intelligence** | `python osintnews.py` | Search news, press releases, government docs, financial coverage, leaks and more for any target. Generates AI-powered executive reports. |
| 🔍 **CLI — OSINT Identity Search** | `python osintnews.py --cli` | Search for usernames, email addresses, phone numbers and people across social media, forums, breach sites and directories. |

---

## ✨ Features

### Both tools
- **Auto-installer** — no pip needed, just run the script and it installs everything automatically
- **Parallel search** — 4 workers run simultaneously (4× faster), with adaptive rate-limit back-off
- **AI analysis** — streaming intelligence reports via Claude, OpenAI, Gemini, or local Ollama
- **Anti-hallucination RAG** — AI only uses retrieved sources, every claim cites `[Source N]`
- **Risk Assessment** — automated LOW / MEDIUM / HIGH / CRITICAL badge with colour coding

### GUI (News Intelligence)
- Dark-theme desktop interface — no browser needed
- 18 dork categories: English/PT/BR/ES news, investigations, financial, government docs, PDFs, leaks, social media, tech/cyber, GitHub, academic, video, Telegram
- Real-time results as each query completes — click any URL to open it
- **Determinate progress bar** — shows X/Y% as queries complete
- CJK filter — removes Chinese/Japanese/Korean results automatically
- Export: HTML (dark theme) · CSV · JSON · Excel · Markdown
- Search history with re-run and report access
- Persistent settings (API keys, delay, output folder)
- Windows desktop notifications on completion

### CLI (OSINT Identity Search)
- 4 search modes: **username · email · phone · person**
- Interactive prompts — run with no arguments and it guides you
- 32 purpose-built dork templates across all modes (see table below)
- Saves results as JSON, CSV, or plain text
- Optional AI analysis on any result set

---

## 🚀 Quick Start

No manual setup required — just run:

```bash
python osintnews.py
```

On first launch, a progress window appears and installs all required packages automatically. The main app opens when it's done.

> **Tip:** If you already have `duckduckgo-search` installed, the auto-installer will swap it to the new `ddgs` package automatically.

---

## 📦 Manual Install (optional)

```bash
pip install -r requirements.txt
```

For AI features, install your provider:

```bash
pip install anthropic          # Claude (recommended)
pip install openai             # OpenAI GPT
pip install google-generativeai  # Google Gemini
# Ollama: install from https://ollama.com — free, fully offline
```

---

## 🖥️ GUI — News Intelligence

```bash
python osintnews.py
```

### Tabs

| Tab | Description |
|-----|-------------|
| **Search** | Enter targets (one per line), pick dork categories, set date filter / max results / delay / proxy / keyword filter |
| **Results** | Live results grouped by category — click URLs to open, export to HTML/CSV/JSON/Excel/Markdown |
| **AI Analysis** | Streaming intelligence report with risk badge and cited sources |
| **History** | Past searches — re-run, open report, or delete |
| **Settings** | Output folder, AI provider, API key, model, max tokens, notifications |

### Dork Categories

| # | Name | Sources |
|---|------|---------|
| 1 | Recent News (EN) | Reuters, BBC, AP, CNN, Guardian, NBC |
| 2 | All News (URL) | `inurl:news` |
| 3 | Press Releases | "press release", "official statement" |
| 4 | Investigations & Legal | scandal, lawsuit, arrested, fraud, corruption |
| 5 | Financial News | Bloomberg, FT, WSJ, Forbes, CNBC |
| 6 | Government & Legal Docs | `.gov`, `.gov.uk`, `.europa.eu` |
| 7 | PDF Documents | `filetype:pdf` |
| 8 | Social Media | Twitter/X, LinkedIn, Reddit, Facebook |
| 9 | Tech & Cyber News | TechCrunch, Wired, Ars Technica, BleepingComputer |
| 10 | Web Archive | Wayback Machine |
| 11 | Notícias PT / BR | Público, DN, G1, Folha, Estadão |
| 12 | Noticias ES | El País, El Mundo, La Vanguardia, Infobae |
| 13 | Forums & Discussions | Reddit, Quora, Hacker News, Medium |
| 14 | Leaks & Paste Sites | Pastebin, breach keywords, dump |
| 15 | GitHub & Code | GitHub, GitLab, Gist, Bitbucket |
| 16 | Academic & Research | arXiv, ResearchGate, SSRN, Google Scholar |
| 17 | Video & Media | YouTube, Vimeo, Rumble, Spotify |
| 18 | Telegram & Discord | Public Telegram channels, Discord servers |

---

## 🔍 CLI — OSINT Identity Search

```bash
# Interactive (guided prompts):
python osintnews.py --cli

# Username hunt:
python osintnews.py --cli --mode username --target johndoe

# Email investigation:
python osintnews.py --cli --mode email --target john@example.com

# Phone lookup:
python osintnews.py --cli --mode phone --target "+1 555 123 4567"

# Person / name search:
python osintnews.py --cli --mode person --target "John Doe"

# With AI analysis:
python osintnews.py --cli --mode username --target h4ck3r --ai --provider claude
python osintnews.py --cli --mode person   --target "Elon Musk" --ai --provider gemini
```

### Search Sources by Mode

**Username** (U1–U12)

| ID | Source |
|----|--------|
| U1 | Twitter / X |
| U2 | Instagram |
| U3 | TikTok |
| U4 | Reddit |
| U5 | GitHub / GitLab |
| U6 | LinkedIn |
| U7 | YouTube |
| U8 | Discord / Telegram |
| U9 | Steam, Twitch, PSN, Xbox |
| U10 | Forums (HN, Medium, Quora, StackOverflow) |
| U11 | Paste & Leak Sites |
| U12 | Web Archive |

**Email** (E1–E7) — social media · professional · code repos · breach/paste · forums · domain intel · PDFs

**Phone** (P1–P5) — social media · people directories · classifieds · leak sites · business pages

**Person** (N1–N8) — social media · news · court/legal records · company records · academic · forums · PDFs · leaks

### CLI Options

```
--mode        Search mode: username / email / phone / person
--target, -t  Search target
--categories  Category codes (e.g. U1,U3 or A for all)
--max-results Max results per category (default: 10)
--delay       Seconds between queries (default: 1.0)
--workers     Parallel workers (default: 4)
--format      Output format: json / csv / txt (default: json)
--output, -o  Output directory (default: reports/)
--no-save     Do not save results to file
--ai          Run AI analysis on results
--provider    AI provider: claude / openai / gemini / ollama (default: claude)
--api-key     API key (or use env var)
--model       Model override (blank = provider default)
--max-tokens  Max AI output tokens (default: 4000)
--ollama-url  Ollama base URL (default: http://localhost:11434)
--ollama-model Ollama model name (default: llama3.2)
```

---

## 🤖 AI / RAG Engine

Both tools share the same AI pipeline:

```
Search Results → Retriever (filter + deduplicate) → LLM Context → AI Report
```

| Provider | Env Var | Default Model | Notes |
|----------|---------|---------------|-------|
| **Claude** *(recommended)* | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` | Best structured output, streaming |
| **OpenAI** | `OPENAI_API_KEY` | `gpt-4o` | Streaming supported |
| **Gemini** | `GOOGLE_API_KEY` | `gemini-1.5-flash` | Fast and cost-effective |
| **Ollama** | *(none)* | `llama3.2` | Free, fully offline, streaming supported |

**Prompt engineering principles:**
- Anti-hallucination: LLM only uses retrieved sources, never its training data
- Every fact must cite `[Source N]`
- Distinguishes FACT / INFERENCE / ALLEGATION
- Precise risk scale: LOW / MEDIUM / HIGH / CRITICAL
- Declares "Intelligence Gaps" when data is insufficient

---

## 📁 Project Structure

```
OSINTNEWS/
├── osintnews.py            ← Launcher (GUI default, --cli for OSINT identity search)
├── osintnews_cli.py        ← CLI: OSINT identity search (username/email/phone/person)
├── requirements.txt
├── modules/
│   ├── installer.py        ← Auto-installs dependencies on first run
│   ├── dorker.py           ← 18 news dork templates (GUI)
│   ├── dorker_osint.py     ← 32 OSINT identity dork templates (CLI)
│   ├── searcher.py         ← DuckDuckGo engine (parallel, retry, rate-limit aware)
│   ├── reporter.py         ← HTML / CSV / JSON / Excel / Markdown export
│   ├── history.py          ← Persistent search history
│   ├── notifier.py         ← Windows desktop notifications
│   ├── gui/
│   │   └── app.py          ← Full tkinter GUI (dark theme, streaming AI, clickable URLs)
│   └── rag/
│       ├── models.py       ← Immutable data models (frozen dataclasses)
│       ├── retriever.py    ← Pure functions + functional pipeline
│       ├── prompts.py      ← Advanced prompt engineering
│       ├── generator.py    ← Claude / OpenAI / Gemini / Ollama (all streaming)
│       └── pipeline.py     ← RAG pipeline composition
├── reports/                ← Generated reports and OSINT exports
└── data/
    ├── history.json        ← Search history
    └── settings.json       ← User settings
```

---

## 📤 Output Formats

| Format | GUI | CLI | Description |
|--------|-----|-----|-------------|
| HTML | ✅ | — | Dark-themed report with AI section, clickable links |
| CSV | ✅ | ✅ | Spreadsheet-ready |
| JSON | ✅ | ✅ | Machine-readable, full data |
| Excel | ✅ | — | Formatted `.xlsx` with column widths |
| Markdown | ✅ | — | For Obsidian, Notion, GitHub |
| TXT | — | ✅ | Plain text, human-readable |

---

## ⚠️ Legal & Ethical Use

This tool queries **publicly available information** using standard search engine queries. It does not scrape private data, bypass authentication, or access non-public systems.

- Use only on targets you have authorisation to research
- Respect local laws regarding privacy and data collection
- Do not use for harassment, stalking, or illegal surveillance

---

## 📄 License

MIT — use freely, contributions welcome.

---

## 🙏 Credits

Built with [DuckDuckGo Search (`ddgs`)](https://github.com/deedy5/ddgs) · [Anthropic Claude](https://anthropic.com) · [tkinter](https://docs.python.org/3/library/tkinter.html)
