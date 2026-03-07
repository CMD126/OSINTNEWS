"""
Dork query builder - defines all Google-style dork templates
and builds queries from a user-supplied target string.
"""

DORK_CATEGORIES = {
    "1": {
        "name": "Recent News",
        "description": "Major news outlets (Reuters, BBC, AP, CNN, Guardian)",
        "template": '"{target}" (site:reuters.com OR site:bbc.com OR site:apnews.com OR site:cnn.com OR site:theguardian.com OR site:nbcnews.com)',
    },
    "2": {
        "name": "All News",
        "description": "Any page with 'news' in the URL",
        "template": '"{target}" inurl:news',
    },
    "3": {
        "name": "Press Releases",
        "description": "Official statements and press releases",
        "template": '"{target}" ("press release" OR "official statement" OR "announces" OR "announces that")',
    },
    "4": {
        "name": "Investigations & Controversies",
        "description": "Scandals, lawsuits, arrests, indictments",
        "template": '"{target}" (investigation OR scandal OR lawsuit OR arrested OR charged OR indicted OR fraud OR corruption)',
    },
    "5": {
        "name": "Financial News",
        "description": "Business and financial coverage",
        "template": '"{target}" (site:bloomberg.com OR site:ft.com OR site:wsj.com OR site:forbes.com OR site:businessinsider.com OR site:marketwatch.com)',
    },
    "6": {
        "name": "Government & Legal",
        "description": "Government websites and legal records",
        "template": '"{target}" (site:.gov OR site:.gov.uk OR site:.gc.ca OR site:.europa.eu)',
    },
    "7": {
        "name": "PDF Documents",
        "description": "Official or leaked PDF documents",
        "template": '"{target}" filetype:pdf',
    },
    "8": {
        "name": "Social Media",
        "description": "Twitter/X, LinkedIn, Reddit mentions",
        "template": '"{target}" (site:twitter.com OR site:x.com OR site:linkedin.com OR site:reddit.com)',
    },
    "9": {
        "name": "Tech & Cyber News",
        "description": "Technology and cybersecurity coverage",
        "template": '"{target}" (site:techcrunch.com OR site:wired.com OR site:arstechnica.com OR site:theverge.com OR site:bleepingcomputer.com)',
    },
    "10": {
        "name": "Cached & Archive",
        "description": "Cached pages and web archives",
        "template": '"{target}" (site:web.archive.org OR cache:"{target}")',
    },
}


def build_dorks(target: str, selected: list) -> list:
    """Build a list of dork dicts from the selected category keys."""
    dorks = []
    for key in selected:
        cat = DORK_CATEGORIES.get(key)
        if cat:
            dorks.append({
                "category": cat["name"],
                "query": cat["template"].replace("{target}", target),
            })
    return dorks
