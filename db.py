import sqlite3
import threading
import time

from config import DATABASE_URL, DB_PATH

PG = bool(DATABASE_URL)

if PG:
    import psycopg
    from psycopg.rows import dict_row

SERIAL = "BIGSERIAL PRIMARY KEY" if PG else "INTEGER PRIMARY KEY AUTOINCREMENT"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    banned INTEGER NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS listings (
    id {SERIAL},
    seller_id BIGINT NOT NULL REFERENCES users(id),
    platform TEXT NOT NULL CHECK (platform IN ('telegram', 'instagram')),
    nick TEXT NOT NULL,
    price BIGINT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'sold')),
    created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS listings_status ON listings(status, platform);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payment_methods (
    id {SERIAL},
    name TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pages (
    id {SERIAL},
    icon TEXT NOT NULL DEFAULT '📄',
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reviews (
    id {SERIAL},
    seller_id BIGINT NOT NULL REFERENCES users(id),
    author_id BIGINT NOT NULL REFERENCES users(id),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    text TEXT NOT NULL DEFAULT '',
    created_at BIGINT NOT NULL,
    UNIQUE (seller_id, author_id)
);
"""

# Admin paneldagi "Sozlamalar" bo'limi shu kalitlarni o'zgartiradi
DEFAULT_SETTINGS = {
    "app_name": "Nik bozori",
    "welcome_text": "Salom, {name}! 👋\n\nBu yerda Telegram va Instagram niklarni sotish va sotib olish mumkin.\nNikingizni sotuvga qo'yish yoki boshqalarning niklarini ko'rish uchun ilovani oching.",
    "open_button": "🛒 Bozorni ochish",
    "currency": "so'm",
    "support_username": "",
    "require_approval": "1",
    "allow_instagram": "1",
    "sell_note": "E'lon admin tekshirganidan keyin bozorda ko'rinadi.",
}
DEFAULT_PAGES = [
    ("📞", "Aloqa", "Savollar bo'yicha adminga yozing."),
    ("📜", "Qoidalar", "1. Faqat o'zingizga tegishli niklarni soting.\n2. Aldov aniqlansa, akkaunt bloklanadi."),
]

_lock = threading.RLock()
_conn = None


def _connect():
    if PG:
        return psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _run(sql, args=()):
    """SQL ni bajaradi va natija qatorlarini dict ro'yxati sifatida qaytaradi."""
    global _conn
    if PG:
        sql = sql.replace("?", "%s")
    with _lock:
        for attempt in range(2):
            try:
                if _conn is None:
                    _conn = _connect()
                cur = _conn.execute(sql, args)
                return [dict(r) for r in cur.fetchall()] if cur.description else []
            except Exception as e:
                # Postgres ulanishi uzilib qolsa, bir marta qayta ulanamiz
                if PG and attempt == 0 and isinstance(e, psycopg.OperationalError):
                    _conn = None
                    continue
                raise


def query(sql, args=()):
    return _run(sql, args)


def one(sql, args=()):
    rows = _run(sql, args)
    return rows[0] if rows else None


def init():
    for stmt in SCHEMA.split(";"):
        if stmt.strip():
            _run(stmt)
    for key, value in DEFAULT_SETTINGS.items():
        _run("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO NOTHING", (key, value))
    if not one("SELECT id FROM pages LIMIT 1") and one("SELECT value FROM settings WHERE key = 'pages_seeded'") is None:
        for i, (icon, title, content) in enumerate(DEFAULT_PAGES):
            _run("INSERT INTO pages (icon, title, content, sort) VALUES (?, ?, ?, ?)", (icon, title, content, i))
        _run("INSERT INTO settings (key, value) VALUES ('pages_seeded', '1')")


# ---- Foydalanuvchilar ----

def upsert_user(user_id, username, first_name):
    _run(
        """INSERT INTO users (id, username, first_name, created_at) VALUES (?, ?, ?, ?)
           ON CONFLICT (id) DO UPDATE SET username = excluded.username, first_name = excluded.first_name""",
        (user_id, username, first_name, int(time.time())),
    )
    return one("SELECT * FROM users WHERE id = ?", (user_id,))


def get_user(user_id):
    return one("SELECT id, username, first_name, banned, created_at FROM users WHERE id = ?", (user_id,))


def list_users():
    return query(
        """SELECT u.id, u.username, u.first_name, u.banned, u.created_at, COUNT(l.id) AS listings
           FROM users u LEFT JOIN listings l ON l.seller_id = u.id
           GROUP BY u.id, u.username, u.first_name, u.banned, u.created_at
           ORDER BY u.created_at DESC LIMIT 500"""
    )


def set_banned(user_id, banned):
    _run("UPDATE users SET banned = ? WHERE id = ?", (int(banned), user_id))
    if banned:
        _run("UPDATE listings SET status = 'rejected' WHERE seller_id = ? AND status IN ('pending', 'approved')", (user_id,))


# ---- E'lonlar ----

LISTING_SELECT = """
SELECT l.*, u.username AS seller_username, u.first_name AS seller_name,
       r.avg_rating AS seller_rating, COALESCE(r.cnt, 0) AS seller_reviews
FROM listings l
JOIN users u ON u.id = l.seller_id
LEFT JOIN (SELECT seller_id, AVG(rating) AS avg_rating, COUNT(*) AS cnt FROM reviews GROUP BY seller_id) r
    ON r.seller_id = l.seller_id
"""


def list_listings(status=None, platform=None, q=None, seller_id=None, nick=None):
    where, args = [], []
    if status:
        where.append("l.status = ?")
        args.append(status)
    if platform:
        where.append("l.platform = ?")
        args.append(platform)
    if q:
        where.append("LOWER(l.nick) LIKE ?")
        args.append(f"%{q.lstrip('@').lower()}%")
    if nick:
        where.append("LOWER(l.nick) = ?")
        args.append(nick.lower())
    if seller_id:
        where.append("l.seller_id = ?")
        args.append(seller_id)
    sql = LISTING_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY l.id DESC LIMIT 200"
    return query(sql, args)


def get_listing(listing_id):
    return one(LISTING_SELECT + " WHERE l.id = ?", (listing_id,))


def create_listing(seller_id, platform, nick, price, description, status):
    row = one(
        """INSERT INTO listings (seller_id, platform, nick, price, description, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
        (seller_id, platform, nick, price, description, status, int(time.time())),
    )
    return row["id"]


def set_listing_status(listing_id, status):
    _run("UPDATE listings SET status = ? WHERE id = ?", (status, listing_id))


def delete_listing(listing_id):
    _run("DELETE FROM listings WHERE id = ?", (listing_id,))


def stats():
    s = {"users": one("SELECT COUNT(*) AS n FROM users")["n"], "reviews": one("SELECT COUNT(*) AS n FROM reviews")["n"]}
    for row in query("SELECT status, COUNT(*) AS n FROM listings GROUP BY status"):
        s[row["status"]] = row["n"]
    return s


# ---- Sozlamalar ----

def get_settings():
    s = dict(DEFAULT_SETTINGS)
    s.update({r["key"]: r["value"] for r in query("SELECT key, value FROM settings")})
    s.pop("pages_seeded", None)
    return s


def update_settings(values: dict):
    for key, value in values.items():
        if key in DEFAULT_SETTINGS:
            _run(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )


# ---- To'lov usullari va menyu sahifalari (bir xil CRUD) ----

EDITABLE = {
    "payment_methods": ("name", "details", "active", "sort"),
    "pages": ("icon", "title", "content", "active", "sort"),
}


def list_items(table, only_active=False):
    sql = f"SELECT * FROM {table}" + (" WHERE active = 1" if only_active else "") + " ORDER BY sort, id"
    return query(sql)


def create_item(table, values):
    cols = [c for c in EDITABLE[table] if c in values]
    row = one(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) RETURNING id",
        [values[c] for c in cols],
    )
    return one(f"SELECT * FROM {table} WHERE id = ?", (row["id"],))


def update_item(table, item_id, values):
    cols = [c for c in EDITABLE[table] if c in values]
    if cols:
        _run(f"UPDATE {table} SET {', '.join(c + ' = ?' for c in cols)} WHERE id = ?", [values[c] for c in cols] + [item_id])
    return one(f"SELECT * FROM {table} WHERE id = ?", (item_id,))


def delete_item(table, item_id):
    _run(f"DELETE FROM {table} WHERE id = ?", (item_id,))


def get_page(page_id):
    return one("SELECT * FROM pages WHERE id = ? AND active = 1", (page_id,))


# ---- Baho va izohlar ----

REVIEW_SELECT = """
SELECT r.*, a.username AS author_username, a.first_name AS author_name,
       s.username AS seller_username, s.first_name AS seller_name
FROM reviews r JOIN users a ON a.id = r.author_id JOIN users s ON s.id = r.seller_id
"""


def seller_rating(seller_id):
    row = one("SELECT AVG(rating) AS avg, COUNT(*) AS cnt FROM reviews WHERE seller_id = ?", (seller_id,))
    return {"avg": float(row["avg"]) if row["avg"] is not None else None, "count": row["cnt"]}


def list_reviews(seller_id=None):
    if seller_id:
        return query(REVIEW_SELECT + " WHERE r.seller_id = ? ORDER BY r.id DESC LIMIT 100", (seller_id,))
    return query(REVIEW_SELECT + " ORDER BY r.id DESC LIMIT 300")


def upsert_review(seller_id, author_id, rating, text):
    _run(
        """INSERT INTO reviews (seller_id, author_id, rating, text, created_at) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (seller_id, author_id) DO UPDATE
           SET rating = excluded.rating, text = excluded.text, created_at = excluded.created_at""",
        (seller_id, author_id, rating, text, int(time.time())),
    )


def delete_review(review_id):
    _run("DELETE FROM reviews WHERE id = ?", (review_id,))
