"""
SQLite database for multi-tenant business configs.
Stores at ./businesses.db — add a Railway volume at /data and set
DATABASE_PATH=/data/businesses.db to persist across deploys.
"""
import os
import sqlite3
from contextlib import contextmanager

_DB_PATH = os.environ.get("DATABASE_PATH", "./businesses.db")
if os.path.isdir("/data"):
    _DB_PATH = "/data/businesses.db"


@contextmanager
def _conn():
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                phone           TEXT DEFAULT '',
                address         TEXT DEFAULT '',
                hours_mon_fri   TEXT DEFAULT '8:00 AM - 6:00 PM',
                hours_sat       TEXT DEFAULT '9:00 AM - 2:00 PM',
                hours_sun       TEXT DEFAULT 'Closed',
                services        TEXT DEFAULT '',
                insurance       TEXT DEFAULT '',
                owner_email     TEXT NOT NULL,
                assistant_name  TEXT DEFAULT '',
                first_message   TEXT DEFAULT '',
                vapi_assistant_id TEXT DEFAULT '',
                active          INTEGER DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)
    # Seed with Bright Smiles on first run
    with _conn() as c:
        if c.execute("SELECT COUNT(*) FROM businesses").fetchone()[0] == 0:
            c.execute("""
                INSERT INTO businesses (id, name, phone, address, hours_mon_fri, hours_sat, hours_sun,
                    services, insurance, owner_email, assistant_name, first_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "bright-smiles",
                "Bright Smiles Dental",
                "+17035551234",
                "1234 Main St, McLean, VA 22101",
                "8:00 AM - 6:00 PM",
                "9:00 AM - 2:00 PM",
                "Closed",
                "General dentistry (cleanings, fillings, extractions, root canals, crowns), "
                "cosmetic dentistry (whitening, veneers, bonding), orthodontics (braces, Invisalign), "
                "pediatric dentistry, same-day emergency care",
                "Delta Dental, MetLife, Cigna, Aetna, United Concordia, BlueCross BlueShield, CareCredit",
                "naseebullah700000@gmail.com",
                "Nova — Bright Smiles Dental Receptionist",
                "Thank you for calling Bright Smiles Dental, this is Nova! How can I help you today?",
            ))


def get_all() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM businesses ORDER BY created_at DESC")]


def get(business_id: str) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
        return dict(r) if r else None


def upsert(data: dict):
    fields = ["id", "name", "phone", "address", "hours_mon_fri", "hours_sat", "hours_sun",
              "services", "insurance", "owner_email", "assistant_name", "first_message",
              "vapi_assistant_id", "active"]
    placeholders = ", ".join(f":{f}" for f in fields)
    updates = ", ".join(f"{f}=excluded.{f}" for f in fields if f != "id")
    with _conn() as c:
        c.execute(
            f"INSERT INTO businesses ({', '.join(fields)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            {f: data.get(f, "") for f in fields},
        )


def set_vapi_id(business_id: str, vapi_id: str):
    with _conn() as c:
        c.execute("UPDATE businesses SET vapi_assistant_id = ? WHERE id = ?", (vapi_id, business_id))


def delete(business_id: str):
    with _conn() as c:
        c.execute("DELETE FROM businesses WHERE id = ?", (business_id,))
