"""Local device registry; pairing secrets and bearer tokens are never stored in clear."""
import hashlib
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
    def connect(self):
        return sqlite3.connect(self.path, timeout=10)
    def invite(self, name, scope, *, replace_pending=False):
        if scope not in {"read","write"} or not name.strip() or len(name)>80:
            raise ValueError("invalid device")
        code = secrets.token_urlsafe(32)
        expires = int(time.time()) + 300
        with self.connect() as db:
            db.execute("DELETE FROM invitations WHERE expires <= ?", (int(time.time()),))
            if replace_pending:
                db.execute("DELETE FROM invitations WHERE name=? AND scope=?", (name, scope))
            db.execute("INSERT INTO invitations VALUES (?,?,?,?)",(digest(code),name,scope,expires))
        return {"code":code,"expires":expires}
    def redeem(self, code):
        now = int(time.time())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT name,scope,expires FROM invitations WHERE hash=?",(digest(code),)).fetchone()
            if row is None or row[2] <= now:
                raise PermissionError("invalid invitation")
            db.execute("DELETE FROM invitations WHERE hash=?",(digest(code),))
            device_id,token = str(uuid.uuid4()),secrets.token_urlsafe(48)
            db.execute("INSERT INTO devices(id,name,scope,hash) VALUES (?,?,?,?)",(device_id,row[0],row[1],digest(token)))
        return {"id":device_id,"token":token,"scope":row[1]}
    def authenticate(self, token):
        if not token or len(token)>256:
            return None
        with self.connect() as db:
            row = db.execute("SELECT id,scope FROM devices WHERE hash=? AND revoked=0",(digest(token),)).fetchone()
        return row
    def list(self):
        with self.connect() as db:
            rows=db.execute("SELECT id,name,scope,revoked FROM devices ORDER BY id").fetchall()
        return [{"id":i,"name":n,"scope":s,"revoked":bool(r)} for i,n,s,r in rows]
    def revoke(self, device_id):
        with self.connect() as db:
            return db.execute("UPDATE devices SET revoked=1 WHERE id=? AND revoked=0",(device_id,)).rowcount == 1
