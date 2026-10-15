"""
Watch-mode baseline store.

Remembers which result URLs have already been seen for a (target, mode) pair so
a later run can report only what is NEW. Used by the CLI's `--watch` flag.

Privacy: the target is stored only as a SHA-256 prefix (same convention as
data/audit.log) — never in plaintext. Files live in data/watch/ which is
git-ignored.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

_RUN_HISTORY_CAP = 50


def _key(target: str, mode: str) -> str:
    return hashlib.sha256(f"{mode}:{target}".encode()).hexdigest()[:16]


def _path(data_dir: str, target: str, mode: str) -> str:
    return os.path.join(data_dir, "watch", f"{_key(target, mode)}.json")


def load(data_dir: str, target: str, mode: str) -> dict:
    """Return the stored baseline, or a fresh empty one."""
    try:
        with open(_path(data_dir, target, mode), "r", encoding="utf-8") as fh:
            state = json.load(fh)
            state.setdefault("seen", [])
            state.setdefault("runs", [])
            return state
    except (FileNotFoundError, ValueError, OSError):
        return {"mode": mode, "target_hash": _key(target, mode),
                "seen": [], "runs": []}


def diff_and_update(data_dir: str, target: str, mode: str, results: list,
                    *, categories: list | None = None) -> dict:
    """
    Compare the current result URLs against the stored baseline, persist the
    merged baseline, and return:

      {"new": [result dict, ...],   # results whose URL was not seen before
       "known": int,               # how many current results were already seen
       "first_run": bool,          # True when there was no prior baseline
       "last_run": str | None}     # ISO timestamp of the previous run
    """
    state = load(data_dir, target, mode)
    seen = set(state.get("seen", []))
    prior_runs = state.get("runs", [])
    first_run = not seen and not prior_runs
    last_run = prior_runs[-1]["at"] if prior_runs else None

    new, current = [], []
    for r in results:
        url = (r.get("href") or "").strip()
        if not url:
            continue
        current.append(url)
        if url not in seen:
            new.append(r)

    seen.update(current)
    state["seen"] = sorted(seen)
    state["runs"] = (prior_runs + [{
        "at":         datetime.now().isoformat(timespec="seconds"),
        "results":    len(current),
        "new":        len(new),
        "categories": list(categories or []),
    }])[-_RUN_HISTORY_CAP:]

    path = _path(data_dir, target, mode)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass  # a failed write just means the next run re-reports the same items

    return {"new": new, "known": len(current) - len(new),
            "first_run": first_run, "last_run": last_run}
