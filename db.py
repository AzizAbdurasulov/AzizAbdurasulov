import sqlite3
import time

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    banned INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL REFERENCES users(id),
    platform TEXT NOT NULL CHECK (platform IN ('telegram', 'instagram')),
    nick TEXT NOT NULL,
    price INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'sold')),
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS listings_status ON listings(status, platform);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_user(user_id, username, first_name):
    with connect() as conn:
        conn.execute(
            """INSERT INTO users (id, username, first_name, created_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET username = excluded.username, first_name = excluded.first_name""",
            (user_id, username, first_name, int(time.time())),
        )
        return dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


LISTING_SELECT = """
SELECT l.*, u.username AS seller_username, u.first_name AS seller_name
FROM listings l JOIN users u ON u.id = l.seller_id
"""


def list_listings(status=None, platform=None, q=None, seller_id=None):
    where, args = [], []
    if status:
        where.append("l.status = ?")
        args.append(status)
    if platform:
        where.append("l.platform = ?")
        args.append(platform)
    if q:
        where.append("l.nick LIKE ?")
        args.append(f"%{q.lstrip('@')}%")
    if seller_id:
        where.append("l.seller_id = ?")
        args.append(seller_id)
    sql = LISTING_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY l.id DESC LIMIT 200"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def get_listing(listing_id):
    with connect() as conn:
        row = conn.execute(LISTING_SELECT + " WHERE l.id = ?", (listing_id,)).fetchone()
        return dict(row) if row else None


def create_listing(seller_id, platform, nick, price, description):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO listings (seller_id, platform, nick, price, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (seller_id, platform, nick, price, description, int(time.time())),
        )
        return cur.lastrowid


def set_listing_status(listing_id, status):
    with connect() as conn:
        conn.execute("UPDATE listings SET status = ? WHERE id = ?", (status, listing_id))


def delete_listing(listing_id):
    with connect() as conn:
        conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))


def list_users():
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                """SELECT u.*, COUNT(l.id) AS listings FROM users u
                   LEFT JOIN listings l ON l.seller_id = u.id
                   GROUP BY u.id ORDER BY u.created_at DESC LIMIT 500"""
            )
        ]


def set_banned(user_id, banned):
    with connect() as conn:
        conn.execute("UPDATE users SET banned = ? WHERE id = ?", (int(banned), user_id))
        if banned:
            conn.execute("UPDATE listings SET status = 'rejected' WHERE seller_id = ? AND status IN ('pending', 'approved')", (user_id,))


def stats():
    with connect() as conn:
        s = {"users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]}
        for status, n in conn.execute("SELECT status, COUNT(*) FROM listings GROUP BY status"):
            s[status] = n
        return s
