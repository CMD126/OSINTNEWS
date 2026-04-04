# OSINTNEWS Plus

> **Two tools in one** — News Intelligence GUI + OSINT Identity CLI

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]()

---

## What is it?

OSINTNEWS Plus is a free, open-source OSINT toolkit built in Python. It uses **Google Dorking via DuckDuckGo** and an optional **RAG AI engine** (Claude / OpenAI / Gemini / Ollama) to help you gather and analyse open-source intelligence quickly — querying only publicly available, indexed information.

It ships as two focused tools sharing the same codebase:

| Tool | Launch command | Purpose |
|------|---------------|---------|
| 🖥️ **GUI — News Intelligence** | `python osintnews.py` | Search news, press releases, government docs, financial coverage, leaks and more for any target. Generates AI-powered executive reports. |
| 🔍 **CLI — OSINT Identity Search** | `python osintnews.py --cli` | Investigate usernames, email addresses, phone numbers and people across social media, forums, breach sites, directories and classifieds. |

---

## ✨ Features

### Both tools
- **Auto-installer** — no pip needed; run the script and it installs everything automatically
- **Parallel search** — multiple workers run simultaneously with adaptive rate-limit back-off
- **AI analysis** — streaming intelligence reports via Claude, OpenAI, Gemini, or local Ollama
- **Anti-hallucination RAG** — AI only uses retrieved sources; every claim cites `[Source N]`
- **Risk Assessment** — automated LOW / MEDIUM / HIGH / CRITICAL badge with colour coding

### GUI (News Intelligence)
- Dark-theme desktop interface — no browser needed
- 18 dork categories: English/PT/BR/ES news, investigations, financial, government docs, PDFs, leaks, social media, tech/cyber, GitHub, academic, video, Telegram
- Real-time results as each query completes — click any URL to open it
- Determinate progress bar showing X/Y% as queries complete
- CJK filter — removes Chinese/Japanese/Korean results automatically
- Export: HTML (dark theme) · CSV · JSON · Excel · Markdown
- Search history with re-run and report access
- Persistent settings (API keys, delay, output folder)
- Windows desktop notifications on completion

### CLI (OSINT Identity Search)
- 4 search modes: **username · email · phone · person**
- Interactive guided menus — no arguments needed, the tool walks you through everything
- 35 purpose-built dork templates across all modes
- **Consent & legal check** before any sensitive search (email / phone / person)
- **Audit log** — every search is recorded in `data/audit.log` (targets stored as hashes, not plaintext)
- **Username correlation summary** — after a username search, shows which platforms confirmed presence and calculates exposure risk level
- **PT/EU phone categories** — dedicated Portuguese and European directory and classifieds sources
- Export: HTML · JSON · CSV · Markdown · **SpiderFoot-compatible JSON**

---

## 🚀 Quick Start

No manual setup required — just run:

```bash
python osintnews.py
```

On first launch, a progress window appears and installs all required packages automatically. The main app opens when done.

> **Tip:** If you already have `duckduckgo-search` installed, the auto-installer will swap it to the new `ddgs` package automatically.

---

## 📦 Manual Install (optional)

```bash
pip install -r requirements.txt
```

For AI features, install your provider:

```bash
pip install anthropic            # Claude (recommended)
pip install openai               # OpenAI GPT
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

The CLI is a guided, interactive OSINT tool for investigating **your own digital footprint** or any target you have explicit authorisation to research. It queries only publicly indexed data via DuckDuckGo dork queries — no private databases, no scraping behind logins.

### How to run

```bash
# Interactive — guided menus, no arguments needed:
python osintnews.py --cli
```

The tool walks you through four steps:

1. Pick a **search mode** (username / email / phone / person)
2. Enter your **target**
3. Select **which categories** to search (or press Enter for all)
4. View results, then optionally **export**

For email, phone and person modes a **consent check** runs first — see the [Ethical OSINT Principles](#️-ethical-osint-principles) section.

---

### Example session — phone lookup

```
Search Mode
  1. Username / Handle  — social media, forums, gaming
  2. Email Address      — breaches, social, professional
  3. Phone Number       — directories, classifieds, leaks
  4. Full Name          — news, legal, academic, social
  Enter number: 3

  Enter phone to search: +351 912 345 678

⚠  Consent & Legal Check
  You are about to search for personal identifier data:
  Mode:   PHONE
  Target: +351 912 345 678

  Please confirm ONE of the following applies:
  1. This is my own data — personal footprint audit
  2. I have explicit written consent from the subject
  3. This is a journalistic / cybersecurity investigation with lawful basis
  0. Cancel — do not proceed
  Confirm (1/2/3 to proceed, 0 to cancel): 1

Select search categories for [PHONE]
  1. Phone — General Web           — broad open web, both +CC and local format
  2. Phone — PT/EU Directories     — Páginas Brancas, 1414.pt, Amarelas, Listel
  3. Phone — PT/EU Classifieds     — OLX.pt, CustoJusto, StandVirtual, Imovirtual
  4. Phone — Leak / Paste Sites    — Pastebin, breach dumps, combo lists
  5. Phone — Business & Contact    — contact pages, LinkedIn, PT business keywords
  6. Phone — International Dirs    — TrueCaller, WhoCalled, WhoCalledMe
  Selection [all]: 2,3,6

  Searching  [PHONE]  target: +351 912 345 678
  Querying 3 dork(s) across 3 categorie(s)…
  [████████████████████] 100% (3/3)

  Results for: +351 912 345 678  |  Total: 4
  [Phone — PT/EU Directories]
    1. Páginas Brancas — 912345678
       https://www.paginasbrancas.pt/...
  ...

Export Results
  1. HTML        2. JSON        3. CSV        4. Markdown        5. SpiderFoot JSON
  Formats: 2
  ✔ JSON → reports/osint_+351_912_345_678_20260404_120000.json
```

> **Tip — phone number formats:** Always try both `+351912345678` (with country code) and `912345678` (local format). Portuguese directories and classifieds often list numbers without the international prefix. The General Web category (P1) searches both formats automatically.

---

### Example session — username search with correlation

```
  Enter username to search: johndoe

  [████████████████████] 100% (12/12)

  Results for: johndoe  |  Total: 31

  Username Correlation Summary

  Target: johndoe

  ● Presence detected on:
    Twitter / X   (3 results)
      https://x.com/johndoe
    Reddit         (5 results)
      https://reddit.com/u/johndoe
    GitHub / GitLab (2 results)
      https://github.com/johndoe
    LinkedIn       (1 result)

  ○ No results on: Instagram, TikTok, YouTube, Discord / Telegram,
    Gaming Platforms, Forums & Communities, Paste & Leak Sites, Web Archive

  Exposure level: MEDIUM  (4 platforms with results)
```

Exposure levels: `LOW` (0 platforms) → `MEDIUM` (1–3) → `HIGH` (4–6) → `CRITICAL` (7+)

---

### Non-interactive (scripted) mode

```bash
# Username hunt:
python osintnews.py --cli --mode username --target johndoe

# Email investigation:
python osintnews.py --cli --mode email --target john@example.com

# Phone lookup — Portuguese number:
python osintnews.py --cli --mode phone --target "+351 912 345 678"

# Person / name search:
python osintnews.py --cli --mode person --target "John Doe"

# With AI analysis:
python osintnews.py --cli --mode username --target johndoe --ai --provider claude

# Skip consent prompt (use only when consent is already confirmed):
python osintnews.py --cli --mode phone --target "+351 912 345 678" --skip-consent
```

---

### Search Sources by Mode

**Username** (U1–U12)

| ID | Platform / Source |
|----|------------------|
| U1 | Twitter / X |
| U2 | Instagram |
| U3 | TikTok |
| U4 | Reddit |
| U5 | GitHub / GitLab |
| U6 | LinkedIn |
| U7 | YouTube |
| U8 | Discord / Telegram |
| U9 | Steam, Twitch, PSN, Xbox |
| U10 | Forums — HN, Medium, Quora, StackOverflow |
| U11 | Paste & Leak Sites — Pastebin, Ghostbin |
| U12 | Web Archive — Wayback Machine |

**Email** (E1–E7)

| ID | Source |
|----|--------|
| E1 | General Web — open search, excludes social media noise |
| E2 | Professional Sites — LinkedIn, company pages, About/Contact pages |
| E3 | Code / Repos — GitHub, GitLab, Bitbucket commits and configs |
| E4 | Breach / Paste Sites — Pastebin, credential dumps, combo lists |
| E5 | Forums — Reddit, Quora, StackOverflow, Disqus |
| E6 | Domain Intelligence — other accounts sharing the same email domain |
| E7 | Documents / PDFs — official filings, whitepapers, `filetype:pdf` |

> **Note:** Social media platforms (Facebook, Instagram, Twitter) intentionally block personal contact data from search engine indexing. E1 uses a broad open web query instead, which is far more effective for finding real mentions.

**Phone** (P1–P6)

| ID | Source |
|----|--------|
| P1 | General Web — searches both `+CCXXXXXXXXX` and local format simultaneously, excludes social media noise |
| P2 | PT/EU Directories — Páginas Brancas, 1414.pt, Amarelas, Listel, Infobel, 118.pt |
| P3 | PT/EU Classifieds — OLX.pt, CustoJusto, StandVirtual, Imovirtual, Milanuncios |
| P4 | Leak / Paste Sites — Pastebin, breach dumps, combo lists |
| P5 | Business & Contact — contact pages, LinkedIn, Portuguese business keywords |
| P6 | International Directories — TrueCaller, WhoCalled, WhoCalledMe, Who-Called |

> **Note:** Facebook and Instagram do not expose phone numbers to search engines — searching them for a phone number will never return meaningful results. P2, P3 and P6 are the most reliable categories for finding a Portuguese mobile number in public records.

**Person** (N1–N8)

| ID | Source |
|----|--------|
| N1 | Social Media — Twitter, Instagram, Facebook, LinkedIn |
| N2 | News — Reuters, BBC, CNN, AP, Guardian |
| N3 | Legal / Court Records — `.gov`, `.gov.uk`, court and arrest keywords |
| N4 | Company Records — Companies House, OpenCorporates, director/CEO keywords |
| N5 | Academic / Research — Google Scholar, ResearchGate, arXiv, Academia.edu |
| N6 | Forums — Reddit, Quora, Hacker News, Medium |
| N7 | Documents / PDFs — `filetype:pdf` |
| N8 | Paste / Leak Sites — Pastebin, breach dumps |

---

### Understanding the results

| Situation | What it means |
|-----------|--------------|
| **Target appears in result snippet** | High confidence direct match — the string was found in the indexed page |
| **Result is on the right platform but no snippet match** | Medium confidence — page may contain the target but snippet wasn't captured |
| **Results seem completely unrelated** | Low confidence noise — the target has no public footprint on that source |
| **No results at all** | The target does not appear in publicly indexed pages for those categories — often a good sign |
| **Hit on E4 or P4 (breach/paste)** | Serious privacy risk — treat as a data exposure incident |

---

### Audit Log

Every search writes a record to `data/audit.log`. Targets are stored as a short SHA-256 hash — never in plaintext — to keep the log useful for activity tracking without creating a surveillance record:

```
2026-04-04 12:00:00 | mode=phone | target_hash=00839c79aea2116c | categories=P2,P3,P6 | results=4
2026-04-04 12:05:22 | mode=username | target_hash=a3f1b2c9de047812 | categories=U1,U2,U4,U5 | results=18
```

---

### SpiderFoot / theHarvester Integration

Select **option 5** in the export menu to save results as a SpiderFoot-compatible JSON file. Each result is mapped to a SpiderFoot event type:

| OSINTNEWS mode | SpiderFoot event type |
|---------------|----------------------|
| username | `SOCIAL_MEDIA` |
| email | `EMAILADDR_COMPROMISED` |
| phone | `PHONE_NUMBER` |
| person | `HUMAN_NAME` |

To import into SpiderFoot: **Investigations → Import Data → JSON**

To pipe into theHarvester workflows:
```bash
python osintnews.py --cli --mode email --target john@example.com
# Export as SpiderFoot JSON, then:
python theHarvester.py -d example.com -b json -f osint_results_spiderfoot.json
```

---

### CLI Options

```
--mode           Search mode: username / email / phone / person
--target         Search target value
--all-categories Use all categories for the selected mode (non-interactive)
--ai             Run AI analysis on results after search
--provider       AI provider: claude / openai / gemini / ollama (default: claude)
--skip-consent   Skip the consent prompt (use only when consent is already confirmed)
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
- Anti-hallucination: LLM only uses retrieved sources, never training data
- Every fact must cite `[Source N]`
- Distinguishes FACT / INFERENCE / ALLEGATION
- Precise risk scale: LOW / MEDIUM / HIGH / CRITICAL
- Declares "Intelligence Gaps" when data is insufficient

---

## 📁 Project Structure

```
OSINTNEWS/
├── osintnews.py            ← Launcher (GUI default, --cli for OSINT identity search)
├── osintnews_cli.py        ← CLI: interactive OSINT identity search
├── requirements.txt
├── modules/
│   ├── installer.py        ← Auto-installs dependencies on first run
│   ├── dorker.py           ← 18 news dork templates (GUI)
│   ├── dorker_osint.py     ← 35 OSINT identity dork templates (CLI)
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
    ├── osint_history.json  ← CLI search history
    ├── history.json        ← GUI search history
    ├── settings.json       ← User settings
    └── audit.log           ← Search audit trail (targets stored as hashes)
```

---

## 📤 Output Formats

| Format | GUI | CLI | Description |
|--------|:---:|:---:|-------------|
| HTML | ✅ | ✅ | Dark-themed report with AI section and clickable links |
| CSV | ✅ | ✅ | Spreadsheet-ready |
| JSON | ✅ | ✅ | Machine-readable, full data |
| Excel | ✅ | — | Formatted `.xlsx` with column widths |
| Markdown | ✅ | ✅ | For Obsidian, Notion, GitHub |
| SpiderFoot JSON | — | ✅ | Compatible with SpiderFoot and theHarvester pipelines |

---

## 🛡️ Ethical OSINT Principles

OSINTNEWS is designed for **ethical, legal, and privacy-respecting investigations**. It queries only publicly indexed data via standard search engine queries. It does not access private databases, scrape behind logins, or bypass authentication.

### Intended use cases

- **Cybersecurity research** — identifying exposed credentials, attack surface analysis
- **Brand monitoring** — tracking mentions, impersonation, or misuse of a brand identity
- **Journalism** — verifying public figures and organisations using open sources
- **Personal digital footprint audits** — understanding your own public exposure, or with explicit consent from the subject

### What this tool does NOT do

- Access private databases, paid breach dumps, or restricted government records
- Scrape behind logins or authentication walls
- Attempt to de-anonymise individuals without explicit consent
- Assist in harassment, stalking, or surveillance

### Consent check

Before any search involving **email**, **phone**, or **person** mode, the tool displays a consent prompt requiring you to confirm one of:

1. You are researching your **own** data (personal footprint audit)
2. You have **explicit written consent** from the subject
3. This is a **journalistic or cybersecurity investigation** with a lawful basis

If none applies, the search is cancelled and no data is queried.

### Output confidence levels

| Level | Meaning |
|-------|---------|
| **High** | Target string appears literally in the indexed page content |
| **Medium** | Result is on a relevant platform but exact match is unclear from the snippet |
| **Low** | Loosely related result — likely unrelated noise from the search engine |

Always distinguish between **verified data** (the string appears in the page) and **assumptions** (inferred from context).

### Legal compliance

- Respect **GDPR** and local privacy regulations — particularly when researching EU/EEA residents
- Use only on targets you have authorisation to research
- Do not use for harassment, stalking, or illegal surveillance
- If a request involves sensitive personal data of another person, confirm you have a legitimate lawful basis before proceeding

---

## 📄 License

MIT — use freely, contributions welcome.

---

## 🙏 Credits

Built with [DuckDuckGo Search (`ddgs`)](https://github.com/deedy5/ddgs) · [Anthropic Claude](https://anthropic.com) · [tkinter](https://docs.python.org/3/library/tkinter.html)
