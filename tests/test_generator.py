"""
RAG generator — risk parsing, citation mapping, provider dispatch, and each
provider's streaming / non-streaming path. Every SDK (anthropic, openai,
google.generativeai) and `requests` is replaced with an in-memory fake via
sys.modules, so nothing is installed or contacted.
"""

import json
import sys
import types
from types import SimpleNamespace

import pytest

from modules.rag import generator as G
from modules.rag.models import NewsItem, SearchBundle


def _bundle(n=3, target="acme"):
    items = tuple(
        NewsItem(title=f"t{i}", url=f"https://e.com/{i}", snippet="s",
                 category="News", target=target, query="q")
        for i in range(1, n + 1)
    )
    return SearchBundle(items=items, target=target, timestamp="ts")


REPORT = "## Findings\nBreach [Source 2] and [Source 1]\n\nRisk Level: HIGH"


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Risk Level: LOW", "LOW"),
    ("**Risk Level:** critical", "CRITICAL"),
    ("risk_level: medium", "MEDIUM"),
    ("Risk Level: BOGUS ... but HIGH exposure", "HIGH"),   # falls back to keyword scan
    ("nothing CRITICAL and also LOW", "CRITICAL"),          # highest keyword wins
    ("no rating here", "UNKNOWN"),
])
def test_parse_risk_level(text, expected):
    assert G._parse_risk_level(text) == expected


def test_extract_cited_urls_dedupes_sorts_and_drops_out_of_range():
    items = _bundle(3).items
    text = "[Source 3] [Source 1] [Source 3] [Source 9] [Source 0]"
    assert G._extract_cited_urls(text, items) == ("https://e.com/1", "https://e.com/3")


def test_make_analysis_fields():
    a = G._make_analysis("acme", REPORT, "m", _bundle(3).items)
    assert a.succeeded
    assert a.risk_level == "HIGH"
    assert a.cited_sources == ("https://e.com/1", "https://e.com/2")
    assert a.source_count == 3
    assert a.model == "m"


def test_error_analysis_is_not_succeeded():
    a = G._make_error_analysis("acme", "m", "boom")
    assert not a.succeeded
    assert a.error == "boom" and a.risk_level == "UNKNOWN"


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------

def test_generate_empty_bundle_short_circuits():
    a = G.generate(SearchBundle(items=(), target="x", timestamp="ts"), "claude")
    assert not a.succeeded and "No search results" in a.error


def test_generate_unknown_provider():
    a = G.generate(_bundle(), "nope")
    assert not a.succeeded and "Unknown provider 'nope'" in a.error


@pytest.mark.parametrize("provider,fn", [
    ("claude", "generate_with_claude"),
    ("OpenAI", "generate_with_openai"),
    ("gemini", "generate_with_gemini"),
    ("ollama", "generate_with_ollama"),
])
def test_generate_routes_to_provider_with_defaults(monkeypatch, provider, fn):
    seen = {}

    def fake(bundle, *args, **kwargs):
        seen["args"], seen["kwargs"] = args, kwargs
        return "sentinel"

    monkeypatch.setattr(G, fn, fake)
    assert G.generate(_bundle(), provider, api_key="k") == "sentinel"
    default = G.DEFAULT_MODELS[provider.lower()]
    if provider.lower() == "ollama":
        assert seen["kwargs"]["model"] == default
    else:
        assert seen["args"][:2] == ("k", default)


def test_generate_explicit_model_overrides_default(monkeypatch):
    seen = {}
    monkeypatch.setattr(G, "generate_with_openai",
                        lambda b, key, model, *a: seen.setdefault("model", model))
    G.generate(_bundle(), "openai", model="gpt-custom")
    assert seen["model"] == "gpt-custom"


# ---------------------------------------------------------------------------
# fake SDKs
# ---------------------------------------------------------------------------

def _install(monkeypatch, name, module):
    monkeypatch.setitem(sys.modules, name, module)


class _FakeAnthropicClient:
    def __init__(self, response=None, stream_chunks=None, raise_exc=None):
        self._response, self._chunks, self._exc = response, stream_chunks, raise_exc
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if self._exc:
            raise self._exc
        return self._response

    def stream(self, **kw):
        self.calls.append(kw)
        chunks = self._chunks

        class _Ctx:
            text_stream = iter(chunks)
            def __enter__(self_inner): return self_inner
            def __exit__(self_inner, *a): return False
        return _Ctx()


def _fake_anthropic(monkeypatch, client):
    mod = types.ModuleType("anthropic")
    mod.Anthropic = lambda api_key: client
    _install(monkeypatch, "anthropic", mod)


def test_claude_non_streaming_skips_leading_non_text_block(monkeypatch):
    resp = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="thinking", thinking="..."),
                 SimpleNamespace(type="text", text=REPORT)],
    )
    client = _FakeAnthropicClient(response=resp)
    _fake_anthropic(monkeypatch, client)

    a = G.generate_with_claude(_bundle(), "key", model="claude-x", max_tokens=123)
    assert a.succeeded and a.summary == REPORT and a.model == "claude-x"
    call = client.calls[0]
    assert call["model"] == "claude-x" and call["max_tokens"] == 123
    assert call["messages"][0]["role"] == "user" and call["system"]


def test_claude_refusal_is_clean_error(monkeypatch):
    resp = SimpleNamespace(stop_reason="refusal", content=[])
    _fake_anthropic(monkeypatch, _FakeAnthropicClient(response=resp))
    a = G.generate_with_claude(_bundle(), "key")
    assert not a.succeeded and "refusal" in a.error


def test_claude_streaming_forwards_tokens(monkeypatch):
    _fake_anthropic(monkeypatch, _FakeAnthropicClient(stream_chunks=["Risk ", "Level: LOW"]))
    tokens = []
    a = G.generate_with_claude(_bundle(), "key", on_token=tokens.append)
    assert tokens == ["Risk ", "Level: LOW"]
    assert a.summary == "Risk Level: LOW" and a.risk_level == "LOW"


def test_claude_exception_becomes_error_analysis(monkeypatch):
    _fake_anthropic(monkeypatch, _FakeAnthropicClient(raise_exc=RuntimeError("401 bad key")))
    a = G.generate_with_claude(_bundle(), "key")
    assert not a.succeeded and a.error == "401 bad key"
    assert a.model == G.DEFAULT_MODELS["claude"]


def _fake_openai(monkeypatch, create):
    mod = types.ModuleType("openai")
    mod.OpenAI = lambda api_key: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    _install(monkeypatch, "openai", mod)


def test_openai_non_streaming(monkeypatch):
    calls = []

    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=REPORT))])

    _fake_openai(monkeypatch, create)
    a = G.generate_with_openai(_bundle(), "k", model="gpt-x")
    assert a.succeeded and a.risk_level == "HIGH" and a.model == "gpt-x"
    assert [m["role"] for m in calls[0]["messages"]] == ["system", "user"]


def test_openai_streaming_skips_empty_deltas(monkeypatch):
    def chunk(c):
        return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=c))])

    _fake_openai(monkeypatch, lambda **kw: iter([chunk("a"), chunk(None), chunk("b")]))
    tokens = []
    a = G.generate_with_openai(_bundle(), "k", on_token=tokens.append)
    assert tokens == ["a", "b"] and a.summary == "ab"


def test_openai_none_content_is_not_succeeded(monkeypatch):
    _fake_openai(monkeypatch, lambda **kw: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None))]))
    a = G.generate_with_openai(_bundle(), "k")
    assert a.error is None and not a.succeeded


def _fake_gemini(monkeypatch, generate_content):
    google = types.ModuleType("google")
    genai = types.ModuleType("google.generativeai")
    genai.configured = {}
    genai.configure = lambda api_key: genai.configured.setdefault("key", api_key)
    genai.GenerationConfig = lambda **kw: kw
    genai.GenerativeModel = lambda **kw: SimpleNamespace(
        generate_content=generate_content, init=kw)
    google.generativeai = genai
    _install(monkeypatch, "google", google)
    _install(monkeypatch, "google.generativeai", genai)
    return genai


def test_gemini_non_streaming_prefixes_model(monkeypatch):
    genai = _fake_gemini(monkeypatch, lambda prompt, stream=False: SimpleNamespace(text=REPORT))
    a = G.generate_with_gemini(_bundle(), "gk", model="gem-x")
    assert a.succeeded and a.model == "gemini/gem-x"
    assert genai.configured["key"] == "gk"


def test_gemini_streaming(monkeypatch):
    _fake_gemini(monkeypatch, lambda prompt, stream=False: iter(
        [SimpleNamespace(text="x"), SimpleNamespace(text=""), SimpleNamespace(text="y")]))
    tokens = []
    a = G.generate_with_gemini(_bundle(), "gk", on_token=tokens.append)
    assert tokens == ["x", "y"] and a.summary == "xy"


def test_gemini_exception(monkeypatch):
    def boom(prompt, stream=False):
        raise ValueError("quota")
    _fake_gemini(monkeypatch, boom)
    a = G.generate_with_gemini(_bundle(), "gk")
    assert a.error == "quota" and a.model.startswith("gemini/")


class _FakeResp:
    def __init__(self, payload=None, lines=None, status_ok=True):
        self._payload, self._lines, self._ok = payload, lines or [], status_ok

    def raise_for_status(self):
        if not self._ok:
            raise RuntimeError("HTTP 500")

    def json(self):
        return self._payload

    def iter_lines(self):
        return iter(self._lines)

    def __enter__(self): return self
    def __exit__(self, *a): return False


def _fake_requests(monkeypatch, resp, calls):
    mod = types.ModuleType("requests")

    def post(url, json=None, timeout=None, stream=False):
        calls.append({"url": url, "json": json, "timeout": timeout, "stream": stream})
        return resp
    mod.post = post
    _install(monkeypatch, "requests", mod)


def test_ollama_non_streaming(monkeypatch):
    calls = []
    _fake_requests(monkeypatch, _FakeResp(payload={"response": REPORT}), calls)
    a = G.generate_with_ollama(_bundle(), model="llama-x", base_url="http://h:1", timeout=5)
    assert a.succeeded and a.model == "ollama/llama-x"
    assert calls[0]["url"] == "http://h:1/api/generate"
    assert calls[0]["json"]["stream"] is False and calls[0]["timeout"] == 5


def test_ollama_streaming_skips_bad_lines_and_stops_on_done(monkeypatch):
    lines = [
        json.dumps({"response": "Risk "}).encode(),
        b"",
        b"not json",
        json.dumps({"response": "Level: MEDIUM", "done": True}).encode(),
        json.dumps({"response": "IGNORED"}).encode(),
    ]
    calls = []
    _fake_requests(monkeypatch, _FakeResp(lines=lines), calls)
    tokens = []
    a = G.generate_with_ollama(_bundle(), on_token=tokens.append)
    assert tokens == ["Risk ", "Level: MEDIUM"]
    assert a.risk_level == "MEDIUM"
    assert calls[0]["stream"] is True


def test_ollama_http_error(monkeypatch):
    _fake_requests(monkeypatch, _FakeResp(status_ok=False), [])
    a = G.generate_with_ollama(_bundle())
    assert not a.succeeded and a.error == "HTTP 500"
