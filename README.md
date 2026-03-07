# OSINTNEWS

OSINT News Intelligence Tool for Windows.
Search actual news about any target using Google dorking techniques, powered by DuckDuckGo.

## Install

```bash
pip install -r requirements.txt
```

## Usage

**Interactive mode (prompts for target and categories):**
```bash
python osintnews.py
```

**With arguments:**
```bash
python osintnews.py -t "Elon Musk" -c A -m 10
python osintnews.py -t "OpenAI" -c 1,4,5
python osintnews.py -t "Microsoft" -c 5 --no-report
```

## Dork Categories

| # | Name | Description |
|---|------|-------------|
| 1 | Recent News | Reuters, BBC, AP, CNN, Guardian |
| 2 | All News | Any URL containing "news" |
| 3 | Press Releases | Official statements |
| 4 | Investigations | Scandals, lawsuits, arrests |
| 5 | Financial News | Bloomberg, FT, WSJ, Forbes |
| 6 | Government & Legal | .gov domains and legal records |
| 7 | PDF Documents | Official or leaked PDFs |
| 8 | Social Media | Twitter/X, LinkedIn, Reddit |
| 9 | Tech & Cyber News | TechCrunch, Wired, Ars, BleepingComputer |
| 10 | Cached & Archive | Wayback Machine, cached pages |

## CLI Options

```
-t, --target        Target to search (name, company, topic)
-c, --categories    Categories to run (e.g. 1,2,3 or A for all)
-m, --max-results   Max results per category (default: 10)
-o, --output        Output folder for HTML report (default: reports/)
    --no-report     Skip HTML report — print to terminal only
    --delay         Seconds between queries (default: 1.5)
```

## Output

- Colored terminal output grouped by category
- HTML report saved to `reports/` folder with dark theme and clickable links

> For educational and authorized security research use only.
