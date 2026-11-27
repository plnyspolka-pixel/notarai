import json
import os
import sqlite3
import uuid
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_BYTES = 20 * 1024 * 1024

class Conflict(Exception):
    pass

class Vault:
    def __init__(self, home: Path, key: bytes):
        self.db = home / "vault.sqlite3"
        self.cipher = AESGCM(key)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS revisions (id TEXT, version INTEGER, payload BLOB NOT NULL, PRIMARY KEY(id, version))")

    def connect(self):
        return sqlite3.connect(self.db, timeout=10)

    @staticmethod
    def aad(doc_id, version):
        return f"notarai-v2:{doc_id}:{version}".encode()

    def put(self, doc_id, expected, name, data):
        doc_id = str(uuid.UUID(doc_id)) if doc_id else str(uuid.uuid4())
        if not isinstance(expected, int) or expected < 0 or not name or len(name) > 255 or len(data) > MAX_BYTES:
            raise ValueError("invalid document")
        metadata = json.dumps({"name": name}, ensure_ascii=False).encode()
        plaintext = len(metadata).to_bytes(4, "big") + metadata + data
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT COALESCE(MAX(version),0) FROM revisions WHERE id=?", (doc_id,)).fetchone()[0]
            if current != expected:
                raise Conflict("stale revision")
            version = current + 1
            nonce = os.urandom(12)
            payload = nonce + self.cipher.encrypt(nonce, plaintext, self.aad(doc_id, version))
            db.execute("INSERT INTO revisions VALUES (?,?,?)", (doc_id, version, payload))
        return doc_id, version

    def get(self, doc_id, version=None):
        doc_id = str(uuid.UUID(doc_id))
        with self.connect() as db:
            if version is None:
                row = db.execute("SELECT version,payload FROM revisions WHERE id=? ORDER BY version DESC LIMIT 1", (doc_id,)).fetchone()
            else:
                row = db.execute("SELECT version,payload FROM revisions WHERE id=? AND version=?", (doc_id,version)).fetchone()
        if row is None:
            raise KeyError(doc_id)
        version, payload = row
        name, data = self.unpack(doc_id, version, payload)
        return version, name, data

    def unpack(self, doc_id, version, payload):
        plain = self.cipher.decrypt(payload[:12], payload[12:], self.aad(doc_id,version))
        size = int.from_bytes(plain[:4], "big")
        return json.loads(plain[4:4+size])["name"], plain[4+size:]

    def list(self):
        with self.connect() as db:
            rows = db.execute("SELECT id, MAX(version) FROM revisions GROUP BY id").fetchall()
        return [{"id": i, "version": v} for i, v in rows]

    def versions(self, doc_id):
        doc_id = str(uuid.UUID(doc_id))
        with self.connect() as db:
            rows = db.execute(
                "SELECT version FROM revisions WHERE id=? ORDER BY version DESC",
                (doc_id,),
            ).fetchall()
        if not rows:
            raise KeyError(doc_id)
        return [version for (version,) in rows]

    def summaries(self):
        with self.connect() as db:
            rows = db.execute("""
                SELECT id, version, payload FROM revisions AS r
                WHERE version = (SELECT MAX(version) FROM revisions WHERE id=r.id)
                ORDER BY id
            """)
            summaries = []
            for doc_id, version, payload in rows:
                name, _ = self.unpack(doc_id, version, payload)
                summaries.append({"id": doc_id, "version": version, "name": name})
        return summaries
