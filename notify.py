import asyncio
import json
import urllib.request

from config import ADMIN_IDS, BOT_TOKEN


def _send(chat_id, text):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:  # xabar yetmasa ham API ishlashda davom etadi
        print(f"notify {chat_id} failed: {e}")


async def send(chat_id, text):
    await asyncio.to_thread(_send, chat_id, text)


async def admins(text):
    for admin_id in ADMIN_IDS:
        await send(admin_id, text)
