"""
Search history manager - persists past searches to a JSON file.
"""

import json
import os
import uuid
import threading
from datetime import datetime


class HistoryManager:
    def __init__(self, path: str):
        self.path    = path
        self.entries: list = []
        self._lock   = threading.Lock()
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    self.entries = json.load(fh)
            except Exception:
                self.entries = []

    def _save(self):
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.entries, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, data: dict) -> dict:
        """Add a new history entry. Returns the entry with auto-generated id and date."""
        with self._lock:
            entry = {
                "id":   str(uuid.uuid4()),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                **data,
            }
            self.entries.append(entry)
            self._save()
            return entry

    def get(self, entry_id: str) -> dict | None:
        with self._lock:
            for e in self.entries:
                if e.get("id") == entry_id:
                    return e
            return None

    def update(self, entry_id: str, **fields) -> dict | None:
        """
        Merge `fields` into the entry with the given id and persist.
        Returns the updated entry, or None if no entry matches.

        Preferred over reaching into `.entries[-1]` + `._save()` from callers:
        it targets a specific entry by id, so a second search starting before
        an async task (e.g. AI analysis) finishes cannot clobber the wrong row.
        """
        with self._lock:
            for e in self.entries:
                if e.get("id") == entry_id:
                    e.update(fields)
                    self._save()
                    return dict(e)
            return None

    def delete(self, entry_id: str):
        with self._lock:
            self.entries = [e for e in self.entries if e.get("id") != entry_id]
            self._save()

    def clear(self):
        with self._lock:
            self.entries = []
            self._save()

    def all(self) -> list:
        with self._lock:
            return list(reversed(self.entries))
