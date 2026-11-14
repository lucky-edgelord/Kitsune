"""Per-user conversation memory in SQLite."""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Dict, List


class Memory:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS turns (chat TEXT, user TEXT, role TEXT, content TEXT, at REAL)")
        self.db.execute("CREATE INDEX IF NOT EXISTS turns_key ON turns (chat, user, at)")

    def history(self, chat: str, user: str, turns: int) -> List[Dict[str, str]]:
        rows = self.db.execute(
            "SELECT role, content FROM turns WHERE chat=? AND user=? ORDER BY at DESC LIMIT ?",
            (chat, user, turns * 2)).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def add(self, chat: str, user: str, role: str, content: str) -> None:
        self.db.execute("INSERT INTO turns VALUES (?,?,?,?,?)", (chat, user, role, content, time.time()))
        self.db.commit()

    def forget(self, chat: str, user: str) -> int:
        n = self.db.execute("DELETE FROM turns WHERE chat=? AND user=?", (chat, user)).rowcount
        self.db.commit()
        return n
