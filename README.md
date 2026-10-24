# Nik bozori: Telegram bot + Mini App

Foydalanuvchilar Telegram va Instagram niklarini sotuvga qo'yadi, boshqalar ularni Mini App ichida ko'rib, sotuvchiga to'g'ridan-to'g'ri yozadi. Har bir e'lonni admin tasdiqlaydi.

## Fayllar

- `server.py` — FastAPI: API + Mini App sahifasi. Bot ham shu jarayon ichida ishga tushadi.
- `bot.py` — aiogram 3 bot: `/start` (bozorni ochish tugmasi), `/admin` (statistika + admin panel tugmasi).
- `db.py` — SQLite ma'lumotlar bazasi (foydalanuvchilar, e'lonlar).
- `notify.py` — adminlarga yangi e'lon haqida, sotuvchiga tasdiq/rad haqida xabar yuborish.
- `index.html` — Mini App: Bozor, Sotish, E'lonlarim, Admin bo'limlari.

## Imkoniyatlar

- **Bozor:** e'lonlarni qidirish, Telegram/Instagram bo'yicha filtr, "Sotuvchiga yozish" tugmasi.
- **Sotish:** platforma, nik, narx (so'm) va izoh. Nik formati tekshiriladi, bir nikni ikki marta qo'yib bo'lmaydi.
  Sotuvchining Telegram profilida username bo'lishi shart (xaridor bog'lanishi uchun).
- **E'lonlarim:** holat (tekshiruvda / sotuvda / rad etilgan / sotilgan), "Sotildi" va "O'chirish".
- **Admin panel** (faqat `ADMIN_IDS` dagilar uchun ko'rinadi): statistika, e'lonlarni tasdiqlash/rad etish/o'chirish,
  foydalanuvchilarni bloklash (bloklanganda uning faol e'lonlari olib tashlanadi).
- Xavfsizlik: har bir so'rovda Telegram `initData` imzosi tekshiriladi, ya'ni boshqa odam nomidan so'rov yuborib bo'lmaydi.

## Ishga tushirish

1. @BotFather'da bot yarating, tokenni oling.
2. `.env.example` ni `.env` ga nusxalang, `BOT_TOKEN` va `ADMIN_IDS` (o'z Telegram ID'ingiz, @userinfobot dan) ni yozing.
3. `pip install -r requirements.txt`
4. `uvicorn server:app --port 8000` — bu bitta buyruq ham botni, ham Mini App'ni yoqadi.
5. Mini App uchun HTTPS manzil kerak. Sinov uchun: `ngrok http 8000`, chiqqan `https://...` manzilni
   `.env` dagi `WEBAPP_URL` ga yozing va serverni qayta yoqing.
6. Telegramda botga `/start` yozing.

## Serverga qo'yish (Railway)

1. Kodni GitHub repoga joylang.
2. railway.app da GitHub orqali kiring, **New Project → Deploy from GitHub repo** bosib, repoingizni tanlang. `Dockerfile` avtomatik topiladi.
3. **Variables** bo'limiga `BOT_TOKEN` va `ADMIN_IDS` ni qo'shing.
4. **Settings → Networking → Generate Domain** bosing. `WEBAPP_URL` shu domendan avtomatik olinadi.
5. Ma'lumotlar o'chib ketmasligi uchun **Volume** qo'shing, mount path: `/data`.
6. Telegramda botga `/start` yozing.
