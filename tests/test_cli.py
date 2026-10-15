"""
CLI (osintnews_cli.py) — consent gate, privacy of the audit log, .env
loading, target sanity checks, SpiderFoot / multi-format export, AI key
handling, watch loop, the _run_search flow and argv routing in main().
The search engine, verifier, notifier and AI pipeline are stubbed; every
file is written under tmp_path.
"""

import json
import os
from types import SimpleNamespace

import pytest

import osintnews_cli as cli
import modules.searcher as searcher
from modules.dorker_osint import categories_for_mode


def _feed(monkeypatch, *answers):
    """Make input() return `answers` in order (EOF after the last one)."""
    it = iter(answers)

    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    monkeypatch.setattr("builtins.input", fake_input)


def _res(**kw):
    base = {"target": "alice", "category": "GitHub", "title": "alice on GitHub",
            "href": "https://github.com/alice", "body": "profile", "query": "q",
            "mode": "username"}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# input helpers
# ---------------------------------------------------------------------------

def test_prompt_strips_bom_and_falls_back_to_default(monkeypatch):
    _feed(monkeypatch, "﻿  ", "﻿value ")
    assert cli._prompt("x", "dflt") == "dflt"
    assert cli._prompt("x") == "value"


def test_prompt_exits_cleanly_on_eof(monkeypatch):
    _feed(monkeypatch)
    with pytest.raises(SystemExit) as e:
        cli._prompt("x")
    assert e.value.code == 0


def test_choose_retries_until_valid(monkeypatch, capsys):
    _feed(monkeypatch, "0", "abc", "2")
    assert cli._choose([("a", "A"), ("b", "B")]) == "b"
    assert capsys.readouterr().out.count("Invalid") == 2


def test_multi_choose_all_and_subset(monkeypatch):
    opts = [("a", "A"), ("b", "B"), ("c", "C")]
    _feed(monkeypatch, "")
    assert cli._multi_choose(opts) == ["a", "b", "c"]
    _feed(monkeypatch, "3, 1")
    assert cli._multi_choose(opts) == ["c", "a"]
    _feed(monkeypatch, "1,9", "2")
    assert cli._multi_choose(opts) == ["b"]


# ---------------------------------------------------------------------------
# consent gate
# ---------------------------------------------------------------------------

def test_consent_not_asked_for_username(monkeypatch):
    _feed(monkeypatch)   # any prompt would raise SystemExit
    assert cli._consent_check("username", "alice") is True


@pytest.mark.parametrize("mode", ["email", "phone", "person"])
@pytest.mark.parametrize("answer,ok", [("1", True), ("2", True), ("3", True),
                                       ("0", False), ("", False), ("yes", False)])
def test_consent_required_for_sensitive_modes(monkeypatch, mode, answer, ok):
    _feed(monkeypatch, answer)
    assert cli._consent_check(mode, "x") is ok


# ---------------------------------------------------------------------------
# audit log
# ---------------------------------------------------------------------------

def test_audit_log_never_stores_plaintext_target(tmp_path):
    cli._audit_log("email", "secret@example.com", ["E1", "E2"], 7, str(tmp_path))
    cli._audit_log("email", "secret@example.com", ["E1"], 0, str(tmp_path))
    log = (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert "secret" not in log and "example.com" not in log
    lines = log.splitlines()
    assert len(lines) == 2
    assert "mode=email" in lines[0] and "categories=E1,E2" in lines[0]
    assert "results=7" in lines[0]
    h0 = lines[0].split("target_hash=")[1].split()[0]
    h1 = lines[1].split("target_hash=")[1].split()[0]
    assert h0 == h1 and len(h0) == 16


def test_audit_log_failure_is_swallowed(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    cli._audit_log("username", "a", [], 0, str(blocker / "sub"))   # must not raise


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------

def test_load_dotenv_parses_and_never_overrides(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "# comment\n\nOSN_A=1\nOSN_B = \"two\"\nOSN_C='three'\nnot a pair\n"
        "OSN_EXISTING=from_file\nOSN_URL=http://h/?a=b=c\n",
        encoding="utf-8",
    )
    for k in ("OSN_A", "OSN_B", "OSN_C", "OSN_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OSN_EXISTING", "from_env")

    cli._load_dotenv(str(tmp_path))
    assert os.environ["OSN_A"] == "1"
    assert os.environ["OSN_B"] == "two"
    assert os.environ["OSN_C"] == "three"
    assert os.environ["OSN_URL"] == "http://h/?a=b=c"
    assert os.environ["OSN_EXISTING"] == "from_env"
    for k in ("OSN_A", "OSN_B", "OSN_C", "OSN_URL"):
        monkeypatch.delenv(k)


def test_load_dotenv_missing_file_is_noop(tmp_path):
    cli._load_dotenv(str(tmp_path))


# ---------------------------------------------------------------------------
# target sanity check
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,target,warns", [
    ("email", "a@b.co", False),
    ("email", "not-an-email", True),
    ("phone", "+351 912 345 678", False),
    ("phone", "12-34", True),
    ("username", "ab", True),
    ("username", "alice", False),
    ("person", "Alice", True),
    ("person", "Alice Smith", False),
])
def test_target_warning(mode, target, warns):
    assert bool(cli._target_warning(mode, target)) is warns


# ---------------------------------------------------------------------------
# SpiderFoot export
# ---------------------------------------------------------------------------

def test_spiderfoot_maps_types_confidence_and_drops_false_positives(tmp_path):
    p = tmp_path / "sf.json"
    cli._save_spiderfoot_json([
        _res(confidence="VERIFIED", evidence={"context": "ctx"}),
        _res(href="https://x/2", mode="email"),
        _res(href="https://x/3", confidence="FALSE_POSITIVE"),
        _res(href="", title="title only", mode="weird", category="Some Cat"),
    ], "alice", str(p), correlations=[
        {"type": "email", "value": "a@b.c", "found_on": ["github", "gitlab"],
         "sources": ["https://github.com/alice"], "confidence": "HIGH"},
        {"type": "other", "value": "v", "found_on": ["x"], "sources": [],
         "confidence": "MEDIUM"},
    ])
    ev = json.loads(p.read_text(encoding="utf-8"))
    assert len(ev) == 5                       # 3 results kept + 2 correlations
    assert ev[0]["type"] == "SOCIAL_MEDIA" and ev[0]["confidence"] == 100
    assert ev[0]["snippet"] == "ctx" and ev[0]["verified"] == "VERIFIED"
    assert ev[1]["type"] == "EMAILADDR_COMPROMISED" and ev[1]["confidence"] == 75
    assert ev[1]["verified"] == "NOT_CHECKED"
    assert ev[2]["type"] == "LINKED_URL_INTERNAL" and ev[2]["data"] == "title only"
    assert ev[2]["module"] == "osintnews_some_cat"
    assert ev[3]["type"] == "AFFILIATE_EMAILADDR" and ev[3]["confidence"] == 90
    assert ev[4]["type"] == "RAW_RIR_DATA" and ev[4]["url"] == ""
    assert all("https://x/3" != e.get("url") for e in ev)


# ---------------------------------------------------------------------------
# export menu
# ---------------------------------------------------------------------------

def test_offer_export_writes_every_format(tmp_path, monkeypatch, capsys):
    _feed(monkeypatch, "1, 2,3,4,5,9")
    cli._offer_export([_res()], "al/ice", str(tmp_path))
    names = sorted(os.listdir(tmp_path))
    assert any(n.startswith("osintnews_al_ice_") and n.endswith(".html") for n in names)
    for suffix in (".json", ".csv", ".md", "_spiderfoot.json"):
        assert any(n.startswith("osint_al_ice_") and n.endswith(suffix) for n in names), suffix
    assert "Skipped unknown option '9'" in capsys.readouterr().out


def test_offer_export_one_failure_does_not_abort_the_rest(tmp_path, monkeypatch, capsys):
    import modules.reporter as rep

    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(rep, "save_json", boom)
    _feed(monkeypatch, "2,3")
    cli._offer_export([_res()], "alice", str(tmp_path))
    out = capsys.readouterr().out
    assert "Export option 2 failed: disk full" in out
    assert any(n.endswith(".csv") for n in os.listdir(tmp_path))


def test_offer_export_skip_and_empty(tmp_path, monkeypatch, capsys):
    _feed(monkeypatch, "")
    cli._offer_export([_res()], "alice", str(tmp_path))
    assert "Skipped export" in capsys.readouterr().out
    cli._offer_export([], "alice", str(tmp_path))       # no prompt at all
    assert os.listdir(tmp_path) == []


# ---------------------------------------------------------------------------
# AI analysis
# ---------------------------------------------------------------------------

def test_ai_analysis_requires_api_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert cli._run_ai_analysis([_res()], "alice", "claude") is None
    assert "Set ANTHROPIC_API_KEY" in capsys.readouterr().out


def test_ai_analysis_ollama_needs_no_key_and_returns_analysis(monkeypatch):
    import modules.rag.pipeline as pipeline
    seen = {}
    analysis = SimpleNamespace(succeeded=True, risk_level="LOW", source_count=1,
                               cited_sources=(), error=None)

    def fake_run(**kw):
        seen.update(kw)
        kw["on_token"]("tok")
        return SimpleNamespace(analysis=analysis)
    monkeypatch.setattr(pipeline, "run_pipeline", fake_run)
    assert cli._run_ai_analysis([_res()], "alice", "OLLAMA") is analysis
    assert seen["provider"] == "ollama" and seen["api_key"] == ""


def test_ai_analysis_failure_returns_none(monkeypatch, capsys):
    import modules.rag.pipeline as pipeline
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(pipeline, "run_pipeline", lambda **kw: SimpleNamespace(
        analysis=SimpleNamespace(succeeded=False, error="quota")))
    assert cli._run_ai_analysis([_res()], "alice", "openai") is None
    assert "quota" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# watch loop
# ---------------------------------------------------------------------------

def test_watch_loop_interval_zero_runs_once():
    calls = []
    cli._watch_loop(lambda: calls.append(1), 0)
    assert calls == [1]


def test_watch_loop_repeats_until_ctrl_c(monkeypatch):
    import time
    calls, sleeps = [], []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    def run_once():
        calls.append(1)
        if len(calls) == 3:
            raise KeyboardInterrupt
    cli._watch_loop(run_once, 600)
    assert len(calls) == 3 and sleeps == [600, 600]


# ---------------------------------------------------------------------------
# _run_search flow (search engine stubbed)
# ---------------------------------------------------------------------------

@pytest.fixture
def no_network(monkeypatch):
    calls = {"search": 0}

    def fake_search(dorks, **kw):
        calls["search"] += 1
        calls["dorks"] = dorks
        return [_res()]
    monkeypatch.setattr(searcher, "run_searches_with_callback", fake_search)
    return calls


def test_run_search_cancelled_consent_runs_nothing(tmp_path, monkeypatch, no_network):
    _feed(monkeypatch, "0")
    cli._run_search("email", "a@b.co", ["E1"], str(tmp_path / "r"), str(tmp_path / "d"))
    assert no_network["search"] == 0
    assert not (tmp_path / "d").exists()


def test_run_search_full_flow_logs_history_and_offers_export(tmp_path, monkeypatch,
                                                             no_network, capsys):
    keys = list(categories_for_mode("username"))
    _feed(monkeypatch, "2")                      # export: JSON
    reports, data = tmp_path / "r", tmp_path / "d"
    cli._run_search("username", "alice", keys, str(reports), str(data))
    assert no_network["search"] == 1 and no_network["dorks"]
    assert (data / "audit.log").is_file()
    assert "alice" in (data / "osint_history.json").read_text(encoding="utf-8")
    assert any(n.endswith(".json") for n in os.listdir(reports))
    assert "Username Correlation Summary" in capsys.readouterr().out


def test_run_search_watch_mode_baseline_then_nothing_new(tmp_path, monkeypatch,
                                                         no_network, capsys):
    _feed(monkeypatch)                           # watch mode must never prompt
    import modules.notifier as notifier
    notes = []
    monkeypatch.setattr(notifier, "notify", lambda *a: notes.append(a))
    args = ("username", "alice", list(categories_for_mode("username")),
            str(tmp_path / "r"), str(tmp_path / "d"))

    cli._run_search(*args, watch=True)
    assert "baseline established" in capsys.readouterr().out
    assert any(n.startswith("watch_") for n in os.listdir(tmp_path / "r"))

    cli._run_search(*args, watch=True)
    assert "Nothing new" in capsys.readouterr().out
    assert notes == []


def test_run_search_watch_mode_notifies_on_new_hits(tmp_path, monkeypatch, capsys):
    _feed(monkeypatch)
    import modules.notifier as notifier
    notes = []
    monkeypatch.setattr(notifier, "notify", lambda *a: notes.append(a))
    batches = iter([[_res()], [_res(), _res(href="https://gitlab.com/alice", category="GitLab")]])
    monkeypatch.setattr(searcher, "run_searches_with_callback", lambda d, **k: next(batches))
    args = ("username", "alice", list(categories_for_mode("username")),
            str(tmp_path / "r"), str(tmp_path / "d"))
    cli._run_search(*args, watch=True)
    cli._run_search(*args, watch=True)
    assert "1 NEW result" in capsys.readouterr().out
    assert len(notes) == 1 and "1 new hit" in notes[0][1]


# ---------------------------------------------------------------------------
# main() argv routing
# ---------------------------------------------------------------------------

def _capture_run_search(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "_run_search", lambda *a, **k: seen.append((a, k)))
    monkeypatch.setattr(cli, "_load_dotenv", lambda d: None)
    return seen


def test_main_direct_mode_uses_all_categories(monkeypatch):
    seen = _capture_run_search(monkeypatch)
    monkeypatch.setattr("sys.argv", ["x", "--mode", "username", "--target", "alice",
                                     "--verify", "--ai", "--provider", "ollama"])
    cli.main()
    (args, kw), = seen
    assert args[:3] == ("username", "alice", list(categories_for_mode("username")))
    assert kw["verify"] is True and kw["run_ai"] is True
    assert kw["ai_provider"] == "ollama" and kw["watch"] is False


def test_main_watch_disables_ai_and_bumps_interval(monkeypatch, capsys):
    seen = _capture_run_search(monkeypatch)
    loops = []
    monkeypatch.setattr(cli, "_watch_loop", lambda fn, interval: (loops.append(interval), fn()))
    monkeypatch.setattr("sys.argv", ["x", "--mode", "username", "--target", "alice",
                                     "--watch", "--interval", "10", "--ai"])
    cli.main()
    assert loops == [cli._MIN_WATCH_INTERVAL]
    assert seen[0][1]["run_ai"] is False and seen[0][1]["watch"] is True
    assert "--interval bumped" in capsys.readouterr().out


def test_main_without_target_goes_interactive(monkeypatch):
    _capture_run_search(monkeypatch)
    hit = []
    monkeypatch.setattr(cli, "_interactive", lambda r, d: hit.append((r, d)))
    monkeypatch.setattr("sys.argv", ["x", "--mode", "username"])
    cli.main()
    assert hit and hit[0][0].endswith("reports") and hit[0][1].endswith("data")
