"""Local device registry; pairing secrets and bearer tokens are never stored in clear."""
import hashlib
import json
import secrets
import sqlite3
import time
import uuid

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

class DeviceRegistry:
    def __init__(self, home):
        self.path = home / "devices.sqlite3"
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS invitations (
              hash TEXT PRIMARY KEY, name TEXT NOT NULL, scope TEXT NOT NULL, expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS devices (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, scope TEXT NOT NULL,
              hash TEXT UNIQUE NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            """)
            for table in ("invitations", "devices"):
                if "cases" not in {row[1] for row in db.execute(f"PRAGMA table_info({table})")}:
                    # NULL = whole vault; otherwise a JSON list of case identifiers.
                    db.execute(f"ALTER TABLE {table} ADD COLUMN cases TEXT")
            if "pubkey" not in {row[1] for row in db.execute("PRAGMA table_info(devices)")}:
                db.execute("ALTER TABLE devices ADD COLUMN pubkey TEXT")   # device signing key, for the tunnel
            if "expires" not in {row[1] for row in db.execute("PRAGMA table_info(devices)")}:
                db.execute("ALTER TABLE devices ADD COLUMN expires INTEGER")  # NULL = until revoked
    def connect(self):
        return sqlite3.connect(self.path, timeout=10)
    ADMIN_SESSION = 12 * 3600

    def invite(self, name, scope, *, replace_pending=False, cases=None, allow_admin=False):
        """`allow_admin` is for the local launcher only: an admin code opens the workstation panel
        for twelve hours. The HTTP API never passes it."""
        allowed = {"read","write","listen","admin"} if allow_admin else {"read","write","listen"}
        if scope in {"admin", "listen"} and cases is not None:
            raise ValueError("invalid device")
        if scope not in allowed or not name.strip() or len(name)>80:
            raise ValueError("invalid device")
        if cases is not None:
            from .vault import valid_case
            cases = sorted(set(cases))
            if not cases or len(cases) > 200 or not all(c is not None and valid_case(c) for c in cases):
                raise ValueError("invalid device")
            cases = json.dumps(cases)
        code = secrets.token_urlsafe(32)
        expires = int(time.time()) + 300
        with self.connect() as db:
            db.execute("DELETE FROM invitations WHERE expires <= ?", (int(time.time()),))
            if replace_pending:
                db.execute("DELETE FROM invitations WHERE name=? AND scope=?", (name, scope))
            db.execute("INSERT INTO invitations(hash,name,scope,expires,cases) VALUES (?,?,?,?,?)",(digest(code),name,scope,expires,cases))
        return {"code":code,"expires":expires}
    def redeem(self, code, pubkey=None):
        now = int(time.time())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT name,scope,expires,cases FROM invitations WHERE hash=?",(digest(code),)).fetchone()
            if row is None or row[2] <= now:
                raise PermissionError("invalid invitation")
            db.execute("DELETE FROM invitations WHERE hash=?",(digest(code),))
            device_id,token = str(uuid.uuid4()),secrets.token_urlsafe(48)
            expires = now + self.ADMIN_SESSION if row[1] == "admin" else None
            db.execute("INSERT INTO devices(id,name,scope,hash,cases,expires,pubkey) VALUES (?,?,?,?,?,?,?)",(device_id,row[0],row[1],digest(token),row[3],expires,pubkey))
        return {"id":device_id,"token":token,"scope":row[1],"cases":json.loads(row[3]) if row[3] else None}
    def authenticate(self, token):
        if not token or len(token)>256:
            return None
        with self.connect() as db:
            row = db.execute("SELECT id,scope,cases FROM devices WHERE hash=? AND revoked=0 AND (expires IS NULL OR expires > ?)",(digest(token),int(time.time()))).fetchone()
        if row is None:
            return None
        return row[0], row[1], frozenset(json.loads(row[2])) if row[2] else None
    def lookup(self, device_id):
        """A live device by identifier (the tunnel authenticates by key, not by token)."""
        with self.connect() as db:
            row = db.execute(
                "SELECT scope,cases,pubkey,name FROM devices WHERE id=? AND revoked=0 AND (expires IS NULL OR expires > ?)",
                (device_id, int(time.time()))).fetchone()
        if row is None:
            return None
        return {"scope": row[0], "cases": json.loads(row[1]) if row[1] else None, "pubkey": row[2], "name": row[3]}

    def list(self):
        with self.connect() as db:
            db.execute("DELETE FROM devices WHERE expires IS NOT NULL AND expires <= ?", (int(time.time()),))
            rows=db.execute("SELECT id,name,scope,revoked,cases FROM devices WHERE scope != 'admin' ORDER BY id").fetchall()
        return [{"id":i,"name":n,"scope":s,"revoked":bool(r),"cases":json.loads(c) if c else None} for i,n,s,r,c in rows]
    def revoke(self, device_id):
        with self.connect() as db:
            return db.execute("UPDATE devices SET revoked=1 WHERE id=? AND revoked=0",(device_id,)).rowcount == 1
