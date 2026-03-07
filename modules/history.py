"""
Search history manager - persists past searches to a JSON file.
"""

import json
import os
import uuid
from datetime import datetime


class HistoryManager:
    def __init__(self, path: str):
        self.path    = path
        self.entries: list = []
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
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.entries, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, data: dict) -> dict:
        """Add a new history entry. Returns the entry with auto-generated id and date."""
        entry = {
            "id":   str(uuid.uuid4()),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            **data,
        }
        self.entries.append(entry)
        self._save()
        return entry

    def get(self, entry_id: str) -> dict | None:
        for e in self.entries:
            if e.get("id") == entry_id:
                return e
        return None

    def delete(self, entry_id: str):
        self.entries = [e for e in self.entries if e.get("id") != entry_id]
        self._save()

    def clear(self):
        self.entries = []
        self._save()

    def all(self) -> list:
        return list(reversed(self.entries))
