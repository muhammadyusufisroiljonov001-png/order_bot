# main.py
# Complete, self-contained Flask + aiogram (v3) bot + minimal templates/static setup.
# What it does:
# - Ensures templates and static folders with minimal files exist (creates placeholders if missing)
# - Serves a mini-web shop (index, order, ordered)
# - Telegram /start shows WebApp in-app button (uses types.WebAppInfo)
# - Web orders saved to orders.json and sent to Telegram group (thread-safe)
# - Uses only stdlib for placeholders (urllib) so no extra pip for that

import os
import json
import datetime
import threading
import asyncio
from pathlib import Path
from urllib.request import urlretrieve
from flask import Flask, render_template, request, redirect
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ---------------- CONFIG ----------------
# Put your secrets in Replit Secrets or environment variables
TOKEN = os.environ.get("BOT_TOKEN", "")
ORDER_GROUP_ID = int(os.environ.get("ORDER_GROUP_ID", "--5036378981"))
WEB_URL = "https://5cfd7f8d-e987-469d-ad6e-f8d23ffe89b2-00-1wtqer7oihe0w.sisko.replit.dev"
REVIEW_URL = os.environ.get("REVIEW_URL", WEB_URL)

DATA_FILE = "orders.json"
PRODUCT_FILE = "products.json"
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
IMAGES_DIR = STATIC_DIR / "images"

# ---------------- Ensure folders & minimal files ----------------
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# default minimal CSS
STYLE = STATIC_DIR / "style.css"
if not STYLE.exists():
    STYLE.write_text('''
body{font-family:Inter,Arial,Helvetica,sans-serif;background:#fff;color:#111;margin:0;padding:20px}
.container{max-width:1100px;margin:0 auto}
.card{border:1px solid #eee;padding:18px;border-radius:8px;display:inline-block;width:300px;margin:10px;vertical-align:top}
.card img{width:100%;height:160px;object-fit:cover;background:#f6f6f6}
.btn{display:inline-block;padding:8px 12px;border-radius:8px;background:#3A7BFF;color:#fff;text-decoration:none}
.header{font-size:34px;margin-bottom:20px}
''', encoding="utf-8")

# minimal templates
INDEX_HTML = TEMPLATES_DIR / "index.html"
if not INDEX_HTML.exists():
    INDEX_HTML.write_text('''
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/static/style.css">
<title>Олтин-Дан</title>
</head>
<body>
<div class="container">
  <div class="header">Олтин-Дан</div>
  <div>
    <a href="?lang=uz">uz O'zbek</a> | <a href="?lang=ru">ru Русский</a>
  </div>
  <div style="margin-top:20px">
    {% for p in products %}
    <div class="card">
      <img src="{{ url_for('static', filename='images/' + p.image) }}" alt="{{ p.name_ru }}">
      <h3>{{ p['name_' + (lang if lang in ['uz','ru'] else 'ru')] }}</h3>
      <div>{{ p.unit }} • Blok: {{ p.block_count }}</div>
      <div style="font-weight:bold;margin-top:10px">{{ p.price }} сум</div>
      <a class="btn" href="{{ web_url }}/order/{{ p.id }}?lang={{ lang }}">Buyurtma</a>
    </div>
    {% endfor %}
  </div>
</div>
</body>
</html>
''', encoding="utf-8")

ORDER_HTML = TEMPLATES_DIR / "order.html"
if not ORDER_HTML.exists():
    ORDER_HTML.write_text('''
<!doctype html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/style.css"></head>
<body>
<div class="container">
  <h2>Buyurtma — {{ product.name_ru }}</h2>
  <form method="post">
    <label>Ism: <input name="name"></label><br><br>
    <label>Tel: <input name="phone"></label><br><br>
    <label>Miqdor (kg): <input name="qty" value="1"></label><br><br>
    <label>Izoh:<br><textarea name="note"></textarea></label><br><br>
    <input type="hidden" name="lang" value="{{ lang }}">
    <button type="submit" class="btn">Buyurtma yuborish</button>
  </form>
</div>
</body>
</html>
''', encoding="utf-8")

ORDERED_HTML = TEMPLATES_DIR / "ordered.html"
if not ORDERED_HTML.exists():
    ORDERED_HTML.write_text('''
<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/style.css"></head>
<body><div class="container"><h2>Rahmat!</h2><p>Buyurtmangiz qabul qilindi.</p></div></body></html>
''', encoding="utf-8")

# ---------------- default products.json if missing ----------------
if not Path(PRODUCT_FILE).exists():
    sample = [
        {"id":"p1","name_uz":"Олтин Дон Пельмени с мясом 1 кг","name_ru":"Олтин Дон Пельмени с мясом 1 кг","price":33000,"block_count":10,"image":"p1.jpg","unit":"1 кг"},
        {"id":"p2","name_uz":"Олтин Дон Пельмени с мясом 0.5 кг","name_ru":"Олтин Дон Пельmени с мясом 0.5 кг","price":18000,"block_count":20,"image":"p2.jpg","unit":"0.5 кг"},
        {"id":"p3","name_uz":"Олтин Дон Пельмени с курицей 1 кг","name_ru":"Олтин Дон Пельмени с курицей 1 кг","price":45000,"block_count":10,"image":"p3.jpg","unit":"1 кг"}
    ]
    Path(PRODUCT_FILE).write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------- ensure placeholder images exist ----------------
# We'll write placeholder images into static/images if the expected files missing
with open(PRODUCT_FILE, "r", encoding="utf-8") as f:
    products = json.load(f)
for p in products:
    imgname = p.get("image") or "placeholder.jpg"
    target = IMAGES_DIR / imgname
    if not target.exists():
        try:
            # use placeholder service
            urlretrieve(f"https://via.placeholder.com/800x400?text={p['id']}", str(target))
        except Exception:
            # fallback: create empty small file
            target.write_text("", encoding="utf-8")

# ------------------ Flask app ------------------
app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR))

def load_products():
    with open(PRODUCT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/")
def index():
    lang = request.args.get("lang", "ru")
    products = load_products()
    return render_template("index.html", products=products, lang=lang, web_url=WEB_URL)

@app.route("/order/<product_id>", methods=["GET","POST"])
def order(product_id):
    products = load_products()
    product = next((x for x in products if x.get("id")==product_id), None)
    if not product:
        return "Mahsulot topilmadi", 404
    if request.method == "POST":
        name = request.form.get("name","Anonim")
        phone = request.form.get("phone","")
        qty = request.form.get("qty","1")
        note = request.form.get("note","")
        lang = request.form.get("lang","ru")
        order = {"product_id":product_id, "product_name":product.get(f"name_{lang}",product.get("name_ru")),
                 "price":product.get("price"), "qty":qty, "name":name, "phone":phone, "note":note,
                 "time":datetime.datetime.now().isoformat()}
        # save
        try:
            if not Path(DATA_FILE).exists():
                Path(DATA_FILE).write_text("[]", encoding="utf-8")
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
        data.append(order)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # send to telegram group (thread-safe)
        try:
            if 'aiogram_loop' in globals() and globals()['aiogram_loop'] is not None:
                asyncio.run_coroutine_threadsafe(send_order_to_group_async(order), globals()['aiogram_loop'])
        except Exception as e:
            print("Send order error:", e)
        return render_template("ordered.html", order=order, lang=lang)
    return render_template("order.html", product=product, lang=request.args.get("lang","ru"))

# ------------------ Telegram bot (aiogram v3) ------------------
bot = Bot(token=TOKEN) if TOKEN else None
dp = Dispatcher()

def build_order_text(order: dict) -> str:
    return (f"🆕 Yangi buyurtma:\nMahsulot: {order.get('product_name')}\nMiqdor: {order.get('qty')}\nIsm: {order.get('name')}\nTel: {order.get('phone')}\nIzoh: {order.get('note')}\nVaqt: {order.get('time')}")

async def send_order_to_group_async(order: dict):
    if not bot:
        print("Bot not configured. Set BOT_TOKEN environment variable.")
        return
    text = build_order_text(order)
    try:
        await bot.send_message(ORDER_GROUP_ID, text)
    except Exception as e:
        print("Telegram send error:", e)

# safe cmd_start that uses WebAppInfo for in-app open
async def cmd_start(message: types.Message):
    text = "Добро пожаловать"
    rows = []
    if WEB_URL:
        rows.append([types.InlineKeyboardButton(text="Открыть", web_app=types.WebAppInfo(url=f"{WEB_URL}?lang=ru"))])
    if REVIEW_URL:
        rows.append([types.InlineKeyboardButton(text="✍️ Оставить отзыв", web_app=types.WebAppInfo(url=REVIEW_URL))])
    if not rows:
        await message.answer(text)
        return
    kb = types.InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(text, reply_markup=kb)

async def cmd_report(message: types.Message):
    if message.chat.id != ORDER_GROUP_ID:
        return await message.reply("Ruxsat yo'q.")
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []
    total = len(data)
    total_kg = 0.0
    total_sum = 0.0
    for d in data:
        try:
            q = float(d.get('qty',0))
            p = float(d.get('price',0))
            total_kg += q
            total_sum += q*p
        except:
            pass
    await message.reply(f"📊 Oy yakunlari:\nJami buyurtma: {total} ta\nJami kg: {total_kg} kg\nJami summa: {int(total_sum)} so'm")

# register handlers only if bot configured
if bot:
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_report, Command("report"))

# ------------------ Run: Flask in background, Aiogram main loop ------------------
def run_flask():
    # use 0.0.0.0 so external Replit proxy can reach it
    app.run(host="0.0.0.0", port=8080)

if __name__ == '__main__':
    # start flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Flask fon thread-da ishga tushirildi.")

    # if bot not configured, we just keep Flask running and exit message
    if not bot:
        print("BOT_TOKEN not set. Telegram bot disabled. Set BOT_TOKEN env var and restart to enable bot.")
        # keep main thread alive while flask runs
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping")
        raise SystemExit

    # create and use a dedicated asyncio loop for aiogram in main thread
    aiogram_loop = asyncio.new_event_loop()
    globals()['aiogram_loop'] = aiogram_loop
    asyncio.set_event_loop(aiogram_loop)

    print("Aiogram: pollingni main thread-da ishga tushurayapmiz...")
    try:
        aiogram_loop.run_until_complete(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi (CTRL+C).")
    except Exception as e:
        print("Aiogram polling error:", e)
    finally:
        try:
            aiogram_loop.run_until_complete(aiogram_loop.shutdown_asyncgens())
            aiogram_loop.close()
        except Exception:
            pass

