"""
Watch-mode baseline store — first-run / delta / persistence / privacy.
"""

import json

from modules import watchstore


def _res(*urls):
    return [{"href": u, "title": u, "category": "Web"} for u in urls]


def test_first_run_reports_everything_and_persists(tmp_path):
    d = str(tmp_path)
    out = watchstore.diff_and_update(d, "johndoe", "username",
                                     _res("https://a/1", "https://a/2"))
    assert out["first_run"] is True
    assert len(out["new"]) == 2
    assert out["known"] == 0
    assert out["last_run"] is None
    # a second, identical run now sees nothing new
    out2 = watchstore.diff_and_update(d, "johndoe", "username",
                                      _res("https://a/1", "https://a/2"))
    assert out2["first_run"] is False
    assert out2["new"] == []
    assert out2["known"] == 2
    assert out2["last_run"] is not None


def test_only_new_urls_are_reported(tmp_path):
    d = str(tmp_path)
    watchstore.diff_and_update(d, "t", "username", _res("https://a/1"))
    out = watchstore.diff_and_update(d, "t", "username",
                                    _res("https://a/1", "https://a/2", "https://a/3"))
    assert [r["href"] for r in out["new"]] == ["https://a/2", "https://a/3"]
    assert out["known"] == 1


def test_target_is_hashed_not_plaintext(tmp_path):
    d = str(tmp_path)
    watchstore.diff_and_update(d, "SecretTarget", "email", _res("https://x/1"))
    blob = "".join(p.read_text(encoding="utf-8")
                   for p in (tmp_path / "watch").iterdir())
    assert "SecretTarget" not in blob
    assert "target_hash" in blob


def test_run_history_is_capped(tmp_path):
    d = str(tmp_path)
    for i in range(60):
        watchstore.diff_and_update(d, "t", "username", _res(f"https://a/{i}"))
    state = watchstore.load(d, "t", "username")
    assert len(state["runs"]) == 50
    assert len(state["seen"]) == 60      # every URL is still remembered


def test_corrupt_baseline_is_tolerated(tmp_path):
    d = tmp_path / "data"
    (d / "watch").mkdir(parents=True)
    key = watchstore._key("t", "username")
    (d / "watch" / f"{key}.json").write_text("{ broken", encoding="utf-8")
    out = watchstore.diff_and_update(str(d), "t", "username", _res("https://a/1"))
    assert out["first_run"] is True and len(out["new"]) == 1


def test_mode_and_target_are_namespaced(tmp_path):
    d = str(tmp_path)
    watchstore.diff_and_update(d, "t", "username", _res("https://a/1"))
    # same target, different mode -> independent baseline
    out = watchstore.diff_and_update(d, "t", "email", _res("https://a/1"))
    assert out["first_run"] is True
