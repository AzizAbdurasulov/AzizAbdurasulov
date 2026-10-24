from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

import db
from config import ADMIN_IDS, BOT_TOKEN, WEBAPP_URL

dp = Dispatcher()


def app_button(text="🛒 Bozorni ochish"):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=WEBAPP_URL))]]
    )


@dp.message(CommandStart())
async def start(message: Message):
    u = message.from_user
    db.upsert_user(u.id, u.username, u.first_name)
    await message.answer(
        f"Salom, {u.first_name}! 👋\n\n"
        "Bu yerda Telegram va Instagram niklarni sotish va sotib olish mumkin.\n"
        "Nikingizni sotuvga qo'yish yoki boshqalarning niklarini ko'rish uchun ilovani oching.",
        reply_markup=app_button(),
    )


@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    s = db.stats()
    await message.answer(
        f"👤 Foydalanuvchilar: {s['users']}\n"
        f"⏳ Tekshiruvda: {s.get('pending', 0)}\n"
        f"✅ Sotuvda: {s.get('approved', 0)}\n"
        f"💰 Sotilgan: {s.get('sold', 0)}",
        reply_markup=app_button("⚙️ Admin panel"),
    )


def create_bot():
    return Bot(BOT_TOKEN)
