"""
Dork query builder - all Google-style dork templates.
Supports custom date ranges via the after: operator.
"""

DORK_CATEGORIES = {
    "1": {
        "name": "Recent News (EN)",
        "description": "Major English news outlets",
        "template": '"{target}" (site:reuters.com OR site:bbc.com OR site:apnews.com OR site:cnn.com OR site:theguardian.com OR site:nbcnews.com OR site:abcnews.go.com)',
    },
    "2": {
        "name": "All News (URL)",
        "description": "Any page with 'news' in the URL",
        "template": '"{target}" inurl:news',
    },
    "3": {
        "name": "Press Releases",
        "description": "Official statements and announcements",
        "template": '"{target}" ("press release" OR "official statement" OR "announces" OR "announcement")',
    },
    "4": {
        "name": "Investigations & Legal",
        "description": "Scandals, lawsuits, arrests, fraud",
        "template": '"{target}" (investigation OR scandal OR lawsuit OR arrested OR charged OR indicted OR fraud OR corruption OR convicted)',
    },
    "5": {
        "name": "Financial News",
        "description": "Business and financial coverage",
        "template": '"{target}" (site:bloomberg.com OR site:ft.com OR site:wsj.com OR site:forbes.com OR site:businessinsider.com OR site:marketwatch.com OR site:cnbc.com)',
    },
    "6": {
        "name": "Government & Legal Docs",
        "description": "Government websites and legal records",
        "template": '"{target}" (site:.gov OR site:.gov.uk OR site:.gc.ca OR site:.europa.eu OR site:.gov.au)',
    },
    "7": {
        "name": "PDF Documents",
        "description": "Official or leaked PDF documents",
        "template": '"{target}" filetype:pdf',
    },
    "8": {
        "name": "Social Media",
        "description": "Twitter/X, LinkedIn, Reddit, Facebook",
        "template": '"{target}" (site:twitter.com OR site:x.com OR site:linkedin.com OR site:reddit.com OR site:facebook.com)',
    },
    "9": {
        "name": "Tech & Cyber News",
        "description": "Technology and cybersecurity coverage",
        "template": '"{target}" (site:techcrunch.com OR site:wired.com OR site:arstechnica.com OR site:theverge.com OR site:bleepingcomputer.com OR site:krebsonsecurity.com)',
    },
    "10": {
        "name": "Web Archive",
        "description": "Wayback Machine and cached pages",
        "template": '"{target}" site:web.archive.org',
    },
    "11": {
        "name": "Noticias PT / BR",
        "description": "Notícias em Português (Portugal e Brasil)",
        "template": '"{target}" (site:publico.pt OR site:dn.pt OR site:observador.pt OR site:cm.pt OR site:g1.globo.com OR site:uol.com.br OR site:folha.uol.com.br OR site:estadao.com.br)',
    },
    "12": {
        "name": "Noticias ES",
        "description": "Noticias en Español",
        "template": '"{target}" (site:elpais.com OR site:elmundo.es OR site:abc.es OR site:lavanguardia.com OR site:infobae.com OR site:clarin.com)',
    },
    "13": {
        "name": "Forums & Discussions",
        "description": "Forums, Quora, Stack Exchange, Hackernews",
        "template": '"{target}" (site:quora.com OR site:news.ycombinator.com OR site:stackexchange.com OR site:medium.com)',
    },
    "14": {
        "name": "Leaked & Paste Sites",
        "description": "Pastebins, leaks, breach sites",
        "template": '"{target}" (site:pastebin.com OR site:ghostbin.com OR site:paste.ee OR "leaked" OR "breach" OR "dump")',
    },
}


def build_dorks(target: str, selected: list) -> list:
    """Build dork dicts for the selected category keys and target string."""
    return [
        {
            "category": DORK_CATEGORIES[key]["name"],
            "query": DORK_CATEGORIES[key]["template"].replace("{target}", target),
            "target": target,
        }
        for key in selected
        if key in DORK_CATEGORIES
    ]
