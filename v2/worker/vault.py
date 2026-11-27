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

    def _set_key(self, key: bytes) -> None:
        self._kek = AESGCM(derive(key, "kek"))
        self._audit_key = derive(key, "audit")

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
    def _dek(self, db, doc_id: str, *, create=False, case=None) -> AESGCM:
        row = db.execute("SELECT dek FROM documents WHERE id=?", (doc_id,)).fetchone()
        if row is None:
            if not create:
                raise KeyError(doc_id)
            dek = os.urandom(32)
            db.execute(
                "INSERT INTO documents VALUES (?,?,?)",
                (doc_id, _seal(self._kek, dek, _aad("dek", doc_id)), case),
            )
            return AESGCM(dek)
        return AESGCM(_open(self._kek, row[0], _aad("dek", doc_id)))

    def rotate(self, new_key: bytes) -> None:
        """Rewrap every data key under a new master key; ciphertext stays in place."""
        if len(new_key) != 32:
            raise ValueError("vault key must be 32 bytes")
        new_kek = AESGCM(derive(new_key, "kek"))
        with self._tx() as db:
            for doc_id, wrapped in db.execute("SELECT id, dek FROM documents").fetchall():
                dek = _open(self._kek, wrapped, _aad("dek", doc_id))
                db.execute(
                    "UPDATE documents SET dek=? WHERE id=?",
                    (_seal(new_kek, dek, _aad("dek", doc_id)), doc_id),
                )
            self._verify_audit(db)
            self._set_key(new_key)
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
