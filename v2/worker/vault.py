"""Encrypted local document vault.

Key hierarchy: the master key (kept by the OS secret store) wraps one data key
per document. Rotating the master key rewraps the data keys and leaves document
ciphertext untouched. Names are encrypted separately from content, so a listing
never decrypts document bodies. Every read and write lands in a MAC-chained
access log; the log holds identifiers only, never names or content.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAX_BYTES = 20 * 1024 * 1024
SCHEMA = 2
CASE_MAX = 64


class Conflict(Exception):
    pass


def derive(key: bytes, purpose: str) -> bytes:
    return HKDF(hashes.SHA256(), 32, None, f"notarai-v2 {purpose}".encode()).derive(key)


def _seal(cipher: AESGCM, data: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + cipher.encrypt(nonce, data, aad)


def _open(cipher: AESGCM, blob: bytes, aad: bytes) -> bytes:
    return cipher.decrypt(blob[:12], blob[12:], aad)


def _aad(kind: str, doc_id: str, version: int | None = None) -> bytes:
    suffix = "" if version is None else f":{version}"
    return f"notarai-v2:{kind}:{doc_id}{suffix}".encode()


def valid_case(case) -> bool:
    return case is None or (
        isinstance(case, str) and 0 < len(case) <= CASE_MAX
        and all(c.isalnum() or c in "-_." for c in case)
    )


class Vault:
    def __init__(self, home: Path, key: bytes):
        if len(key) != 32:
            raise ValueError("vault key must be 32 bytes")
        self.db = Path(home) / "vault.sqlite3"
        self._set_key(key)
        with self._tx() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA:
                raise ValueError("vault was written by a newer NotarAI")
            if version < SCHEMA:
                self._migrate(db, key)
            # People named in a case (for pseudonymisation), encrypted; added after schema 2 shipped.
            db.execute("CREATE TABLE IF NOT EXISTS case_notes (case_id TEXT PRIMARY KEY, parties BLOB NOT NULL)")
            # The office calendar, one encrypted entry per appointment; added later, like case_notes.
            db.execute("CREATE TABLE IF NOT EXISTS calendar (id TEXT PRIMARY KEY, entry BLOB NOT NULL)")
            # What learning mode has learned (lessons), encrypted like the calendar.
            db.execute("CREATE TABLE IF NOT EXISTS lessons (id TEXT PRIMARY KEY, entry BLOB NOT NULL)")
            # Office messenger between workstations, and deletions other workstations must also apply.
            db.execute("CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, entry BLOB NOT NULL, created INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS tombstones (kind TEXT NOT NULL, id TEXT NOT NULL, ts INTEGER NOT NULL,"
                       " PRIMARY KEY(kind, id))")

    def _set_key(self, key: bytes) -> None:
        self._kek = AESGCM(derive(key, "kek"))
        self._audit_key = derive(key, "audit")
        self._notes = AESGCM(derive(key, "case-notes"))

    def connect(self):
        return sqlite3.connect(self.db, timeout=10, isolation_level=None)

    @contextmanager
    def _tx(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")

    @contextmanager
    def _ro(self):
        with closing(self.connect()) as db:
            yield db

    # ------------------------------------------------------------ schema
    def _migrate(self, db, key: bytes) -> None:
        legacy = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='revisions'"
        ).fetchone()
        if legacy:
            db.execute("ALTER TABLE revisions RENAME TO revisions_v1")
        db.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, dek BLOB NOT NULL, case_id TEXT)")
        db.execute(
            "CREATE TABLE revisions (id TEXT NOT NULL, version INTEGER NOT NULL, payload BLOB NOT NULL,"
            " meta BLOB NOT NULL, size INTEGER NOT NULL, created INTEGER NOT NULL, author TEXT NOT NULL,"
            " PRIMARY KEY(id, version))"
        )
        db.execute(
            "CREATE TABLE audit (seq INTEGER PRIMARY KEY, ts INTEGER NOT NULL, actor TEXT NOT NULL,"
            " action TEXT NOT NULL, doc_id TEXT, version INTEGER, mac BLOB NOT NULL)"
        )
        if legacy:
            old = AESGCM(key)
            rows = db.execute("SELECT id, version, payload FROM revisions_v1 ORDER BY id, version").fetchall()
            for doc_id, version, payload in rows:
                plain = old.decrypt(payload[:12], payload[12:], f"notarai-v2:{doc_id}:{version}".encode())
                size = int.from_bytes(plain[:4], "big")
                name = json.loads(plain[4:4 + size])["name"]
                self._insert(db, doc_id, version, name, plain[4 + size:], "migration", None)
            db.execute("DROP TABLE revisions_v1")
            self._log(db, "migration", "migrate", None, None)
        db.execute(f"PRAGMA user_version = {SCHEMA}")

    # ------------------------------------------------------------ keys
    @staticmethod
    def _dek_aad(doc_id: str, case) -> bytes:
        # The case is part of the key wrapping: moving a document to another case by editing
        # the database makes its key unreadable instead of widening who may see it.
        return _aad("dek", doc_id) + b":" + (case or "").encode()

    def _dek(self, db, doc_id: str, *, create=False, case=None) -> AESGCM:
        row = db.execute("SELECT dek, case_id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if row is None:
            if not create:
                raise KeyError(doc_id)
            dek = os.urandom(32)
            db.execute(
                "INSERT INTO documents VALUES (?,?,?)",
                (doc_id, _seal(self._kek, dek, self._dek_aad(doc_id, case)), case),
            )
            return AESGCM(dek)
        return AESGCM(_open(self._kek, row[0], self._dek_aad(doc_id, row[1])))

    def rotate(self, new_key: bytes) -> None:
        """Rewrap every data key under a new master key; ciphertext stays in place."""
        if len(new_key) != 32:
            raise ValueError("vault key must be 32 bytes")
        new_kek = AESGCM(derive(new_key, "kek"))
        with self._tx() as db:
            for doc_id, wrapped, case in db.execute("SELECT id, dek, case_id FROM documents").fetchall():
                dek = _open(self._kek, wrapped, self._dek_aad(doc_id, case))
                db.execute(
                    "UPDATE documents SET dek=? WHERE id=?",
                    (_seal(new_kek, dek, self._dek_aad(doc_id, case)), doc_id),
                )
            notes = [(case, _open(self._notes, blob, _aad("parties", case)))
                     for case, blob in db.execute("SELECT case_id, parties FROM case_notes").fetchall()]
            entries = [(ident, _open(self._notes, blob, _aad("calendar", ident)))
                       for ident, blob in db.execute("SELECT id, entry FROM calendar").fetchall()]
            lessons = [(ident, _open(self._notes, blob, _aad("lesson", ident)))
                       for ident, blob in db.execute("SELECT id, entry FROM lessons").fetchall()]
            messages = [(ident, _open(self._notes, blob, _aad("message", ident)))
                        for ident, blob in db.execute("SELECT id, entry FROM messages").fetchall()]
            self._verify_audit(db)
            self._set_key(new_key)
            for case, plain in notes:
                db.execute("UPDATE case_notes SET parties=? WHERE case_id=?",
                           (_seal(self._notes, plain, _aad("parties", case)), case))
            for ident, plain in entries:
                db.execute("UPDATE calendar SET entry=? WHERE id=?", (_seal(self._notes, plain, _aad("calendar", ident)), ident))
            for ident, plain in lessons:
                db.execute("UPDATE lessons SET entry=? WHERE id=?", (_seal(self._notes, plain, _aad("lesson", ident)), ident))
            for ident, plain in messages:
                db.execute("UPDATE messages SET entry=? WHERE id=?", (_seal(self._notes, plain, _aad("message", ident)), ident))
            previous = b""
            for row in db.execute("SELECT seq, ts, actor, action, doc_id, version FROM audit ORDER BY seq").fetchall():
                previous = self._mac(previous, row)
                db.execute("UPDATE audit SET mac=? WHERE seq=?", (previous, row[0]))
            self._log(db, "local-admin", "rotate-key", None, None)

    # ------------------------------------------------------------ audit
    def _mac(self, previous: bytes, row) -> bytes:
        body = json.dumps(list(row), separators=(",", ":")).encode()
        return hmac.new(self._audit_key, previous + body, hashlib.sha256).digest()

    def _log(self, db, actor, action, doc_id, version) -> None:
        last = db.execute("SELECT seq, mac FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (last[0] + 1, last[1]) if last else (1, b"")
        row = (seq, time.time_ns(), str(actor)[:80], action, doc_id, version)
        db.execute("INSERT INTO audit VALUES (?,?,?,?,?,?,?)", row + (self._mac(previous, row),))

    def log(self, actor, action, doc_id=None, version=None) -> None:
        with self._tx() as db:
            self._log(db, actor, action, doc_id, version)

    def _verify_audit(self, db) -> int:
        previous, expected = b"", 1
        for row in db.execute("SELECT seq, ts, actor, action, doc_id, version, mac FROM audit ORDER BY seq"):
            if row[0] != expected or not hmac.compare_digest(self._mac(previous, row[:6]), row[6]):
                raise ValueError("access log was altered")
            previous, expected = row[6], expected + 1
        return expected - 1

    def audit(self, limit=200, doc_id=None):
        query = "SELECT seq, ts, actor, action, doc_id, version FROM audit"
        args = []
        if doc_id is not None:
            query, args = query + " WHERE doc_id=?", [str(uuid.UUID(doc_id))]
        with self._ro() as db:
            rows = db.execute(query + " ORDER BY seq DESC LIMIT ?", (*args, max(1, min(int(limit), 1000)))).fetchall()
        keys = ("seq", "ts", "actor", "action", "doc_id", "version")
        return [dict(zip(keys, row)) for row in rows]

    def last_action(self, action: str) -> int | None:
        """Time (ns) of the newest log entry with this action."""
        with self._ro() as db:
            row = db.execute("SELECT MAX(ts) FROM audit WHERE action=?", (action,)).fetchone()
        return row[0]

    # ------------------------------------------------------------ documents
    def _insert(self, db, doc_id, version, name, data, author, case) -> None:
        cipher = self._dek(db, doc_id, create=True, case=case)
        meta = json.dumps({"name": name}, ensure_ascii=False).encode()
        db.execute(
            "INSERT INTO revisions VALUES (?,?,?,?,?,?,?)",
            (
                doc_id, version,
                _seal(cipher, data, _aad("data", doc_id, version)),
                _seal(cipher, meta, _aad("meta", doc_id, version)),
                len(data), time.time_ns(), str(author)[:80],
            ),
        )

    def put(self, doc_id, expected, name, data, *, actor="local-admin", case=None):
        doc_id = str(uuid.UUID(doc_id)) if doc_id else str(uuid.uuid4())
        if (
            not isinstance(expected, int) or isinstance(expected, bool) or expected < 0
            or not isinstance(name, str) or not name or len(name) > 255
            or not isinstance(data, bytes) or len(data) > MAX_BYTES or not valid_case(case)
        ):
            raise ValueError("invalid document")
        with self._tx() as db:
            current = db.execute("SELECT COALESCE(MAX(version),0) FROM revisions WHERE id=?", (doc_id,)).fetchone()[0]
            if current != expected:
                raise Conflict("stale revision")
            if current and case is not None and case != self._case(db, doc_id):
                raise ValueError("a document stays in its case")
            self._insert(db, doc_id, current + 1, name, data, actor, case)
            self._log(db, actor, "write", doc_id, current + 1)
        return doc_id, current + 1

    @staticmethod
    def _case(db, doc_id):
        row = db.execute("SELECT case_id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if row is None:
            raise KeyError(doc_id)
        return row[0]

    def case_of(self, doc_id):
        with self._ro() as db:
            return self._case(db, str(uuid.UUID(doc_id)))

    def get(self, doc_id, version=None, *, actor="local-admin"):
        doc_id = str(uuid.UUID(doc_id))
        with self._tx() as db:
            if version is None:
                row = db.execute(
                    "SELECT version, payload, meta FROM revisions WHERE id=? ORDER BY version DESC LIMIT 1", (doc_id,)
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT version, payload, meta FROM revisions WHERE id=? AND version=?", (doc_id, version)
                ).fetchone()
            if row is None:
                raise KeyError(doc_id)
            version, payload, meta = row
            cipher = self._dek(db, doc_id)
            data = _open(cipher, payload, _aad("data", doc_id, version))
            name = json.loads(_open(cipher, meta, _aad("meta", doc_id, version)))["name"]
            self._log(db, actor, "read", doc_id, version)
        return version, name, data

    def list(self, cases=None):
        with self._ro() as db:
            rows = db.execute(
                "SELECT r.id, MAX(r.version), d.case_id FROM revisions r JOIN documents d ON d.id=r.id GROUP BY r.id"
            ).fetchall()
        return [{"id": i, "version": v} for i, v, case in rows if cases is None or case in cases]

    def versions(self, doc_id):
        doc_id = str(uuid.UUID(doc_id))
        with self._ro() as db:
            rows = db.execute("SELECT version FROM revisions WHERE id=? ORDER BY version DESC", (doc_id,)).fetchall()
        if not rows:
            raise KeyError(doc_id)
        return [version for (version,) in rows]

    def summaries(self, cases=None):
        """Latest revision of each document. Decrypts names only."""
        with self._ro() as db:
            rows = db.execute("""
                SELECT r.id, r.version, r.meta, r.size, r.created, d.case_id
                FROM revisions AS r JOIN documents AS d ON d.id = r.id
                WHERE r.version = (SELECT MAX(version) FROM revisions WHERE id = r.id)
                ORDER BY r.id
            """).fetchall()
            result = []
            for doc_id, version, meta, size, created, case in rows:
                if cases is not None and case not in cases:
                    continue
                name = json.loads(_open(self._dek(db, doc_id), meta, _aad("meta", doc_id, version)))["name"]
                result.append({"id": doc_id, "version": version, "name": name, "size": size,
                               "created": created, "case": case})
        return result

    def set_parties(self, case: str, names):
        """Remember who is named in a case, so every device hides the same people from the model."""
        names = [*dict.fromkeys(" ".join(str(n).split()) for n in names if str(n).strip())][:50]
        if not valid_case(case) or case is None or any(len(n) > 120 for n in names):
            raise ValueError("invalid parties")
        blob = _seal(self._notes, json.dumps(names, ensure_ascii=False).encode(), _aad("parties", case))
        with self._tx() as db:
            db.execute("INSERT INTO case_notes VALUES (?,?) ON CONFLICT(case_id) DO UPDATE SET parties=excluded.parties",
                       (case, blob))
        return names

    def all_parties(self):
        """Names of every case's parties (to cut them out of anything that leaves the computer)."""
        with self._ro() as db:
            cases = [c for (c,) in db.execute("SELECT case_id FROM case_notes").fetchall()]
        names = []
        for case in cases:
            names += self.parties(case)
        return names

    def parties(self, case):
        if case is None:
            return []
        with self._ro() as db:
            row = db.execute("SELECT parties FROM case_notes WHERE case_id=?", (case,)).fetchone()
        return json.loads(_open(self._notes, row[0], _aad("parties", case))) if row else []

    # ------------------------------------------------------------ calendar
    def calendar_put(self, ident: str, entry: dict, *, actor="local-admin") -> None:
        entry = {**entry, "updated": entry.get("updated") or time.time_ns()}
        blob = _seal(self._notes, json.dumps(entry, ensure_ascii=False).encode(), _aad("calendar", ident))
        with self._tx() as db:
            db.execute("INSERT INTO calendar VALUES (?,?) ON CONFLICT(id) DO UPDATE SET entry=excluded.entry", (ident, blob))
            self._log(db, actor, "calendar-put", None, None)

    def calendar_delete(self, ident: str, *, actor="local-admin") -> bool:
        with self._tx() as db:
            gone = db.execute("DELETE FROM calendar WHERE id=?", (ident,)).rowcount
            db.execute("INSERT OR REPLACE INTO tombstones VALUES ('calendar', ?, ?)", (ident, time.time_ns()))
            if gone:
                self._log(db, actor, "calendar-delete", None, None)
        return bool(gone)

    def calendar(self):
        with self._ro() as db:
            rows = db.execute("SELECT id, entry FROM calendar").fetchall()
        return [{"id": ident, **json.loads(_open(self._notes, blob, _aad("calendar", ident)))} for ident, blob in rows]

    # ------------------------------------------------------------ lessons (learning mode)
    def lesson_put(self, ident: str, entry: dict) -> None:
        entry = {**entry, "updated": time.time_ns()}
        blob = _seal(self._notes, json.dumps(entry, ensure_ascii=False).encode(), _aad("lesson", ident))
        with self._tx() as db:
            db.execute("INSERT INTO lessons VALUES (?,?) ON CONFLICT(id) DO UPDATE SET entry=excluded.entry", (ident, blob))

    def lesson_delete(self, ident: str, *, actor="local-admin") -> bool:
        with self._tx() as db:
            gone = db.execute("DELETE FROM lessons WHERE id=?", (ident,)).rowcount
            db.execute("INSERT OR REPLACE INTO tombstones VALUES ('lesson', ?, ?)", (ident, time.time_ns()))
            if gone:
                self._log(db, actor, "lesson-delete", None, None)
        return bool(gone)

    def lessons(self):
        with self._ro() as db:
            rows = db.execute("SELECT id, entry FROM lessons").fetchall()
        return [{"id": ident, **json.loads(_open(self._notes, blob, _aad("lesson", ident)))} for ident, blob in rows]

    # ------------------------------------------------------------ office messenger
    def message_put(self, ident: str, entry: dict) -> None:
        blob = _seal(self._notes, json.dumps(entry, ensure_ascii=False).encode(), _aad("message", ident))
        with self._tx() as db:
            db.execute("INSERT INTO messages VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET entry=excluded.entry",
                       (ident, blob, int(entry.get("created") or time.time_ns())))

    def messages(self, limit: int = 200):
        with self._ro() as db:
            rows = db.execute("SELECT id, entry FROM messages ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": ident, **json.loads(_open(self._notes, blob, _aad("message", ident)))} for ident, blob in rows][::-1]

    # ------------------------------------------------------------ workstation sync
    def revisions_since(self, after_ns: int, limit: int = 200):
        """Revisions written here after a moment, oldest first, without those that came from other stations."""
        with self._ro() as db:
            rows = db.execute(
                "SELECT r.id, r.version, r.created, r.author, d.case_id FROM revisions r JOIN documents d ON d.id = r.id "
                "WHERE r.created > ? AND r.author NOT LIKE 'sync:%' ORDER BY r.created LIMIT ?", (after_ns, limit)).fetchall()
        out = []
        for doc_id, version, created, author, case in rows:
            _, name, data = self.get(doc_id, version, actor="sync")
            out.append({"id": doc_id, "version": version, "created": created, "author": author, "case": case,
                        "name": name, "data": data})
        return out

    def import_revision(self, doc_id: str, version: int, name: str, data: bytes, case, author: str):
        """Another workstation's revision. Same id and version when it follows ours; otherwise (both edited)
        it is kept as a separate document so no one's work is overwritten. Returns ("same"|"new"|"conflict", id)."""
        doc_id = str(uuid.UUID(doc_id))
        with self._tx() as db:
            current = db.execute("SELECT COALESCE(MAX(version),0) FROM revisions WHERE id=?", (doc_id,)).fetchone()[0]
            if current == version - 1 and (current == 0 or self._case(db, doc_id) == case):
                self._insert(db, doc_id, version, name, data, author, case)
                self._log(db, author, "sync-write", doc_id, version)
                return "new", doc_id
        if current >= version:
            _, _, ours = self.get(doc_id, version, actor="sync")
            if ours == data:
                return "same", doc_id               # already here
        # Both stations edited, or a gap: keep their text as a document of its own.
        new_id, _ = self.put(None, 0, f"(konflikt) {name}"[:255], data, actor=author, case=case)
        return "conflict", new_id

    def notes_since(self, after_ns: int):
        """Calendar, lessons and messages changed after a moment, plus deletions."""
        with self._ro() as db:
            tombs = db.execute("SELECT kind, id, ts FROM tombstones WHERE ts > ?", (after_ns,)).fetchall()
        changed = {
            "calendar": [e for e in self.calendar() if e.get("updated", 0) > after_ns],
            "lessons": [e for e in self.lessons() if e.get("updated", 0) > after_ns],
            "messages": [m for m in self.messages(500) if m.get("created", 0) > after_ns],
        }
        return changed, [{"kind": k, "id": i, "ts": t} for k, i, t in tombs]

    def apply_notes(self, changed: dict, tombs: list) -> int:
        applied = 0
        with self._ro() as db:
            dead = {(k, i) for k, i in db.execute("SELECT kind, id FROM tombstones").fetchall()}
        local_calendar = {e["id"]: e for e in self.calendar()}
        for entry in changed.get("calendar", []):
            ident = entry.pop("id")
            if ("calendar", ident) in dead or local_calendar.get(ident, {}).get("updated", 0) >= entry.get("updated", 0):
                continue
            self.calendar_put(ident, entry, actor="sync")
            applied += 1
        local_lessons = {e["id"]: e for e in self.lessons()}
        for entry in changed.get("lessons", []):
            ident = entry.pop("id")
            if ("lesson", ident) in dead or local_lessons.get(ident, {}).get("updated", 0) >= entry.get("updated", 0):
                continue
            blob = _seal(self._notes, json.dumps(entry, ensure_ascii=False).encode(), _aad("lesson", ident))
            with self._tx() as db:
                db.execute("INSERT INTO lessons VALUES (?,?) ON CONFLICT(id) DO UPDATE SET entry=excluded.entry", (ident, blob))
            applied += 1
        known = {m["id"] for m in self.messages(1000)}
        for entry in changed.get("messages", []):
            ident = entry.pop("id")
            if ident not in known:
                self.message_put(ident, entry)
                applied += 1
        for tomb in tombs:
            table = {"calendar": "calendar", "lesson": "lessons"}.get(tomb["kind"])
            if table:
                with self._tx() as db:
                    db.execute(f"DELETE FROM {table} WHERE id=?", (tomb["id"],))
                    db.execute("INSERT OR REPLACE INTO tombstones VALUES (?, ?, ?)", (tomb["kind"], tomb["id"], tomb["ts"]))
                applied += 1
        return applied

    def cases(self):
        with self._ro() as db:
            return [c for (c,) in db.execute(
                "SELECT DISTINCT case_id FROM documents WHERE case_id IS NOT NULL ORDER BY case_id")]

    def verify(self) -> dict:
        """Decrypt every revision and check the access log. Used after a restore."""
        revisions = 0
        with self._ro() as db:
            entries = self._verify_audit(db)
            documents = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            for doc_id, version, payload, meta, size in db.execute(
                "SELECT id, version, payload, meta, size FROM revisions ORDER BY id, version"
            ):
                cipher = self._dek(db, doc_id)
                if len(_open(cipher, payload, _aad("data", doc_id, version))) != size:
                    raise ValueError("revision size mismatch")
                json.loads(_open(cipher, meta, _aad("meta", doc_id, version)))["name"]
                revisions += 1
        return {"documents": documents, "revisions": revisions, "audit_entries": entries}

    def snapshot(self, destination: Path) -> None:
        """Consistent copy of the encrypted database, safe while the worker runs."""
        with closing(self.connect()) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
