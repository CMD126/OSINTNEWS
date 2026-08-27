"""
HistoryManager persistence + the new targeted update() method.
"""

import json

from modules.history import HistoryManager


def test_add_assigns_id_and_date(tmp_path):
    hm = HistoryManager(str(tmp_path / "h.json"))
    entry = hm.add({"targets": "x", "result_count": 3})
    assert entry["id"]
    assert entry["date"]
    assert entry["targets"] == "x"


def test_persists_across_instances(tmp_path):
    path = str(tmp_path / "h.json")
    HistoryManager(path).add({"targets": "a"})
    assert len(HistoryManager(path).all()) == 1


def test_all_returns_newest_first(tmp_path):
    hm = HistoryManager(str(tmp_path / "h.json"))
    hm.add({"targets": "first"})
    hm.add({"targets": "second"})
    assert [e["targets"] for e in hm.all()] == ["second", "first"]


def test_update_targets_specific_entry(tmp_path):
    path = str(tmp_path / "h.json")
    hm = HistoryManager(path)
    first  = hm.add({"targets": "a", "risk_level": "—"})
    second = hm.add({"targets": "b", "risk_level": "—"})

    updated = hm.update(first["id"], risk_level="HIGH")
    assert updated["risk_level"] == "HIGH"

    # only the targeted row changed, and it was persisted to disk
    on_disk = {e["id"]: e for e in json.loads(open(path, encoding="utf-8").read())}
    assert on_disk[first["id"]]["risk_level"] == "HIGH"
    assert on_disk[second["id"]]["risk_level"] == "—"


def test_update_unknown_id_returns_none(tmp_path):
    hm = HistoryManager(str(tmp_path / "h.json"))
    hm.add({"targets": "a"})
    assert hm.update("does-not-exist", risk_level="LOW") is None


def test_corrupt_file_is_tolerated(tmp_path):
    path = tmp_path / "h.json"
    path.write_text("{ not valid json", encoding="utf-8")
    hm = HistoryManager(str(path))
    assert hm.all() == []
    hm.add({"targets": "recovered"})
    assert len(hm.all()) == 1
