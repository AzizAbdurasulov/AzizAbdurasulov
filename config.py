import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")
# Render yoki Railway manzil bersa, WEBAPP_URL ni qo'lda yozish shart emas
if not WEBAPP_URL and os.environ.get("RENDER_EXTERNAL_URL"):
    WEBAPP_URL = os.environ["RENDER_EXTERNAL_URL"]
if not WEBAPP_URL and os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    WEBAPP_URL = "https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"]
# Render bepul serveri uxlab qoladi, shuning uchun u yerda polling o'rniga webhook ishlatamiz
USE_WEBHOOK = bool(os.environ.get("RENDER_EXTERNAL_URL")) or os.environ.get("USE_WEBHOOK") == "1"
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
DB_PATH = os.environ.get("DB_PATH", "market.db")
RUN_BOT = os.environ.get("RUN_BOT", "1") == "1"
