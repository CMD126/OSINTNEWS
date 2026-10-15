"""
Where OSINTNEWS keeps its writable state (data/ and reports/).

  1. $OSINTNEWS_HOME, if set.
  2. The repo checkout, when run from one — detected by data/.gitkeep, which
     ships in the repo but never in a wheel. Keeps `python osintnews.py`
     behaving exactly as before.
  3. ~/.osintnews otherwise (pip / pipx install), so settings.json with API
     keys and search reports never land inside site-packages.
"""

from __future__ import annotations

import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_home() -> str:
    env = os.environ.get("OSINTNEWS_HOME", "").strip()
    if env:
        return os.path.abspath(os.path.expanduser(env))
    if os.path.isfile(os.path.join(_REPO_ROOT, "data", ".gitkeep")):
        return _REPO_ROOT
    return os.path.join(os.path.expanduser("~"), ".osintnews")


def data_dir() -> str:
    return os.path.join(app_home(), "data")


def reports_dir() -> str:
    return os.path.join(app_home(), "reports")
