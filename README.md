# Nik bozori: Telegram bot + Mini App

Foydalanuvchilar Telegram va Instagram niklarini sotuvga qo'yadi, boshqalar ularni Mini App ichida ko'rib, sotuvchiga to'g'ridan-to'g'ri yozadi. Har bir e'lonni admin tasdiqlaydi.

## Fayllar

- `server.py` — FastAPI: API + Mini App sahifasi. Bot ham shu jarayon ichida ishga tushadi.
- `bot.py` — aiogram 3 bot: `/start` (bozorni ochish tugmasi), `/admin` (statistika + admin panel tugmasi).
- `db.py` — ma'lumotlar bazasi: foydalanuvchilar, e'lonlar, sozlamalar, to'lov usullari, menyu sahifalari, izohlar.
  `DATABASE_URL` berilsa Postgres (masalan Neon), aks holda SQLite fayl.
- `notify.py` — adminlarga yangi e'lon haqida, sotuvchiga tasdiq/rad haqida xabar yuborish.
- `index.html` — Mini App: Bozor, Sotish, E'lonlarim, Menyu, Admin bo'limlari.

## Imkoniyatlar

- **Bozor:** e'lonlarni qidirish, Telegram/Instagram bo'yicha filtr, "Sotuvchiga yozish" tugmasi.
- **Sotish:** platforma, nik, narx (so'm) va izoh. Nik formati tekshiriladi, bir nikni ikki marta qo'yib bo'lmaydi.
  Sotuvchining Telegram profilida username bo'lishi shart (xaridor bog'lanishi uchun).
- **E'lonlarim:** holat (tekshiruvda / sotuvda / rad etilgan / sotilgan), "Sotildi" va "O'chirish".
- **Admin panel** (faqat `ADMIN_IDS` dagilar uchun ko'rinadi): statistika, e'lonlarni tasdiqlash/rad etish/o'chirish,
  foydalanuvchilarni bloklash (bloklanganda uning faol e'lonlari olib tashlanadi).
- **Menyu:** admin qo'shgan sahifalar (Aloqa, Qoidalar va h.k.), to'lov usullari, admin bilan bog'lanish tugmasi.
  Shu sahifalar botdagi `/start` xabarida ham tugma bo'lib chiqadi.
- **Baho va izohlar:** har bir xaridor sotuvchiga 1–5 yulduz va izoh qoldiradi; reyting e'lonlarda ko'rinadi.
- **Admin sozlamalari:** bozor nomi, botdagi salomlashish matni va tugma nomi, valyuta, yordam username'i,
  e'lonlarni tasdiqlash kerakmi, Instagram'ga ruxsat. To'lov usullari va menyu sahifalarini qo'shish, tahrirlash, yashirish, o'chirish.
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

## Serverga qo'yish (Render, bepul)

1. render.com da GitHub orqali kiring.
2. **New + → Web Service** ni bosing va `nik-bozori` reposini tanlang. Language: **Docker**, Instance Type: **Free**.
3. **Environment Variables** bo'limiga `BOT_TOKEN` va `ADMIN_IDS` ni qo'shing.
4. **Deploy Web Service** ni bosing. Sayt manzili va webhook avtomatik sozlanadi.

Eslatma: Render bepul rejasida doimiy disk yo'q, shuning uchun qayta deploy qilinganda e'lonlar bazasi tozalanadi.

### Doimiy baza (Neon, bepul)

Render bepul rejasida fayl saqlanmaydi, shuning uchun sozlamalar va e'lonlar uchun Postgres kerak:

1. neon.tech da ro'yxatdan o'ting va loyiha yarating (regionni Render servisingiz regioniga yaqin tanlang).
2. **Connection string** (`postgresql://...`) ni nusxalang.
3. Render → servisingiz → **Environment** → `DATABASE_URL` qo'shing va saqlang. Jadvallar avtomatik yaratiladi.
