"""
OSINT Dork Templates — Identity & Social Media Intelligence
===========================================================
Used by the CLI tool (osintnews_cli.py) for searching:
  - Usernames across social platforms
  - Email addresses (breaches, social accounts, professional)
  - Phone numbers
  - Full person names

Separate from dorker.py which is used by the GUI news tool, but shares the
query mechanics in modules/dork_common.py.
"""

from modules.dork_common import (
    build_queries,
    email_domain,
    local_phone,
    sanitize_target,
)

# ---------------------------------------------------------------------------
# Search modes
# ---------------------------------------------------------------------------

OSINT_MODES = {
    "username": "Username / Handle",
    "email":    "Email Address",
    "phone":    "Phone Number",
    "person":   "Person / Full Name",
}

# ---------------------------------------------------------------------------
# Dork categories per mode
# ---------------------------------------------------------------------------

OSINT_CATEGORIES = {

    # ── USERNAME ────────────────────────────────────────────────────────────

    "U1": {
        "mode":        "username",
        "name":        "Twitter / X",
        "description": "Profile, posts and mentions on X",
        "template":    '"{target}" (site:twitter.com OR site:x.com)',
    },
    "U2": {
        "mode":        "username",
        "name":        "Instagram",
        "description": "Profile and tagged posts",
        "template":    '"{target}" site:instagram.com',
    },
    "U3": {
        "mode":        "username",
        "name":        "TikTok",
        "description": "Profile and videos",
        "template":    '"{target}" site:tiktok.com',
    },
    "U4": {
        "mode":        "username",
        "name":        "Reddit",
        "description": "Posts, comments and profile",
        "template":    '"{target}" site:reddit.com',
    },
    "U5": {
        "mode":        "username",
        "name":        "GitHub / GitLab",
        "description": "Code repositories and activity",
        "template":    '"{target}" (site:github.com OR site:gitlab.com OR site:gist.github.com)',
    },
    "U6": {
        "mode":        "username",
        "name":        "LinkedIn",
        "description": "Professional profile",
        "template":    '"{target}" site:linkedin.com',
    },
    "U7": {
        "mode":        "username",
        "name":        "YouTube",
        "description": "Channel and videos",
        "template":    '"{target}" site:youtube.com',
    },
    "U8": {
        "mode":        "username",
        "name":        "Discord / Telegram",
        "description": "Public Discord servers and Telegram channels",
        "template":    '"{target}" (site:discord.com OR site:discord.gg OR site:t.me OR site:telegram.me)',
    },
    "U9": {
        "mode":        "username",
        "name":        "Gaming Platforms",
        "description": "Steam, Twitch, Xbox, PSN profiles",
        "template":    '"{target}" (site:steamcommunity.com OR site:twitch.tv OR site:psnprofiles.com OR site:xboxgamertag.com)',
    },
    "U10": {
        "mode":        "username",
        "name":        "Forums & Communities",
        "description": "HackerNews, Medium, Quora, StackOverflow",
        "template":    '"{target}" (site:news.ycombinator.com OR site:medium.com OR site:quora.com OR site:stackoverflow.com)',
    },
    "U11": {
        "mode":        "username",
        "name":        "Paste & Leak Sites",
        "description": "Pastebin, Ghostbin — credential leaks",
        "template":    '"{target}" (site:pastebin.com OR site:ghostbin.com OR site:paste.ee OR "leaked" OR "breach" OR "combolist")',
    },
    "U12": {
        "mode":        "username",
        "name":        "Web Archive",
        "description": "Cached / deleted pages mentioning this username",
        "template":    '"{target}" site:web.archive.org',
    },

    # ── EMAIL ───────────────────────────────────────────────────────────────

    "E1": {
        "mode":        "email",
        "name":        "Email — General Web",
        "description": "Broad open web search — forums, personal sites, contact pages, directories",
        "template":    '"{target}" -site:facebook.com -site:instagram.com',
    },
    "E2": {
        "mode":        "email",
        "name":        "Email on Professional Sites",
        "description": "LinkedIn, company pages, About pages",
        "template":    '"{target}" (site:linkedin.com OR "about" OR "contact" OR "team")',
    },
    "E3": {
        "mode":        "email",
        "name":        "Email in Code / Repos",
        "description": "GitHub commits, config files, issue trackers",
        "template":    '"{target}" (site:github.com OR site:gitlab.com OR site:bitbucket.org)',
    },
    "E4": {
        "mode":        "email",
        "name":        "Email in Breach / Paste Sites",
        "description": "Credential dumps, leaked databases",
        "template":    '"{target}" (site:pastebin.com OR site:ghostbin.com OR site:paste.ee OR "breach" OR "dump" OR "leaked" OR "combo")',
    },
    "E5": {
        "mode":        "email",
        "name":        "Email in Forums",
        "description": "Public forum registrations and posts",
        "template":    '"{target}" (site:reddit.com OR site:quora.com OR site:stackoverflow.com OR site:medium.com OR site:disqus.com)',
    },
    "E6": {
        "mode":        "email",
        "name":        "Email Domain Intelligence",
        "description": "Other accounts using the same domain",
        "template":    '"@{domain}" -"{target}" (site:linkedin.com OR site:twitter.com OR site:github.com)',
    },
    "E7": {
        "mode":        "email",
        "name":        "Email in Documents / PDFs",
        "description": "Official documents, whitepapers, filings",
        "template":    '"{target}" filetype:pdf',
    },

    # ── PHONE ───────────────────────────────────────────────────────────────

    "P1": {
        "mode":        "phone",
        "name":        "Phone — General Web",
        "description": "Broad open web search for any public mention of the number",
        "template":    '"{target}" OR "{target_local}" -site:facebook.com -site:instagram.com -site:twitter.com',
    },
    "P2": {
        "mode":        "phone",
        "name":        "Phone — PT/EU Directories",
        "description": "Portuguese & European reverse-lookup and white-pages directories",
        "template":    '"{target}" (site:paginasbrancas.pt OR site:1414.pt OR site:amarelas.pt OR site:listel.pt OR site:infobel.com OR site:numberway.com OR site:118.pt)',
    },
    "P3": {
        "mode":        "phone",
        "name":        "Phone — PT/EU Classifieds",
        "description": "OLX Portugal, CustoJusto and other Iberian classifieds where sellers post numbers",
        "template":    '"{target}" (site:olx.pt OR site:custojusto.pt OR site:standvirtual.com OR site:imovirtual.com OR site:milanuncios.com OR site:olx.com)',
    },
    "P4": {
        "mode":        "phone",
        "name":        "Phone — Leak / Paste Sites",
        "description": "Credential and contact data dumps on paste/breach sites",
        "template":    '"{target}" (site:pastebin.com OR site:paste.ee OR site:ghostbin.com OR "leaked" OR "breach" OR "database dump" OR "combo")',
    },
    "P5": {
        "mode":        "phone",
        "name":        "Phone — Business & Contact Pages",
        "description": "Business registrations, contact pages, personal sites",
        "template":    '"{target}" ("contacto" OR "contact" OR "telefone" OR "telemovel" OR "ligar" OR "call us" OR "empresa" OR site:linkedin.com)',
    },
    "P6": {
        "mode":        "phone",
        "name":        "Phone — International Directories",
        "description": "Global reverse-lookup engines (TrueCaller, Who Called, etc.)",
        "template":    '"{target}" (site:truecaller.com OR site:whocalledme.com OR site:whycall.me OR site:callername.com OR site:who-called.co.uk OR "reverse lookup")',
    },

    # ── PERSON ──────────────────────────────────────────────────────────────

    "N1": {
        "mode":        "person",
        "name":        "Person on Social Media",
        "description": "Twitter, Instagram, Facebook, LinkedIn",
        "template":    '"{target}" (site:twitter.com OR site:x.com OR site:instagram.com OR site:facebook.com OR site:linkedin.com)',
    },
    "N2": {
        "mode":        "person",
        "name":        "Person in News",
        "description": "News articles mentioning this person",
        "template":    '"{target}" (site:reuters.com OR site:bbc.com OR site:theguardian.com OR site:cnn.com OR site:apnews.com OR inurl:news)',
    },
    "N3": {
        "mode":        "person",
        "name":        "Person in Legal / Court Records",
        "description": "Court records, legal filings, government docs",
        "template":    '"{target}" (site:.gov OR site:.gov.uk OR "court" OR "lawsuit" OR "indicted" OR "arrested" OR "charged")',
    },
    "N4": {
        "mode":        "person",
        "name":        "Person in Company Records",
        "description": "Director roles, filings, company associations",
        "template":    '"{target}" (site:companieshouse.gov.uk OR site:opencorporates.com OR "director" OR "CEO" OR "founder" OR "officer")',
    },
    "N5": {
        "mode":        "person",
        "name":        "Person in Academic / Research",
        "description": "Papers, citations, university profiles",
        "template":    '"{target}" (site:scholar.google.com OR site:researchgate.net OR site:academia.edu OR site:arxiv.org)',
    },
    "N6": {
        "mode":        "person",
        "name":        "Person on Forums",
        "description": "Reddit, Quora, Hacker News, Medium posts",
        "template":    '"{target}" (site:reddit.com OR site:quora.com OR site:news.ycombinator.com OR site:medium.com)',
    },
    "N7": {
        "mode":        "person",
        "name":        "Person in Documents / PDFs",
        "description": "Official documents, contracts, public filings",
        "template":    '"{target}" filetype:pdf',
    },
    "N8": {
        "mode":        "person",
        "name":        "Person in Paste / Leak Sites",
        "description": "Credential dumps referencing this name",
        "template":    '"{target}" (site:pastebin.com OR "leaked" OR "breach" OR "dump")',
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Backwards-compatible aliases — the mechanics now live in dork_common.
_sanitize     = sanitize_target
_local_phone  = local_phone
_email_domain = email_domain


def categories_for_mode(mode: str) -> dict:
    """Return only the categories relevant to a given mode."""
    return {k: v for k, v in OSINT_CATEGORIES.items() if v["mode"] == mode}


def build_osint_dorks(target: str, selected_keys: list) -> list:
    """
    Build dork dicts for the selected category keys.
    Placeholders handled by dork_common.build_queries:
      {target}       → sanitised target as-is
      {target_local} → phone number with the country calling code removed
      {domain}       → domain part of an email address (E6)
    """
    return build_queries(target, selected_keys, OSINT_CATEGORIES)
