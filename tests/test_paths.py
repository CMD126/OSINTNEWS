"""
State-directory resolution: $OSINTNEWS_HOME > repo checkout > ~/.osintnews.
"""

import os

from modules import paths


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("OSINTNEWS_HOME", str(tmp_path / "home"))
    assert paths.app_home() == str(tmp_path / "home")
    assert paths.data_dir() == os.path.join(str(tmp_path / "home"), "data")
    assert paths.reports_dir() == os.path.join(str(tmp_path / "home"), "reports")


def test_blank_env_is_ignored(monkeypatch):
    monkeypatch.setenv("OSINTNEWS_HOME", "   ")
    assert paths.app_home() == paths._REPO_ROOT     # this test runs from a checkout


def test_checkout_detected_by_gitkeep(monkeypatch, tmp_path):
    monkeypatch.delenv("OSINTNEWS_HOME", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / ".gitkeep").write_text("")
    monkeypatch.setattr(paths, "_REPO_ROOT", str(tmp_path))
    assert paths.app_home() == str(tmp_path)


def test_installed_package_falls_back_to_user_home(monkeypatch, tmp_path):
    monkeypatch.delenv("OSINTNEWS_HOME", raising=False)
    monkeypatch.setattr(paths, "_REPO_ROOT", str(tmp_path / "site-packages"))
    monkeypatch.setattr(os.path, "expanduser",
                        lambda p: p.replace("~", str(tmp_path / "user"), 1))
    assert paths.app_home() == os.path.join(str(tmp_path / "user"), ".osintnews")
