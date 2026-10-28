import sqlite3
from contextlib import closing

from .domain import canonical, fingerprint


class DraftStore:
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY, request_id TEXT NOT NULL, material_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, channel TEXT NOT NULL, slot TEXT NOT NULL,
                status TEXT NOT NULL, payload TEXT NOT NULL,
                UNIQUE(request_id, material_id))""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ready_slot
                ON drafts(channel, slot) WHERE status='ready'""")

    def occupied(self, channel, slot):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT 1 FROM drafts WHERE channel=? AND slot=? AND status='ready'",
                              (channel, slot)).fetchone() is not None

    def existing(self, request, material_id):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT fingerprint, slot FROM drafts WHERE request_id=? AND material_id=?",
                             (request["request_id"], material_id)).fetchone()
        return row[1] if row and row[0] == fingerprint(request, material_id) else None

    def save(self, request, material_id, slot, status, fail=False):
        digest = fingerprint(request, material_id)
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT id, fingerprint, slot, status FROM drafts WHERE request_id=? AND material_id=?",
                             (request["request_id"], material_id)).fetchone()
            if old:
                if old[1] != digest:
                    return {"ok": False, "error": "idempotency_key_reused_with_different_input"}
                return {"ok": True, "draft_id": old[0], "slot": old[2], "status": old[3], "duplicate": True}
            if fail:
                return {"ok": False, "error": "save_failed", "retryable": False}
            try:
                cursor = db.execute("""INSERT INTO drafts
                    (request_id, material_id, fingerprint, channel, slot, status, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (request["request_id"], material_id, digest, request["channel"], slot, status, canonical(request)))
            except sqlite3.IntegrityError:
                return {"ok": False, "error": "slot_conflict", "retryable": True}
            return {"ok": True, "draft_id": cursor.lastrowid, "slot": slot, "status": status, "duplicate": False}
