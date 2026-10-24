import asyncio
import hashlib
import hmac
import json
import re
import time
from contextlib import asynccontextmanager
from html import escape
from urllib.parse import parse_qsl

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import db
import notify
from config import ADMIN_IDS, BOT_TOKEN, RUN_BOT, USE_WEBHOOK, WEBAPP_URL

NICK_RE = {
    "telegram": re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$"),
    "instagram": re.compile(r"^[A-Za-z0-9._]{1,30}$"),
}
PLATFORM_NAME = {"telegram": "Telegram", "instagram": "Instagram"}
MAX_INIT_DATA_AGE = 24 * 3600


WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]
bot = None


async def keep_awake():
    """Render bepul serveri 15 daqiqa so'rovsiz qolsa uxlaydi; har 10 daqiqada o'zimizga so'rov yuboramiz."""
    import urllib.request

    while True:
        await asyncio.sleep(600)
        try:
            await asyncio.to_thread(lambda: urllib.request.urlopen(WEBAPP_URL + "/health", timeout=30).read())
        except Exception as e:
            print(f"keep_awake failed: {e}")


@asynccontextmanager
async def lifespan(app):
    global bot
    db.init()
    tasks = []
    if RUN_BOT:
        from bot import create_bot, dp

        bot = create_bot()
        if USE_WEBHOOK:
            await bot.set_webhook(f"{WEBAPP_URL}/webhook", secret_token=WEBHOOK_SECRET, drop_pending_updates=False)
            tasks.append(asyncio.create_task(keep_awake()))
        else:
            await bot.delete_webhook()
            tasks.append(asyncio.create_task(dp.start_polling(bot, handle_signals=False)))
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header("")):
    if not hmac.compare_digest(x_telegram_bot_api_secret_token, WEBHOOK_SECRET):
        raise HTTPException(403)
    from aiogram.types import Update

    from bot import dp

    await dp.feed_update(bot, Update.model_validate(await request.json(), context={"bot": bot}))
    return {"ok": True}


def check_init_data(init_data: str) -> dict:
    """Telegram Mini App initData imzosini tekshiradi (core.telegram.org/bots/webapps)."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(401, "initData noto'g'ri")
    if time.time() - int(pairs.get("auth_date", 0)) > MAX_INIT_DATA_AGE:
        raise HTTPException(401, "initData eskirgan")
    return json.loads(pairs["user"])


def current_user(x_init_data: str = Header(...)) -> dict:
    tg_user = check_init_data(x_init_data)
    user = db.upsert_user(tg_user["id"], tg_user.get("username"), tg_user.get("first_name"))
    user["is_admin"] = user["id"] in ADMIN_IDS
    if user["banned"] and not user["is_admin"]:
        raise HTTPException(403, "Siz bloklangansiz")
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(403, "Faqat admin uchun")
    return user


class NewListing(BaseModel):
    platform: str
    nick: str
    price: int = Field(gt=0, lt=10**12)
    description: str = Field("", max_length=500)


class NewReview(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = Field("", max_length=500)


def money(amount, settings=None):
    settings = settings or db.get_settings()
    return f"{amount:,}".replace(",", " ") + " " + settings["currency"]


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


@app.get("/api/config")
def public_config(user=Depends(current_user)):
    """Mini App uchun admin sozlagan hamma narsa: nomi, matnlar, to'lov usullari, menyu sahifalari."""
    return {
        "settings": db.get_settings(),
        "payment_methods": db.list_items("payment_methods", only_active=True),
        "pages": db.list_items("pages", only_active=True),
    }


@app.get("/api/listings")
def listings(platform: str | None = None, q: str | None = None, user=Depends(current_user)):
    return db.list_listings(status="approved", platform=platform, q=q)


@app.get("/api/my-listings")
def my_listings(user=Depends(current_user)):
    return db.list_listings(seller_id=user["id"])


@app.post("/api/listings")
async def create_listing(body: NewListing, user=Depends(current_user)):
    settings = db.get_settings()
    if not user["username"]:
        raise HTTPException(400, "Sotish uchun Telegram profilingizda username bo'lishi kerak (xaridorlar siz bilan bog'lanishi uchun)")
    nick = body.nick.strip().lstrip("@")
    if body.platform not in NICK_RE or (body.platform == "instagram" and settings["allow_instagram"] != "1"):
        raise HTTPException(400, "Platforma noto'g'ri")
    if not NICK_RE[body.platform].match(nick):
        raise HTTPException(400, f"{PLATFORM_NAME[body.platform]} nik formati noto'g'ri")
    if any(l["status"] in ("pending", "approved") for l in db.list_listings(platform=body.platform, nick=nick)):
        raise HTTPException(400, "Bu nik allaqachon sotuvda yoki tekshiruvda")
    status = "pending" if settings["require_approval"] == "1" else "approved"
    listing_id = db.create_listing(user["id"], body.platform, nick, body.price, body.description.strip(), status)
    await notify.admins(
        f"🆕 Yangi e'lon #{listing_id}\n{PLATFORM_NAME[body.platform]}: <b>@{escape(nick)}</b>\n"
        f"Narx: {money(body.price, settings)}\nSotuvchi: @{escape(user['username'])}"
        + ("\n\nAdmin panelda tasdiqlang." if status == "pending" else "")
    )
    return db.get_listing(listing_id)


def own_listing(listing_id: int, user: dict) -> dict:
    listing = db.get_listing(listing_id)
    if not listing:
        raise HTTPException(404, "E'lon topilmadi")
    if listing["seller_id"] != user["id"] and not user["is_admin"]:
        raise HTTPException(403, "Bu sizning e'loningiz emas")
    return listing


@app.post("/api/listings/{listing_id}/sold")
def mark_sold(listing_id: int, user=Depends(current_user)):
    own_listing(listing_id, user)
    db.set_listing_status(listing_id, "sold")
    return {"ok": True}


@app.delete("/api/listings/{listing_id}")
def remove_listing(listing_id: int, user=Depends(current_user)):
    own_listing(listing_id, user)
    db.delete_listing(listing_id)
    return {"ok": True}


# ---- Sotuvchi profili, baho va izohlar ----

@app.get("/api/sellers/{seller_id}")
def seller_profile(seller_id: int, user=Depends(current_user)):
    seller = db.get_user(seller_id)
    if not seller:
        raise HTTPException(404, "Sotuvchi topilmadi")
    reviews = db.list_reviews(seller_id)
    return {
        "seller": {k: seller[k] for k in ("id", "username", "first_name")},
        "rating": db.seller_rating(seller_id),
        "reviews": reviews,
        "my_review": next((r for r in reviews if r["author_id"] == user["id"]), None),
        "listings": db.list_listings(status="approved", seller_id=seller_id),
        "sold_count": len(db.list_listings(status="sold", seller_id=seller_id)),
    }


@app.post("/api/sellers/{seller_id}/reviews")
async def add_review(seller_id: int, body: NewReview, user=Depends(current_user)):
    if seller_id == user["id"]:
        raise HTTPException(400, "O'zingizga baho qo'ya olmaysiz")
    if not db.get_user(seller_id):
        raise HTTPException(404, "Sotuvchi topilmadi")
    db.upsert_review(seller_id, user["id"], body.rating, body.text.strip())
    author = "@" + user["username"] if user["username"] else escape(user["first_name"] or "Foydalanuvchi")
    await notify.send(seller_id, f"⭐ {author} sizga {'★' * body.rating} baho qo'ydi" + (f":\n{escape(body.text.strip())}" if body.text.strip() else ""))
    return {"ok": True}


# ---- Admin panel ----

@app.get("/api/admin/stats")
def admin_stats(user=Depends(admin_user)):
    return db.stats()


@app.get("/api/admin/listings")
def admin_listings(status: str = "pending", user=Depends(admin_user)):
    return db.list_listings(status=status)


@app.post("/api/admin/listings/{listing_id}/{action}")
async def admin_moderate(listing_id: int, action: str, user=Depends(admin_user)):
    status = {"approve": "approved", "reject": "rejected"}.get(action)
    listing = db.get_listing(listing_id)
    if not status or not listing:
        raise HTTPException(404)
    db.set_listing_status(listing_id, status)
    nick = f"{PLATFORM_NAME[listing['platform']]} @{escape(listing['nick'])}"
    text = f"✅ {nick} e'loningiz tasdiqlandi va sotuvga chiqdi!" if status == "approved" else f"❌ {nick} e'loningiz rad etildi."
    await notify.send(listing["seller_id"], text)
    return {"ok": True}


@app.get("/api/admin/users")
def admin_users(user=Depends(admin_user)):
    return db.list_users()


@app.post("/api/admin/users/{user_id}/{action}")
def admin_ban(user_id: int, action: str, user=Depends(admin_user)):
    if action not in ("ban", "unban"):
        raise HTTPException(404)
    db.set_banned(user_id, action == "ban")
    return {"ok": True}


@app.get("/api/admin/settings")
def admin_settings(user=Depends(admin_user)):
    return db.get_settings()


@app.put("/api/admin/settings")
def admin_update_settings(values: dict[str, str], user=Depends(admin_user)):
    db.update_settings(values)
    return db.get_settings()


@app.get("/api/admin/reviews")
def admin_reviews(user=Depends(admin_user)):
    return db.list_reviews()


@app.delete("/api/admin/reviews/{review_id}")
def admin_delete_review(review_id: int, user=Depends(admin_user)):
    db.delete_review(review_id)
    return {"ok": True}


# To'lov usullari (/api/admin/payment_methods) va menyu sahifalari (/api/admin/pages)
def item_table(table: str) -> str:
    if table not in db.EDITABLE:
        raise HTTPException(404)
    return table


@app.get("/api/admin/{table}")
def admin_items(table: str, user=Depends(admin_user)):
    return db.list_items(item_table(table))


@app.post("/api/admin/{table}")
def admin_create_item(table: str, values: dict, user=Depends(admin_user)):
    return db.create_item(item_table(table), values)


@app.put("/api/admin/{table}/{item_id}")
def admin_update_item(table: str, item_id: int, values: dict, user=Depends(admin_user)):
    return db.update_item(item_table(table), item_id, values)


@app.delete("/api/admin/{table}/{item_id}")
def admin_delete_item(table: str, item_id: int, user=Depends(admin_user)):
    db.delete_item(item_table(table), item_id)
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse("index.html")
