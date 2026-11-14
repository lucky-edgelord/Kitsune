"""Per-user, per-channel conversation history in SQLite."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import List

from ..providers.llm import ChatMessage


class ConversationStore:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS turns (chat TEXT NOT NULL, user TEXT NOT NULL, "
                "role TEXT NOT NULL, content TEXT NOT NULL, at REAL NOT NULL)"
            )
            self._db.execute("CREATE INDEX IF NOT EXISTS turns_by_user ON turns (chat, user, at)")
            self._db.commit()

    def history(self, chat: str, user: str, turns: int) -> List[ChatMessage]:
        """The last ``turns`` exchanges (user + assistant), oldest first."""
        with self._lock:
            rows = self._db.execute(
                "SELECT role, content FROM turns WHERE chat=? AND user=? ORDER BY at DESC, rowid DESC LIMIT ?",
                (chat, user, turns * 2),
            ).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def append(self, chat: str, user: str, *messages: ChatMessage) -> None:
        now = time.time()
        with self._lock:
            self._db.executemany(
                "INSERT INTO turns VALUES (?,?,?,?,?)", [(chat, user, m["role"], m["content"], now) for m in messages]
            )
            self._db.commit()

    def forget(self, chat: str, user: str) -> int:
        with self._lock:
            n = self._db.execute("DELETE FROM turns WHERE chat=? AND user=?", (chat, user)).rowcount
            self._db.commit()
        return n

    def close(self) -> None:
        with self._lock:
            self._db.close()
