"""
Phase-2 verifier — classification, per-platform routing, throttle, budget and
the documented exposure formula. All HTTP is stubbed; nothing touches the net.
"""

import time

import pytest
import requests

import modules.verifier as V


# ---------------------------------------------------------------------------
# Fake HTTP layer
# ---------------------------------------------------------------------------

class FakeResp:
    def __init__(self, status=200, text="", url="", json_data=None):
        self.status_code = status
        self.text = text
        self.content = text.encode() if text else b""
        self.url = url
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class FakeSession:
    """Maps a URL (ignoring query params) to a FakeResp or an Exception."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, timeout=None, params=None, allow_redirects=True):
        self.calls.append(url)
        r = self.routes.get(url)
        if r is None:
            r = FakeResp(404, "", url)
        if isinstance(r, Exception):
            raise r
        if not r.url:
            r.url = url
        return r


@pytest.fixture
def fake(monkeypatch):
    holder = {"session": None}

    def install(routes):
        s = FakeSession(routes)
        holder["session"] = s
        monkeypatch.setattr(V, "_session", lambda: s)
        return s

    return install


def _result(href, target="johndoe", mode="username", category="Web"):
    return {"href": href, "target": target, "mode": mode,
            "category": category, "title": "t", "body": "b", "query": "q"}


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url, host", [
    ("https://www.GitHub.com/x", "github.com"),
    ("http://m.twitter.com:80/x", "twitter.com"),
    ("https://user:pw@reddit.com/u/x", "reddit.com"),
    ("not a url", ""),
])
def test_host(url, host):
    assert V._host(url) == host


def test_context_window_and_ellipsis():
    # window=2 chars each side of the match, whitespace collapsed
    assert V._context("aaaa TARGET bbbb", "target", 2) == "… a TARGET b …"
    # whole string fits in the window -> no ellipsis
    assert V._context("hi TARGET yo", "target", 50) == "hi TARGET yo"
    assert V._context("no needle here", "zzz", 5) is None


def test_visible_text_strips_tags_and_scripts():
    html = "<html><script>var x=1</script><p>Hello <b>John</b></p></html>"
    out = V._visible_text(html)
    assert "var x" not in out
    assert "Hello John" in out


# ---------------------------------------------------------------------------
# throttle
# ---------------------------------------------------------------------------

def test_throttle_spaces_same_host():
    t = V._Throttle(0.15)
    start = time.monotonic()
    t.wait("a.com"); t.wait("a.com"); t.wait("a.com")
    assert time.monotonic() - start >= 0.30 - 0.02   # 2 gaps of 0.15


def test_throttle_independent_per_host():
    t = V._Throttle(0.20)
    start = time.monotonic()
    t.wait("a.com"); t.wait("b.com"); t.wait("c.com")
    assert time.monotonic() - start < 0.20           # different hosts don't wait


# ---------------------------------------------------------------------------
# login-walled → UNVERIFIABLE, and NO request is made
# ---------------------------------------------------------------------------

def test_login_walled_not_requested(fake):
    s = fake({})
    out = V.verify_results([_result("https://twitter.com/johndoe")], min_interval=0)
    assert out[0]["confidence"] == V.UNVERIFIABLE
    assert "authenticated session" in out[0]["evidence"]["reason"]
    assert s.calls == []                              # never touched the network


def test_login_walled_covers_regional_subdomains(fake):
    s = fake({})
    out = V.verify_results([
        _result("https://es.linkedin.com/in/johndoe", mode="person"),
        _result("https://de-de.facebook.com/johndoe", mode="person"),
    ], min_interval=0)
    assert all(r["confidence"] == V.UNVERIFIABLE for r in out)
    assert s.calls == []


@pytest.mark.parametrize("host, walled", [
    ("linkedin.com", True), ("es.linkedin.com", True),
    ("notlinkedin.com", False), ("linkedin.com.evil.com", False),
    ("x.com", True), ("github.com", False),
])
def test_is_login_walled(host, walled):
    assert V._is_login_walled(host) is walled


def test_non_http_url_unverifiable(fake):
    fake({})
    out = V.verify_results([_result("ftp://x/y")], min_interval=0)
    assert out[0]["confidence"] == V.UNVERIFIABLE


# ---------------------------------------------------------------------------
# GitHub / Reddit API fast paths
# ---------------------------------------------------------------------------

def test_github_profile_exact_match_verified(fake):
    fake({"https://api.github.com/users/johndoe":
          FakeResp(200, json_data={"login": "johndoe", "name": "John Doe"})})
    out = V.verify_results([_result("https://github.com/johndoe")], min_interval=0)
    assert out[0]["confidence"] == V.VERIFIED
    assert out[0]["evidence"]["method"] == "api"
    assert "johndoe" in out[0]["evidence"]["context"]


def test_github_profile_404_false_positive(fake):
    fake({"https://api.github.com/users/ghost": FakeResp(404)})
    out = V.verify_results([_result("https://github.com/ghost")], min_interval=0)
    assert out[0]["confidence"] == V.FALSE_POSITIVE


def test_github_non_profile_url_falls_back_to_generic(fake):
    # /torvalds/linux is a repo, not a profile → generic HTML check
    s = fake({"https://github.com/torvalds/linux":
              FakeResp(200, text="<p>johndoe was here</p>",
                       url="https://github.com/torvalds/linux")})
    out = V.verify_results([_result("https://github.com/torvalds/linux")], min_interval=0)
    assert "https://api.github.com" not in " ".join(s.calls)
    assert out[0]["confidence"] == V.LIKELY


def test_reddit_user_about_json_verified(fake):
    fake({"https://www.reddit.com/user/johndoe/about.json":
          FakeResp(200, json_data={"data": {"name": "johndoe",
                                             "comment_karma": 10, "link_karma": 5}})})
    out = V.verify_results([_result("https://reddit.com/user/johndoe")], min_interval=0)
    assert out[0]["confidence"] == V.VERIFIED
    assert "15 karma" in out[0]["evidence"]["context"]


# ---------------------------------------------------------------------------
# Pastebin raw
# ---------------------------------------------------------------------------

def test_pastebin_hit_is_verified(fake):
    fake({"https://pastebin.com/raw/abc123":
          FakeResp(200, text="leaked creds for johndoe:hunter2")})
    out = V.verify_results([_result("https://pastebin.com/abc123", category="Paste & Leak Sites")],
                           min_interval=0)
    assert out[0]["confidence"] == V.VERIFIED
    assert out[0]["evidence"]["matched_on"] == "pastebin raw content"


def test_pastebin_miss_is_false_positive(fake):
    fake({"https://pastebin.com/raw/abc123": FakeResp(200, text="nothing relevant")})
    out = V.verify_results([_result("https://pastebin.com/abc123")], min_interval=0)
    assert out[0]["confidence"] == V.FALSE_POSITIVE


# ---------------------------------------------------------------------------
# Generic HTML
# ---------------------------------------------------------------------------

def test_generic_match_is_likely_with_context(fake):
    fake({"https://someforum.example/thread/9":
          FakeResp(200, text="<div>post by johndoe about cats</div>",
                   url="https://someforum.example/thread/9")})
    out = V.verify_results([_result("https://someforum.example/thread/9", mode="person",
                                    target="johndoe")], min_interval=0)
    assert out[0]["confidence"] == V.LIKELY
    assert "johndoe" in out[0]["evidence"]["context"]


def test_generic_no_match_is_false_positive(fake):
    fake({"https://site.example/x":
          FakeResp(200, text="totally unrelated", url="https://site.example/x")})
    out = V.verify_results([_result("https://site.example/x", mode="person")], min_interval=0)
    assert out[0]["confidence"] == V.FALSE_POSITIVE


def test_generic_login_redirect_is_unverifiable(fake):
    fake({"https://site.example/x":
          FakeResp(200, text="Sign in", url="https://site.example/account/login")})
    out = V.verify_results([_result("https://site.example/x")], min_interval=0)
    assert out[0]["confidence"] == V.UNVERIFIABLE


def test_network_error_is_error_verdict(fake):
    fake({"https://slow.example/x": requests.Timeout("too slow")})
    out = V.verify_results([_result("https://slow.example/x", mode="person")], min_interval=0)
    assert out[0]["confidence"] == V.ERROR
    assert out[0]["evidence"]["reason"] == "timeout"


# ---------------------------------------------------------------------------
# orchestration: budget, requests-missing, immutability
# ---------------------------------------------------------------------------

def test_max_checks_budget(fake):
    fake({})  # every unknown URL -> 404 -> FALSE_POSITIVE
    rs = [_result(f"https://h{i}.example/p", mode="person") for i in range(5)]
    out = V.verify_results(rs, min_interval=0, max_checks=2)
    budget_exhausted = [r for r in out
                        if r["evidence"].get("reason", "").startswith("check budget")]
    assert len(budget_exhausted) == 3


# ---------------------------------------------------------------------------
# verification-queue priority (reorders *when*, never skips)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("result, rank", [
    ({"href": "https://pastebin.com/abc", "mode": "username", "target": "johndoe"}, 0),
    ({"href": "https://github.com/johndoe", "mode": "username", "target": "johndoe"}, 0),
    ({"href": "https://gitlab.com/johndoe", "mode": "username", "target": "johndoe"}, 0),
    ({"href": "https://www.reddit.com/user/johndoe", "mode": "username", "target": "johndoe"}, 0),
    ({"href": "https://github.com/johndoe/proj", "mode": "username", "target": "johndoe"}, 1),  # repo, target in path
    ({"href": "https://blog.example/johndoe-bio", "mode": "person", "target": "johndoe"}, 1),
    ({"href": "https://blog.example/some-post", "mode": "person", "target": "johndoe"}, 5),
    ({"href": "https://blog.example/linux", "mode": "username", "target": "ab"}, 5),  # 2-char target ignored
    ({"href": "https://es.linkedin.com/in/johndoe", "mode": "username", "target": "johndoe"}, 8),
    ({"href": "ftp://x/y", "mode": "username", "target": "johndoe"}, 9),
])
def test_priority_key_ranks(result, rank):
    assert V._priority_key(result)[0] == rank


@pytest.mark.parametrize("url, needs", [
    ("https://example.com/x", True),
    ("http://example.com/x", True),
    ("https://uk.linkedin.com/in/x", False),
    ("https://x.com/foo", False),
    ("ftp://example.com/x", False),
    ("not a url", False),
])
def test_needs_request(url, needs):
    assert V._needs_request({"href": url}) is needs


def test_login_walled_does_not_consume_budget(fake):
    fake({"https://blog.example/x":
          FakeResp(200, text="johndoe here", url="https://blog.example/x")})
    rs = [
        _result("https://twitter.com/johndoe", mode="person", target="johndoe"),
        _result("https://instagram.com/johndoe", mode="person", target="johndoe"),
        _result("https://blog.example/x", mode="person", target="johndoe"),
    ]
    out = V.verify_results(rs, min_interval=0, max_checks=1)   # budget of exactly 1
    by_url = {r["href"]: r for r in out}
    assert by_url["https://twitter.com/johndoe"]["confidence"] == V.UNVERIFIABLE
    assert by_url["https://instagram.com/johndoe"]["confidence"] == V.UNVERIFIABLE
    assert by_url["https://blog.example/x"]["confidence"] == V.LIKELY   # got the slot


def test_priority_spends_budget_on_the_useful_url_first(fake):
    fake({
        "https://api.github.com/users/johndoe": FakeResp(200, json_data={"login": "johndoe"}),
        "https://random-blog.example/p":
            FakeResp(200, text="mentions johndoe", url="https://random-blog.example/p"),
    })
    rs = [
        _result("https://random-blog.example/p", mode="username", target="johndoe"),  # rank 5
        _result("https://github.com/johndoe", mode="username", target="johndoe"),      # rank 0
    ]
    out = V.verify_results(rs, min_interval=0, max_checks=1)   # only ONE real check
    by_url = {r["href"]: r for r in out}
    assert by_url["https://github.com/johndoe"]["confidence"] == V.VERIFIED
    assert by_url["https://random-blog.example/p"]["evidence"]["reason"].startswith("check budget")
    assert [r["href"] for r in out] == [rs[0]["href"], rs[1]["href"]]   # caller order kept


def test_requests_missing_marks_all_unverifiable(monkeypatch):
    monkeypatch.setattr(V, "_HAVE_REQUESTS", False)
    out = V.verify_results([_result("https://github.com/x")])
    assert out[0]["confidence"] == V.UNVERIFIABLE
    assert "requests" in out[0]["evidence"]["reason"]


def test_input_not_mutated(fake):
    fake({"https://api.github.com/users/johndoe":
          FakeResp(200, json_data={"login": "johndoe"})})
    original = _result("https://github.com/johndoe")
    V.verify_results([original], min_interval=0)
    assert "confidence" not in original


# ---------------------------------------------------------------------------
# summarize + exposure_level formula
# ---------------------------------------------------------------------------

def test_summarize_counts():
    rs = [{"confidence": V.VERIFIED}, {"confidence": V.VERIFIED},
          {"confidence": V.FALSE_POSITIVE}, {"no": "conf"}]
    c = V.summarize(rs)
    assert c[V.VERIFIED] == 2 and c[V.FALSE_POSITIVE] == 1 and c[V.LIKELY] == 0


def _uv(host, reason):
    return {"confidence": V.UNVERIFIABLE, "href": f"https://{host}/x",
            "evidence": {"reason": reason}}


def test_unverifiable_breakdown_groups_by_reason_and_host():
    rs = [
        _uv("uk.linkedin.com", "login wall / JS-only — needs an authenticated session"),
        _uv("linkedin.com",    "login wall / JS-only — needs an authenticated session"),
        _uv("instagram.com",   "login wall / JS-only — needs an authenticated session"),
        _uv("a.example",       "check budget (80) exhausted"),
        _uv("b.example",       "check budget (80) exhausted"),
        _uv("c.example",       "not an HTTP(S) URL"),
        {"confidence": V.VERIFIED},                      # ignored
    ]
    bd = V.unverifiable_breakdown(rs)
    labels = [row[0] for row in bd]
    assert labels[0] == "login-walled" and bd[0][1] == 3       # most common first
    assert ("check budget exhausted", 2) == (bd[1][0], bd[1][1])
    # host detail for the login-walled bucket (hosts are not domain-collapsed)
    hosts = dict(bd[0][2])
    assert hosts == {"uk.linkedin.com": 1, "linkedin.com": 1, "instagram.com": 1}
    assert ("non-HTTP URL", 1) in [(r[0], r[1]) for r in bd]


def _hit(conf, category="Web", href="https://a.example/x", context=""):
    return {"confidence": conf, "category": category, "href": href,
            "evidence": {"context": context}}


def test_exposure_low_when_nothing_verified():
    level, pts, _ = V.exposure_level([_hit(V.FALSE_POSITIVE), {"x": 1}])
    assert (level, pts) == ("LOW", 0)


def test_exposure_medium_single_platform():
    level, pts, _ = V.exposure_level([_hit(V.LIKELY, "GitHub")])
    assert level == "MEDIUM" and pts == 2


def test_exposure_strong_identity_bonus():
    level, pts, _ = V.exposure_level([_hit(V.VERIFIED, "GitHub")])
    assert pts == 2 + V._W_STRONG_IDENTITY          # platform + strong-identity


def test_exposure_leak_and_email_bonuses_push_to_critical():
    rs = [
        _hit(V.VERIFIED, "GitHub", "https://github.com/j"),
        _hit(V.VERIFIED, "Reddit", "https://reddit.com/u/j"),
        _hit(V.VERIFIED, "Paste & Leak Sites", "https://pastebin.com/raw/x",
             context="contact johndoe@acme.com for more"),
    ]
    level, pts, breakdown = V.exposure_level(rs)
    # 3 platforms(6) + leak(4) + email(3) + strong(2) = 15  -> CRITICAL
    assert pts == 15 and level == "CRITICAL"
    assert any("leak" in b for b in breakdown)
    assert any("email" in b for b in breakdown)


def test_exposure_leak_word_category_needs_verified_not_just_likely():
    # a LIKELY hit on a "…leaked OR breach…" dork that landed on Wikipedia
    # must NOT trigger the leak bonus
    weak = [_hit(V.LIKELY, "Paste & Leak Sites", "https://en.wikipedia.org/wiki/Linux")]
    _, pts, breakdown = V.exposure_level(weak)
    assert pts == 2                                   # platform only, no leak bonus
    assert not any("leak" in b for b in breakdown)

    # …but a VERIFIED hit on that same noisy category does count
    strong = [_hit(V.VERIFIED, "Paste & Leak Sites", "https://random.example/x")]
    _, pts2, breakdown2 = V.exposure_level(strong)
    assert any("leak" in b for b in breakdown2)       # 2 + 4 + 2(strong) = 8

    # a real paste host counts even at LIKELY
    host = [_hit(V.LIKELY, "Paste & Leak Sites", "https://pastebin.com/raw/z")]
    assert any("leak" in b for b in V.exposure_level(host)[2])


def test_exposure_platform_cap():
    rs = [_hit(V.LIKELY, f"cat{i}", f"https://h{i}.example/x") for i in range(20)]
    _, pts, _ = V.exposure_level(rs)
    assert pts == V._W_PLATFORM_CAP * V._W_PLATFORM   # capped, no strong bonus


# ---------------------------------------------------------------------------
# identifier extraction + cross-correlation
# ---------------------------------------------------------------------------

def test_extract_identifiers():
    text = ("contact john.doe@acme.com or press@acme.com, follow @realjohn and "
            "@github, call +1 (555) 123-4567. sprite@2x.png is not an email.")
    ext = V._extract_identifiers(text, self_target="realjohn")
    assert "john.doe@acme.com" in ext["emails"]
    assert "press@acme.com" in ext["emails"]
    assert "sprite@2x.png" not in ext.get("emails", [])
    assert "realjohn" not in ext.get("handles", [])   # self dropped
    assert "github" not in ext.get("handles", [])     # stopword dropped
    assert any("555" in p for p in ext.get("phones", []))


def test_extract_identifiers_rejects_short_or_repeated_numbers():
    ext = V._extract_identifiers("ref 1111111111 and code 12345 and 999999999999")
    assert "phones" not in ext          # all rejected (repeated digits / too short)


def test_generic_check_stashes_extracted(fake):
    fake({"https://blog.example/p":
          FakeResp(200, text="<p>johndoe — email me at j@x.io</p>",
                   url="https://blog.example/p")})
    out = V.verify_results([_result("https://blog.example/p", mode="person",
                                    target="johndoe")], min_interval=0)
    assert out[0]["evidence"]["extracted"]["emails"] == ["j@x.io"]


def _cr(cat, url, **ext):
    return {"confidence": V.LIKELY, "category": cat, "href": url,
            "evidence": {"extracted": ext}}


def test_correlate_needs_two_distinct_sources():
    one = [_cr("GitHub", "https://github.com/j", emails=["j@x.io"])]
    assert V.correlate(one) == []                       # single source -> nothing

    two = [
        _cr("GitHub", "https://github.com/j", emails=["j@x.io"]),
        _cr("Forums", "https://f.example/t",  emails=["j@x.io"]),
    ]
    got = V.correlate(two)
    assert len(got) == 1
    assert got[0]["type"] == "email" and got[0]["value"] == "j@x.io"
    assert got[0]["confidence"] == "MEDIUM"
    assert sorted(got[0]["found_on"]) == ["Forums", "GitHub"]


def test_correlate_three_sources_is_high_and_sorted_first():
    rs = [
        _cr("A", "https://a/1", handles=["shared"]),
        _cr("B", "https://b/1", handles=["shared"]),
        _cr("C", "https://c/1", handles=["shared"]),
        _cr("A", "https://a/2", emails=["x@y.io"]),
        _cr("B", "https://b/2", emails=["x@y.io"]),
    ]
    got = V.correlate(rs)
    assert got[0]["value"] == "shared" and got[0]["confidence"] == "HIGH"
    assert got[1]["value"] == "x@y.io" and got[1]["confidence"] == "MEDIUM"


def test_build_email_recheck_targets():
    rs = [
        _cr("GitHub", "https://github.com/j", emails=["j@x.io"]),
        {"href": "https://pastebin.com/raw/a", "category": "Paste & Leak Sites"},
        {"href": "https://news.example/1", "category": "Person in News"},
    ]
    targets = V.build_email_recheck_targets(rs)
    # 1 email × 1 leak URL (pastebin host; the news URL is not a leak surface)
    assert len(targets) == 1
    assert targets[0]["target"] == "j@x.io"
    assert targets[0]["href"] == "https://pastebin.com/raw/a"
    assert targets[0]["mode"] == "email"


def test_build_email_recheck_targets_empty_without_leak_urls():
    rs = [_cr("GitHub", "https://github.com/j", emails=["j@x.io"])]
    assert V.build_email_recheck_targets(rs) == []
