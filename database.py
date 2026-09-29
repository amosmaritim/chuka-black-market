"""
Database layer for Chuka Black Market.

Uses plain sqlite3 (no ORM) on purpose — this project has one table
and needs to stay easy to read and deploy anywhere.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "chuka.db"

CATEGORIES = [
    "Electronics",
    "Phones & Accessories",
    "Fashion & Clothing",
    "Furniture & Home",
    "Vehicles & Parts",
    "Tools & Equipment",
    "Farm & Agriculture",
    "Books & Media",
    "Sports & Outdoors",
    "Other",
]

CONDITIONS = [
    "New",
    "Like New",
    "Used - Good",
    "Used - Fair",
    "For Parts",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    quantity      INTEGER NOT NULL DEFAULT 1,
    price         REAL NOT NULL,
    condition     TEXT NOT NULL,
    specs         TEXT,
    photos        TEXT,              -- comma-separated relative paths under static/uploads
    contact_name  TEXT,
    contact_phone TEXT NOT NULL,
    token         TEXT UNIQUE NOT NULL,   -- kept for backward compatibility, no longer used to remove listings
    password_hash TEXT,               -- hash of the removal password the seller sets when posting
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    message       TEXT NOT NULL,
    contact_info  TEXT,              -- optional — phone/email the sender left for a reply
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    # Safe migration for databases created before password-based removal existed —
    # CREATE TABLE IF NOT EXISTS above is a no-op on an existing table, so older
    # deployments need this column added explicitly. Harmless to run every startup.
    try:
        conn.execute("ALTER TABLE listings ADD COLUMN password_hash TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.close()


def create_listing(data: dict) -> int:
    conn = get_db()
    cur = conn.execute(
        """
        INSERT INTO listings
            (name, category, quantity, price, condition, specs,
             photos, contact_name, contact_phone, token, password_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"],
            data["category"],
            data["quantity"],
            data["price"],
            data["condition"],
            data.get("specs", ""),
            data.get("photos", ""),
            data.get("contact_name", ""),
            data["contact_phone"],
            data["token"],
            data["password_hash"],
        ),
    )
    conn.commit()
    listing_id = cur.lastrowid
    conn.close()
    return listing_id


def set_listing_photos(listing_id: int, photos_csv: str):
    conn = get_db()
    conn.execute("UPDATE listings SET photos = ? WHERE id = ?", (photos_csv, listing_id))
    conn.commit()
    conn.close()


def get_listing(listing_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    conn.close()
    return row


def delete_listing(listing_id: int):
    conn = get_db()
    conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()


def search_listings(query: str = "", category: str = ""):
    sql = "SELECT * FROM listings WHERE 1=1"
    params = []

    if query:
        sql += " AND (name LIKE ? OR specs LIKE ? OR category LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])

    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY created_at DESC"

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def create_message(message: str, contact_info: str = "") -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO messages (message, contact_info) VALUES (?, ?)",
        (message, contact_info),
    )
    conn.commit()
    msg_id = cur.lastrowid
    conn.close()
    return msg_id


def get_all_messages():
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()
    conn.close()
    return rows


def delete_message(message_id: int):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
