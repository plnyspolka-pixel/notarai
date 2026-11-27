"""Local ledger of model usage: counts only, never prompts, names or document identifiers."""
import sqlite3
import time
from contextlib import closing
from pathlib import Path

PURPOSES = frozenset({"draft", "chat", "extract", "command", "smoke"})


class UsageLedger:
    def __init__(self, home: Path):
        self.path = Path(home) / "usage.sqlite3"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY, ts INTEGER NOT NULL,"
                " model TEXT NOT NULL, purpose TEXT NOT NULL, input_tokens INTEGER NOT NULL,"
                " output_tokens INTEGER NOT NULL, ok INTEGER NOT NULL)"
            )

    def record(self, model: str, purpose: str, input_tokens: int, output_tokens: int, ok: bool = True) -> None:
        if purpose not in PURPOSES:
            raise ValueError("unknown purpose")
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute(
                "INSERT INTO usage VALUES (NULL,?,?,?,?,?,?)",
                (int(time.time()), model, purpose, max(0, int(input_tokens)), max(0, int(output_tokens)), int(ok)),
            )

    def summary(self, since: int = 0) -> list[dict]:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            rows = db.execute(
                "SELECT model, purpose, COUNT(*), SUM(input_tokens), SUM(output_tokens) FROM usage"
                " WHERE ts >= ? GROUP BY model, purpose ORDER BY model, purpose", (int(since),)
            ).fetchall()
        keys = ("model", "purpose", "calls", "input_tokens", "output_tokens")
        return [dict(zip(keys, row)) for row in rows]
