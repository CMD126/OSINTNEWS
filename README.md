# OSINTNEWS Plus

**OSINT News Intelligence Tool** for Windows, powered by Google Dorking + RAG AI Engine.

Search real news, documents, leaks and social media about any target. Generate AI-powered executive intelligence reports with source citations and risk assessment.

## Features

| Feature | Details |
|---------|---------|
| **14 Dork Categories** | News (EN/PT/BR/ES), Investigations, Financial, Gov Docs, PDFs, Leaks, Social, Tech/Cyber, Archive |
| **Multiple Targets** | Search several targets at once, one per line |
| **Date Filter** | Any time / Past day / Week / Month / Year |
| **Keyword Filter** | Show only results containing a specific term |
| **Proxy Support** | HTTP/HTTPS proxy for anonymization |
| **RAG AI Analysis** | Claude / OpenAI / Ollama, executive report with cited sources and risk level |
| **Export** | HTML (dark theme), CSV, JSON, Excel |
| **Search History** | Persistent history with re-run and report access |
| **Windows Notifications** | Desktop alert when search or AI analysis completes |
| **GUI + CLI** | Full desktop interface or terminal mode |

## Install

```bash
pip install -r requirements.txt
```

For AI features, install your provider of choice:

```bash
pip install anthropic      # Claude (recommended)
pip install openai         # OpenAI GPT
# Ollama: install from https://ollama.com, free and offline
```

## Launch

**Desktop GUI (default):**
```bash
python osintnews.py
```

**Terminal / CLI mode:**
```bash
python osintnews.py --cli
python osintnews_cli.py
```

**CLI with arguments:**
```bash
python osintnews.py --cli -t "Elon Musk" -c A -m 10
python osintnews.py --cli -t "OpenAI" -c 1,4,5
python osintnews.py --cli -t "Boeing,Airbus" -c 4,5 --delay 2
```

## GUI Overview

The GUI has 5 tabs:

### Search
- Enter one or more targets (one per line)
- Select dork categories with checkboxes
- Set date filter, max results, delay, proxy, keyword filter
- Toggle **Auto-run AI Analysis** after search

### Results
- Live results streamed as they arrive, grouped by category
- Export buttons: HTML / CSV / JSON / Excel
- **Generate AI Analysis** button

### AI Analysis
- Displays the AI-generated intelligence report
- Color-coded risk badge: `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`
- Inline source citations `[Source N]`
- Export as full HTML report (news + AI analysis combined)

### History
- All past searches with date, target, result count, AI risk level
- Re-run, open report, or delete entries

### Settings
- Output directory, delay, notifications, auto-open report
- **AI / RAG Engine**: provider (Claude/OpenAI/Ollama), API key, model, Ollama URL

## Dork Categories

| # | Name | Sources / Technique |
|---|------|---------------------|
| 1 | Recent News (EN) | Reuters, BBC, AP, CNN, Guardian, NBC |
| 2 | All News (URL) | `inurl:news` operator |
| 3 | Press Releases | `"press release"`, `"official statement"` |
| 4 | Investigations & Legal | scandal, lawsuit, arrested, fraud, corruption |
| 5 | Financial News | Bloomberg, FT, WSJ, Forbes, CNBC |
| 6 | Government & Legal Docs | `.gov`, `.gov.uk`, `.europa.eu` |
| 7 | PDF Documents | `filetype:pdf`, official or leaked |
| 8 | Social Media | Twitter/X, LinkedIn, Reddit, Facebook |
| 9 | Tech & Cyber News | TechCrunch, Wired, Ars Technica, BleepingComputer |
| 10 | Web Archive | Wayback Machine |
| 11 | Notícias PT / BR | Público, DN, G1, Folha, Estadão, UOL |
| 12 | Noticias ES | El País, El Mundo, La Vanguardia, Infobae |
| 13 | Forums & Discussions | Reddit, Quora, Hacker News, Medium |
| 14 | Leaks & Paste Sites | Pastebin, breach keywords, dump, leaked |

## CLI Options

```
-t, --target        Target(s), comma-separated
-c, --categories    Categories (e.g. 1,2,4 or A for all)
-m, --max-results   Max results per category (default: 10)
-o, --output        Output folder for HTML report (default: reports/)
    --no-report     Skip HTML report
    --delay         Seconds between queries (default: 1.5)
```

## AI / RAG Engine

The AI layer follows a **RAG (Retrieval-Augmented Generation)** architecture:

```
Dork Queries -> DuckDuckGo -> NewsItems (immutable) -> LLM Context -> AI Report
    [Retriever]                                             [Generator]
```

**Prompt engineering principles applied:**
- Anti-hallucination: LLM only uses retrieved sources
- Every fact must cite `[Source N]`
- Distinguishes FACT / INFERENCE / ALLEGATION
- Risk scale with precise definitions: LOW / MEDIUM / HIGH / CRITICAL
- Declares "Intelligence Gaps" when data is insufficient

**Supported providers:**

| Provider | Setup |
|----------|-------|
| **Claude** (recommended) | Set API key in Settings |
| **OpenAI GPT** | Set API key in Settings |
| **Ollama** (free, offline) | Install Ollama + pull a model, set URL |

## Output

- `reports/` folder: HTML reports with dark theme, clickable links, AI section
- Export manually: CSV, JSON, Excel from the Results tab
- History stored in `data/history.json`
- Settings stored in `data/settings.json`

## Project Structure

```
OSINTNEWS/
├── osintnews.py          <- Launcher (GUI default, --cli for terminal)
├── osintnews_cli.py      <- CLI mode
├── requirements.txt
├── modules/
│   ├── dorker.py         <- 14 Google dork templates
│   ├── searcher.py       <- DuckDuckGo engine (proxy, timelimit, callbacks)
│   ├── reporter.py       <- HTML / CSV / JSON / Excel export
│   ├── history.py        <- Persistent search history
│   ├── notifier.py       <- Windows desktop notifications
│   ├── gui/
│   │   └── app.py        <- Full tkinter GUI (dark theme)
│   └── rag/
│       ├── models.py     <- Immutable data models (frozen dataclasses)
│       ├── retriever.py  <- Pure functions + functional pipeline
│       ├── prompts.py    <- Advanced prompt engineering
│       ├── generator.py  <- Claude / OpenAI / Ollama integration
│       └── pipeline.py   <- RAG pipeline composition
├── reports/              <- Generated HTML reports
└── data/
    ├── history.json      <- Search history
    └── settings.json     <- User settings
```
