"""
Result verifier — Phase 2 of the two-stage ("Maltego-lite") pipeline.

Phase 1  (modules/searcher.py) : DuckDuckGo dorks -> candidate URLs (low trust)
Phase 2  (this module)         : for each candidate, do a live HTTP check and
                                 attach a confidence verdict + evidence

What a verdict means
--------------------
  VERIFIED        A definitive existence signal — a platform API confirmed the
                  exact handle, or a raw paste literally contains the target.
  LIKELY          The target string is present in the fetched page, but this is
                  not proof of identity (generic mention, adjacent handle, …).
  FALSE_POSITIVE  The page loaded fine but the target is absent / API says 404.
  UNVERIFIABLE    Not checkable without an authenticated session (login-walled
                  sites), non-HTTP URL, or the per-run check budget ran out.
  ERROR           Network failure / timeout / DNS.

Design choices
--------------
* Login-walled platforms (Twitter/X, Instagram, TikTok, Facebook, LinkedIn,
  Threads) are **not** requested at all. An unauthenticated GET returns a JS
  shell whose <title> still contains the handle — matching that would produce
  false VERIFIED hits, and hammering them burns the caller's IP reputation.
* No BeautifulSoup: JSON where an API exists, cheap regex tag-strip otherwise.
* Polite by construction: >= `min_interval` seconds between hits to the *same*
  host, a hard `max_checks` budget, small worker pool, `stop_event` support.

Cross-correlation
-----------------
While verifying, emails / @handles / phone numbers found in the fetched page
text are stashed in ``evidence.extracted``. ``correlate()`` then links any
identifier that appears on >= 2 distinct sources, and
``build_email_recheck_targets()`` produces a chained pass — extracted emails
re-checked against the paste/leak URLs already in the run (no new searches).
"""

from __future__ import annotations

import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

try:
    import requests
    _HAVE_REQUESTS = True
except Exception:                       # pragma: no cover - requests is optional
    _HAVE_REQUESTS = False


# ---------------------------------------------------------------------------
# Confidence vocabulary (ordered strongest -> weakest, for display / sorting)
# ---------------------------------------------------------------------------

VERIFIED       = "VERIFIED"
LIKELY         = "LIKELY"
UNVERIFIABLE   = "UNVERIFIABLE"
FALSE_POSITIVE = "FALSE_POSITIVE"
ERROR          = "ERROR"
CONFIDENCE_ORDER = (VERIFIED, LIKELY, UNVERIFIABLE, FALSE_POSITIVE, ERROR)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# Sites that block unauthenticated reads — never requested.
_LOGIN_WALLED = frozenset({
    "twitter.com", "x.com", "instagram.com", "tiktok.com",
    "facebook.com", "fb.com", "linkedin.com", "lnkd.in", "threads.net",
})

# Surfaces that make a hit materially worse (used by exposure_level()).
_LEAK_HOSTS = frozenset({
    "pastebin.com", "ghostbin.com", "paste.ee", "controlc.com", "rentry.co",
})
_LEAK_WORDS = ("paste", "leak", "breach", "dump", "combo")

# GitHub top-level paths that are not user profiles.
_GH_RESERVED = frozenset({
    "orgs", "sponsors", "about", "features", "topics", "collections", "trending",
    "marketplace", "explore", "settings", "notifications", "search", "login",
    "join", "pricing", "readme", "site", "contact", "security", "team",
    "enterprise", "customer-stories", "apps", "new", "issues", "pulls",
})

_MAX_BYTES = 512_000
_EMAIL_RE  = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_HANDLE_RE = re.compile(r"(?<![\w@/.])@([A-Za-z0-9_]{2,30})\b")
_PHONE_RE  = re.compile(r"(?<![\d/])(\+?\d[\d ()\-.]{6,16}\d)(?!\d)")
_SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_TAG_RE    = re.compile(r"<[^>]+>")
_WS_RE     = re.compile(r"\s+")
_LOGIN_URL_MARKERS = ("/login", "/signin", "/sign-in", "/account/login",
                      "/challenge", "checkpoint", "authwall")

# @handles that are almost always noise, never a person's identifier
_ID_STOP_HANDLES = frozenset({
    "gmail", "hotmail", "outlook", "yahoo", "icloud", "proton", "protonmail",
    "example", "email", "mailto", "username", "user", "admin", "test", "info",
    "contact", "support", "media", "press", "twitter", "instagram", "facebook",
    "github", "reddit", "youtube", "tiktok", "linkedin", "telegram", "discord",
})
_IMG_TLDS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _host(url: str) -> str:
    """Normalised host: lower-case, no port, no www./m./mobile. prefix."""
    try:
        net = urlparse(url).netloc.lower()
    except Exception:
        return ""
    net = net.split("@")[-1].split(":")[0]
    for prefix in ("www.", "m.", "mobile.", "en."):
        if net.startswith(prefix):
            net = net[len(prefix):]
    return net


def _is_login_walled(host: str) -> bool:
    """True for a login-walled domain or any of its subdomains (es.linkedin.com…)."""
    return any(host == d or host.endswith("." + d) for d in _LOGIN_WALLED)


def _sleep(seconds: float, stop_event: "threading.Event | None") -> None:
    end = time.monotonic() + seconds
    while True:
        left = end - time.monotonic()
        if left <= 0 or (stop_event is not None and stop_event.is_set()):
            return
        time.sleep(min(0.2, left))


def _visible_text(html: str) -> str:
    html = _SCRIPT_RE.sub(" ", html)
    html = _TAG_RE.sub(" ", html)
    return _WS_RE.sub(" ", html)


def _context(haystack: str, needle: str, window: int) -> "str | None":
    if not needle:
        return None
    i = haystack.lower().find(needle.lower())
    if i < 0:
        return None
    a = max(0, i - window)
    b = min(len(haystack), i + len(needle) + window)
    snippet = _WS_RE.sub(" ", haystack[a:b]).strip()
    return ("… " if a > 0 else "") + snippet + (" …" if b < len(haystack) else "")


def _extract_identifiers(text: str, self_target: str = "") -> dict:
    """
    Pull emails / @handles / phone-like numbers out of fetched page text so the
    cross-correlation pass can link them across platforms. Best-effort and
    conservative — noise is filtered later by the "appears on >= 2 sources" rule.
    """
    st = self_target.lower().lstrip("@").strip()

    emails = sorted({m.group(0).lower() for m in _EMAIL_RE.finditer(text)})
    emails = [e for e in emails if not e.endswith(_IMG_TLDS)][:20]

    handles = sorted({m.group(1).lower() for m in _HANDLE_RE.finditer(text)})
    handles = [h for h in handles if h != st and h not in _ID_STOP_HANDLES][:20]

    phones, seen = [], set()
    for m in _PHONE_RE.finditer(text):
        raw = m.group(1).strip()
        digits = re.sub(r"\D", "", raw)
        if 8 <= len(digits) <= 15 and len(set(digits)) > 2 and digits not in seen:
            seen.add(digits)
            phones.append(raw)
    phones = phones[:10]

    out: dict = {}
    if emails:
        out["emails"] = emails
    if handles:
        out["handles"] = handles
    if phones:
        out["phones"] = phones
    return out


def _verdict(confidence: str, *, method: str, checked_url: str = "",
             context: "str | None" = None, matched_on: str = "",
             reason: str = "", extracted: "dict | None" = None) -> dict:
    ev: dict = {"method": method}
    if checked_url:
        ev["checked_url"] = checked_url
    if context:
        ev["context"] = context
    if matched_on:
        ev["matched_on"] = matched_on
    if reason:
        ev["reason"] = reason
    if extracted:
        ev["extracted"] = extracted
    return {"confidence": confidence, "evidence": ev}


# ---------------------------------------------------------------------------
# Per-host throttle
# ---------------------------------------------------------------------------

class _Throttle:
    """Guarantees >= `min_interval` seconds between requests to the same host."""

    def __init__(self, min_interval: float):
        self._min = max(0.0, float(min_interval))
        self._next: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str, stop_event=None) -> None:
        if self._min <= 0 or not host:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next.get(host, 0.0))
            self._next[host] = start + self._min
        delay = start - time.monotonic()
        if delay > 0:
            _sleep(delay, stop_event)


# ---------------------------------------------------------------------------
# HTTP session (one per worker thread)
# ---------------------------------------------------------------------------

_local = threading.local()


def _session():
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": _UA, "Accept-Language": "en,pt;q=0.8"})
        _local.session = s
    return s


# ---------------------------------------------------------------------------
# Platform-specific checks (username mode)
# ---------------------------------------------------------------------------

def _check_github_user(handle: str, target: str, *, timeout) -> "dict | None":
    r = _session().get(f"https://api.github.com/users/{handle}", timeout=timeout)
    if r.status_code == 404:
        return _verdict(FALSE_POSITIVE, method="api",
                        checked_url=f"https://github.com/{handle}",
                        reason="GitHub API: user does not exist")
    if r.status_code != 200:
        return None  # rate-limited / transient -> fall through to generic
    try:
        d = r.json()
    except ValueError:
        return None
    login = str(d.get("login") or handle)
    name  = str(d.get("name") or "")
    ctx = f"GitHub @{login}" + (f" — {name}" if name else "")
    exact = login.lower() == target.lower() or target.lower() in name.lower()
    extracted = {"emails": [str(d["email"]).lower()]} if d.get("email") else None
    return _verdict(VERIFIED if exact else LIKELY, method="api",
                    checked_url=f"https://github.com/{login}", context=ctx,
                    matched_on="github api" if exact else "github api (adjacent handle)",
                    extracted=extracted)


def _check_gitlab_user(handle: str, target: str, *, timeout) -> "dict | None":
    r = _session().get("https://gitlab.com/api/v4/users",
                       params={"username": handle}, timeout=timeout)
    if r.status_code != 200:
        return None
    try:
        arr = r.json() if r.content else []
    except ValueError:
        return None
    if not arr:
        return _verdict(FALSE_POSITIVE, method="api",
                        checked_url=f"https://gitlab.com/{handle}",
                        reason="GitLab API: username not found")
    u = arr[0]
    uname = str(u.get("username") or handle)
    ctx = f"GitLab @{uname}" + (f" — {u.get('name')}" if u.get("name") else "")
    exact = uname.lower() == target.lower()
    return _verdict(VERIFIED if exact else LIKELY, method="api",
                    checked_url=f"https://gitlab.com/{uname}", context=ctx,
                    matched_on="gitlab api")


def _check_reddit_user(handle: str, target: str, *, timeout) -> "dict | None":
    r = _session().get(f"https://www.reddit.com/user/{handle}/about.json",
                       timeout=timeout)
    if r.status_code in (403, 404):
        return _verdict(FALSE_POSITIVE, method="api",
                        checked_url=f"https://www.reddit.com/user/{handle}",
                        reason=f"Reddit API: HTTP {r.status_code} (no such user)")
    if r.status_code != 200:
        return None
    try:
        d = r.json().get("data", {})
    except ValueError:
        return None
    name = str(d.get("name") or handle)
    karma = int(d.get("comment_karma", 0)) + int(d.get("link_karma", 0))
    ctx = f"Reddit u/{name} — {karma} karma"
    if d.get("is_suspended"):
        ctx += " (suspended)"
    exact = name.lower() == target.lower()
    return _verdict(VERIFIED if exact else LIKELY, method="api",
                    checked_url=f"https://www.reddit.com/user/{name}", context=ctx,
                    matched_on="reddit api")


def _dispatch_username(host: str, url: str, target: str, *, timeout) -> "dict | None":
    segs = [s for s in urlparse(url).path.split("/") if s]

    if host == "github.com":
        if len(segs) == 1 and segs[0].lower() not in _GH_RESERVED:
            return _check_github_user(segs[0], target, timeout=timeout)
        return None
    if host == "gitlab.com":
        if len(segs) == 1 and segs[0] not in ("users", "explore", "help", "-", "dashboard"):
            return _check_gitlab_user(segs[0], target, timeout=timeout)
        return None
    if host == "reddit.com":
        if len(segs) >= 2 and segs[0] in ("user", "u"):
            return _check_reddit_user(segs[1], target, timeout=timeout)
        return None
    return None


def _check_pastebin(url: str, target: str, *, timeout, window) -> "dict | None":
    segs = [s for s in urlparse(url).path.split("/") if s]
    if not segs or segs[0] in ("u", "user"):
        return None  # user page -> generic
    pid = segs[1] if segs[0] == "raw" and len(segs) > 1 else segs[-1]
    if not pid or "." in pid:
        return None
    r = _session().get(f"https://pastebin.com/raw/{pid}", timeout=timeout)
    checked = f"https://pastebin.com/raw/{pid}"
    if r.status_code != 200:
        return _verdict(FALSE_POSITIVE, method="html", checked_url=checked,
                        reason=f"paste not public (HTTP {r.status_code})")
    body = r.text[:_MAX_BYTES]
    if target and target.lower() in body.lower():
        return _verdict(VERIFIED, method="html", checked_url=checked,
                        context=_context(body, target, window),
                        matched_on="pastebin raw content",
                        extracted=_extract_identifiers(body, target))
    return _verdict(FALSE_POSITIVE, method="html", checked_url=checked,
                    reason="target string not present in paste body")


def _check_generic(url: str, target: str, *, timeout, window) -> dict:
    r = _session().get(url, timeout=timeout)
    final_host = _host(r.url)
    low_url = r.url.lower()
    if _is_login_walled(final_host) or any(m in low_url for m in _LOGIN_URL_MARKERS):
        return _verdict(UNVERIFIABLE, method="html", checked_url=url,
                        reason=f"redirected to a login page ({final_host or 'unknown'})")
    if r.status_code >= 400:
        return _verdict(FALSE_POSITIVE, method="html", checked_url=url,
                        reason=f"HTTP {r.status_code}")
    if not target:
        return _verdict(UNVERIFIABLE, method="html", checked_url=url,
                        reason="no target string to match against")
    text = _visible_text(r.text[:_MAX_BYTES])
    if target.lower() in text.lower():
        return _verdict(LIKELY, method="html", checked_url=url,
                        context=_context(text, target, window),
                        matched_on="page text",
                        extracted=_extract_identifiers(text, target))
    return _verdict(FALSE_POSITIVE, method="html", checked_url=url,
                    reason="target string not found in page text")


def _verify_one(result: dict, *, timeout, window, throttle, stop_event) -> dict:
    url  = (result.get("href") or "").strip()
    tgt  = (result.get("target") or "").strip()
    mode = result.get("mode") or "username"

    if not url.lower().startswith(("http://", "https://")):
        return _verdict(UNVERIFIABLE, method="none", checked_url=url,
                        reason="not an HTTP(S) URL")
    host = _host(url)
    if _is_login_walled(host):
        return _verdict(UNVERIFIABLE, method="none", checked_url=url,
                        reason="login wall / JS-only — needs an authenticated session")
    if stop_event is not None and stop_event.is_set():
        return _verdict(UNVERIFIABLE, method="none", checked_url=url, reason="cancelled")

    throttle.wait(host, stop_event)
    try:
        if mode == "username":
            special = _dispatch_username(host, url, tgt, timeout=timeout)
            if special is not None:
                return special
        if host == "pastebin.com":
            pb = _check_pastebin(url, tgt, timeout=timeout, window=window)
            if pb is not None:
                return pb
        return _check_generic(url, tgt, timeout=timeout, window=window)
    except requests.Timeout:
        return _verdict(ERROR, method="html", checked_url=url, reason="timeout")
    except requests.RequestException as exc:
        return _verdict(ERROR, method="html", checked_url=url,
                        reason=f"{type(exc).__name__}: {exc}"[:160])
    except Exception as exc:                       # pragma: no cover - defensive
        return _verdict(ERROR, method="html", checked_url=url,
                        reason=f"{type(exc).__name__}: {exc}"[:160])


# ---------------------------------------------------------------------------
# Verification queue ordering
# ---------------------------------------------------------------------------

def _needs_request(result: dict) -> bool:
    """True when verifying this result will actually make an HTTP request."""
    url = (result.get("href") or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return False
    return not _is_login_walled(_host(url))


def _priority_key(result: dict):
    """
    Sort key for the verification queue (lower = checked sooner). This only
    reorders *when* each result is checked — nothing is skipped, and the
    returned list keeps its original order.

      0  cheap + definitive : profile API (username mode) or a raw paste
      1  target appears in the URL path  → probably the right page
      5  everything else (generic HTML fetch)
      8  login-walled  → returns instantly, never worth a queue slot up front
      9  non-HTTP URL  → instant
    """
    url = (result.get("href") or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return (9, url)
    host = _host(url)
    if _is_login_walled(host):
        return (8, url)

    segs = [s for s in urlparse(url).path.split("/") if s]
    if host == "pastebin.com":
        return (0, url)
    if (result.get("mode") or "username") == "username":
        if host == "github.com" and len(segs) == 1 and segs[0].lower() not in _GH_RESERVED:
            return (0, url)
        if host == "gitlab.com" and len(segs) == 1:
            return (0, url)
        if host == "reddit.com" and len(segs) >= 2 and segs[0] in ("user", "u"):
            return (0, url)

    tgt = (result.get("target") or "").lower().lstrip("@")
    if len(tgt) >= 3 and tgt in url.lower():
        return (1, url)
    return (5, url)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_results(
    results: list,
    *,
    min_interval:   float = 1.0,
    max_workers:    int   = 4,
    max_checks:     int   = 80,
    timeout:        tuple = (4, 8),
    context_window: int   = 120,
    on_status             = None,
    on_progress           = None,
    stop_event            = None,
) -> list:
    """
    Return a NEW list of dicts — each input result plus ``confidence`` and
    ``evidence`` keys. Input dicts are not mutated. Output order matches input.

    min_interval : minimum seconds between hits to the same host
    max_checks   : hard cap on live HTTP requests per run; results that would
                   exceed it become UNVERIFIABLE ("check budget exhausted").
                   Results that make no request (login-walled, non-HTTP) never
                   consume the budget. Checks are ordered by likely relevance
                   (profile APIs and target-in-URL first) so a tight budget is
                   spent on the useful URLs.
    """
    out = [dict(r) for r in results]
    if not out:
        return out

    if not _HAVE_REQUESTS:
        if on_status:
            on_status("verification skipped — the `requests` package is not installed")
        for r in out:
            r.update(_verdict(UNVERIFIABLE, method="none",
                              reason="`requests` package not installed"))
        return out

    throttle = _Throttle(min_interval)
    total = len(out)
    lock = threading.Lock()
    done = [0]

    # Assign the budget up front, walking results in likely-relevance order, so
    # a tight `max_checks` is spent deterministically on the useful URLs.
    # `out` itself keeps the caller's order — only processing is reordered.
    queue = sorted(enumerate(out, 1), key=lambda it: _priority_key(it[1]))
    budget = int(max_checks)
    plan = []
    for idx, r in queue:
        if not _needs_request(r):
            plan.append((idx, r, "instant"))      # login-walled / non-HTTP
        elif budget > 0:
            budget -= 1
            plan.append((idx, r, "check"))
        else:
            plan.append((idx, r, "budget"))

    def work(item):
        idx, r, action = item
        if stop_event is not None and stop_event.is_set():
            v = _verdict(UNVERIFIABLE, method="none",
                         checked_url=r.get("href", ""), reason="cancelled")
        elif action == "budget":
            v = _verdict(UNVERIFIABLE, method="none", checked_url=r.get("href", ""),
                         reason=f"check budget ({max_checks}) exhausted")
        else:
            if action == "check" and on_status:
                label = _host(r.get("href", "")) or r.get("href", "")
                on_status(f"[{idx}/{total}] {label}")
            v = _verify_one(r, timeout=timeout, window=context_window,
                            throttle=throttle, stop_event=stop_event)
        r.update(v)
        with lock:
            done[0] += 1
            if on_progress:
                on_progress(done[0], total)
        return r

    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as ex:
        list(ex.map(work, plan))
    return out


def summarize(results: list) -> dict:
    """Count results by confidence level (missing/unknown levels ignored)."""
    counts = {c: 0 for c in CONFIDENCE_ORDER}
    for r in results:
        c = r.get("confidence")
        if c in counts:
            counts[c] += 1
    return counts


def unverifiable_breakdown(results: list) -> list:
    """
    Explain *why* results ended up UNVERIFIABLE. Returns, most-common first:
        [(label, count, [(host, count), ...]), ...]

    Labels: "login-walled", "check budget exhausted", "non-HTTP URL",
    "cancelled", "requests not installed", "other".
    """
    buckets: dict = {}
    for r in results:
        if r.get("confidence") != UNVERIFIABLE:
            continue
        reason = ((r.get("evidence") or {}).get("reason") or "").lower()
        if ("login wall" in reason or "authenticated session" in reason
                or "login page" in reason):
            label = "login-walled"
        elif "budget" in reason:
            label = "check budget exhausted"
        elif "not an http" in reason:
            label = "non-HTTP URL"
        elif "cancelled" in reason:
            label = "cancelled"
        elif "requests" in reason:
            label = "requests not installed"
        else:
            label = "other"
        b = buckets.setdefault(label, {"count": 0, "hosts": {}})
        b["count"] += 1
        h = _host(r.get("href", ""))
        if h:
            b["hosts"][h] = b["hosts"].get(h, 0) + 1

    out = []
    for label, b in sorted(buckets.items(), key=lambda kv: -kv[1]["count"]):
        top = sorted(b["hosts"].items(), key=lambda kv: (-kv[1], kv[0]))[:6]
        out.append((label, b["count"], top))
    return out


# ---------------------------------------------------------------------------
# Exposure score — deterministic, documented formula
# ---------------------------------------------------------------------------
# Counts only VERIFIED / LIKELY results (i.e. things Phase 2 stood behind).
#
# points =  W_PLATFORM * min(distinct platforms with such a hit, CAP)
#        + (W_LEAK_PRESENCE  if a real paste/leak host has a hit, OR a
#                            leak-labelled category has a *VERIFIED* hit —
#                            a LIKELY hit on a noisy "…leaked OR breach…" dork
#                            does NOT count, it is usually a news/wiki page)
#        + (W_PUBLIC_EMAIL   if an email address appears in any evidence context)
#        + (W_STRONG_IDENTITY if at least one hit is VERIFIED, not just LIKELY)
#
# bucket:  0 -> LOW   |   1..5 -> MEDIUM   |   6..11 -> HIGH   |   >=12 -> CRITICAL

_W_PLATFORM        = 2
_W_PLATFORM_CAP    = 8
_W_LEAK_PRESENCE   = 4
_W_PUBLIC_EMAIL    = 3
_W_STRONG_IDENTITY = 2


def _bucket(points: int) -> str:
    if points <= 0:
        return "LOW"
    if points <= 5:
        return "MEDIUM"
    if points <= 11:
        return "HIGH"
    return "CRITICAL"


def exposure_level(results: list) -> tuple:
    """
    Return (level, points, breakdown_lines).

    Only VERIFIED / LIKELY results count. When no result carries a
    ``confidence`` key (verification was not run) this still works — it simply
    finds nothing and returns ("LOW", 0, [...]).
    """
    platforms: dict = {}
    leak_hit = email_hit = strong = False

    for r in results:
        conf = r.get("confidence")
        if conf not in (VERIFIED, LIKELY):
            continue
        cat = r.get("category") or _host(r.get("href", "")) or "?"
        platforms[cat] = True
        if conf == VERIFIED:
            strong = True

        host = _host(r.get("href", ""))
        cat_l = str(r.get("category", "")).lower()
        if host in _LEAK_HOSTS:
            leak_hit = True                                   # on a real paste host
        elif any(w in cat_l for w in _LEAK_WORDS) and conf == VERIFIED:
            leak_hit = True                                   # leak dork, but confirmed

        ev = r.get("evidence") or {}
        if (ev.get("extracted") or {}).get("emails") or _EMAIL_RE.search(ev.get("context") or ""):
            email_hit = True

    n = min(len(platforms), _W_PLATFORM_CAP)
    points = n * _W_PLATFORM
    breakdown = [f"{n} platform(s) with a hit  (+{n * _W_PLATFORM})"]
    if leak_hit:
        points += _W_LEAK_PRESENCE
        breakdown.append(f"paste/leak-site presence  (+{_W_LEAK_PRESENCE})")
    if email_hit:
        points += _W_PUBLIC_EMAIL
        breakdown.append(f"email address in evidence  (+{_W_PUBLIC_EMAIL})")
    if strong:
        points += _W_STRONG_IDENTITY
        breakdown.append(f">=1 definitively verified account  (+{_W_STRONG_IDENTITY})")
    return _bucket(points), points, breakdown


# ---------------------------------------------------------------------------
# Cross-correlation — link identifiers that surfaced during verification
# ---------------------------------------------------------------------------

def correlate(results: list) -> list:
    """
    Group identifiers found in ``evidence.extracted`` that appear on >= 2
    distinct sources. Returns records:

      {"type": "email"|"handle"|"phone", "value": "...",
       "found_on": [platform, ...], "sources": [url, ...],
       "confidence": "MEDIUM"|"HIGH"}

    A single-source identifier is noise and is dropped; 2 sources -> MEDIUM,
    3+ -> HIGH. Sorted most-connected first.
    """
    buckets: dict = {}
    for r in results:
        ext = (r.get("evidence") or {}).get("extracted") or {}
        platform = r.get("category") or _host(r.get("href", "")) or "?"
        url = r.get("href", "")
        for typ, key in (("email", "emails"), ("handle", "handles"), ("phone", "phones")):
            for val in ext.get(key, []):
                b = buckets.setdefault((typ, val), {"platforms": set(), "urls": set()})
                b["platforms"].add(platform)
                if url:
                    b["urls"].add(url)

    out = []
    for (typ, val), b in buckets.items():
        if len(b["platforms"]) < 2:
            continue
        out.append({
            "type":       typ,
            "value":      val,
            "found_on":   sorted(b["platforms"]),
            "sources":    sorted(b["urls"]),
            "confidence": "HIGH" if len(b["platforms"]) >= 3 else "MEDIUM",
        })
    out.sort(key=lambda c: (-len(c["found_on"]), c["type"], c["value"]))
    return out


def build_email_recheck_targets(results: list) -> list:
    """
    Synthetic result dicts for the chained pass: every email extracted during
    verification paired with every paste/leak-surface URL seen in the run.
    Feed these straight back into verify_results() — no new dork searches.
    """
    emails = sorted({
        e for r in results
        for e in ((r.get("evidence") or {}).get("extracted") or {}).get("emails", [])
    })
    leak_urls = sorted({
        r["href"] for r in results
        if r.get("href") and (
            _host(r["href"]) in _LEAK_HOSTS
            or any(w in str(r.get("category", "")).lower() for w in _LEAK_WORDS)
        )
    })
    return [
        {"href": url, "target": email, "mode": "email",
         "category": f"chain:{email}", "title": url, "body": "", "query": ""}
        for email in emails for url in leak_urls
    ]
