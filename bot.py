from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

import db
from config import ADMIN_IDS, BOT_TOKEN, WEBAPP_URL

dp = Dispatcher()


def main_keyboard(settings, button_text=None):
    """Ilovani ochish tugmasi + admin qo'shgan menyu sahifalari (Aloqa, Qoidalar va h.k.)."""
    rows = [[InlineKeyboardButton(text=button_text or settings["open_button"], web_app=WebAppInfo(url=WEBAPP_URL))]]
    pages = db.list_items("pages", only_active=True)
    for i in range(0, len(pages), 2):
        rows.append([
            InlineKeyboardButton(text=f"{p['icon']} {p['title']}", callback_data=f"page:{p['id']}")
            for p in pages[i:i + 2]
        ])
    if settings["support_username"]:
        rows.append([InlineKeyboardButton(text="💬 Yordam", url=f"https://t.me/{settings['support_username'].lstrip('@')}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(CommandStart())
async def start(message: Message):
    u = message.from_user
    db.upsert_user(u.id, u.username, u.first_name)
    settings = db.get_settings()
    await message.answer(
        settings["welcome_text"].replace("{name}", u.first_name or ""),
        reply_markup=main_keyboard(settings),
    )


@dp.callback_query(F.data.startswith("page:"))
async def show_page(callback: CallbackQuery):
    page = db.get_page(int(callback.data.split(":")[1]))
    await callback.answer()
    if page:
        await callback.message.answer(f"{page['icon']} {page['title']}\n\n{page['content']}")


@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    s = db.stats()
    await message.answer(
        f"👤 Foydalanuvchilar: {s['users']}\n"
        f"⏳ Tekshiruvda: {s.get('pending', 0)}\n"
        f"✅ Sotuvda: {s.get('approved', 0)}\n"
        f"💰 Sotilgan: {s.get('sold', 0)}\n"
        f"⭐ Izohlar: {s['reviews']}",
        reply_markup=main_keyboard(db.get_settings(), "⚙️ Admin panel"),
    )


def create_bot():
    return Bot(BOT_TOKEN)
