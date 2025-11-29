"""
main.py — Flask + aiogram (v3) combined app for Replit/Render.
How to use:
 - Set env vars: BOT_TOKEN (optional), ORDER_GROUP_ID (optional, integer like -100123...), WEB_URL (optional)
 - Run: python main.py
 - If BOT_TOKEN not set, only web runs.
"""

import os
import json
import datetime
import threading
import asyncio
from pathlib import Path
from urllib.request import urlretrieve
from flask import Flask, render_template, request, send_from_directory
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ---------- Config / files ----------
BASE = Path(__file__).parent
DATA_FILE = BASE / "orders.json"
PRODUCT_FILE = BASE / "products.json"
TEMPLATES = BASE / "templates"
STATIC = BASE / "static"
IMAGES = STATIC / "images"

# Ensure folders exist
TEMPLATES.mkdir(exist_ok=True)
STATIC.mkdir(exist_ok=True)
IMAGES.mkdir(parents=True, exist_ok=True)

# Env
BOT_TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN") or ""
ORDER_GROUP_ID = None
try:
    gid_raw = os.environ.get("ORDER_GROUP_ID") or os.environ.get("GROUP_ID")
    if gid_raw:
        ORDER_GROUP_ID = int(gid_raw)
except Exception:
    ORDER_GROUP_ID = None

WEB_URL = os.environ.get("WEB_URL") or os.environ.get("WEBAPP_URL") or ""  # optional

# ---------- Create default static/template files if missing ----------
STYLE = STATIC / "style.css"
if not STYLE.exists():
    STYLE.write_text('''
body{font-family:Inter,Arial,Helvetica,sans-serif;background:#fff;color:#111;margin:0;padding:18px}
.container{max-width:1000px;margin:0 auto}
.header{font-size:28px;margin-bottom:14px}
.card{border:1px solid #eee;padding:12px;border-radius:8px;display:inline-block;width:300px;margin:10px;vertical-align:top}
.card img{width:100%;height:160px;object-fit:cover;background:#f6f6f6}
.btn{display:inline-block;padding:8px 12px;border-radius:8px;background:#2b8cff;color:#fff;text-decoration:none}
''', encoding="utf-8")

INDEX_HTML = TEMPLATES / "index.html"
if not INDEX_HTML.exists():
    INDEX_HTML.write_text('''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/static/style.css"><title>Menu</title></head>
<body><div class="container"><div class="header">Altindan - Menu</div>
<div><a href="?lang=uz">uz</a> | <a href="?lang=ru">ru</a></div>
<div style="margin-top:16px">
{% for p in products %}
  <div class="card">
    <img src="{{ url_for('static', filename='images/'+p.image) }}" alt="{{ p.name_ru }}">
    <h3>{{ p['name_'+(lang if lang in ['uz','ru'] else 'ru')] }}</h3>
    <div style="font-weight:bold;margin-top:8px">{{ p.price }} so'm</div>
    <div style="margin-top:8px"><a class="btn" href="{{ web_url }}/order/{{ p.id }}?lang={{ lang }}">Buyurtma</a></div>
  </div>
{% endfor %}
</div></div></body></html>''', encoding="utf-8")

ORDER_HTML = TEMPLATES / "order.html"
if not ORDER_HTML.exists():
    ORDER_HTML.write_text('''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/style.css"></head><body>
<div class="container"><h2>Buyurtma — {{ product['name_ru'] }}</h2>
<form method="post">
<label>Ism: <input name="name" required></label><br><br>
<label>Tel: <input name="phone" required></label><br><br>
<label>Miqdor (kg): <input name="qty" value="1" required></label><br><br>
<label>Izoh:<br><textarea name="note"></textarea></label><br><br>
<input type="hidden" name="lang" value="{{ lang }}">
<button class="btn" type="submit">Yuborish</button>
</form></div></body></html>''', encoding="utf-8")

ORDERED_HTML = TEMPLATES / "ordered.html"
if not ORDERED_HTML.exists():
    ORDERED_HTML.write_text('''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/style.css"></head><body>
<div class="container"><h2>Rahmat!</h2><p>Buyurtmangiz qabul qilindi.</p></div></body></html>''', encoding="utf-8")

# ---------- default products.json ----------
if not PRODUCT_FILE.exists():
    sample = [
        {"id":"p1","name_uz":"Chuchvara 1kg","name_ru":"Чучвара 1кг","price":20000,"image":"p1.jpg"},
        {"id":"p2","name_uz":"Manty 1kg","name_ru":"Манты 1кг","price":25000,"image":"p2.jpg"}
    ]
    PRODUCT_FILE.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")

# ensure placeholder images exist
with PRODUCT_FILE.open("r", encoding="utf-8") as f:
    _prods = json.load(f)
for p in _prods:
    img = p.get("image") or f"{p.get('id')}.jpg"
    t = IMAGES / img
    if not t.exists():
        try:
            urlretrieve(f"https://via.placeholder.com/800x400?text={p.get('id')}", str(t))
        except Exception:
            t.write_text("", encoding="utf-8")

# ---------- Flask app ----------
app = Flask(__name__, template_folder=str(TEMPLATES), static_folder=str(STATIC))

def load_products():
    try:
        with PRODUCT_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

@app.route("/")
def index():
    lang = request.args.get("lang", "ru")
    prods = load_products()
    # if WEB_URL not provided, use request host as fallback
    web_url = WEB_URL if WEB_URL else (request.url_root.rstrip("/"))
    return render_template("index.html", products=prods, lang=lang, web_url=web_url)

@app.route("/order/<product_id>", methods=["GET","POST"])
def order(product_id):
    prods = load_products()
    product = next((x for x in prods if x.get("id")==product_id), None)
    if not product:
        return "Mahsulot topilmadi", 404
    if request.method == "POST":
        name = request.form.get("name","Anonim")
        phone = request.form.get("phone","")
        qty = request.form.get("qty","1")
        note = request.form.get("note","")
        lang = request.form.get("lang","ru")
        order = {
            "product_id": product_id,
            "product_name": product.get(f"name_{lang}", product.get("name_ru")),
            "price": product.get("price", 0),
            "qty": qty,
            "name": name,
            "phone": phone,
            "note": note,
            "time": datetime.datetime.now().isoformat()
        }
        # save
        try:
            if not DATA_FILE.exists():
                DATA_FILE.write_text("[]", encoding="utf-8")
            with DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
        data.append(order)
        with DATA_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # trigger telegram send async if loop exists
        try:
            if 'aioloop' in globals() and globals()['aioloop'] is not None:
                asyncio.run_coroutine_threadsafe(send_order_to_group_async(order), globals()['aioloop'])
        except Exception as e:
            print("Send error:", e)

        return render_template("ordered.html", order=order, lang=lang)
    return render_template("order.html", product=product, lang=request.args.get("lang","ru"))

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(STATIC), filename)

# ---------- Telegram (aiogram v3) ----------
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()

def build_text(o):
    return (f"🆕 Yangi buyurtma\nMahsulot: {o.get('product_name')}\nMiqdor: {o.get('qty')}\nIsm: {o.get('name')}\nTel: {o.get('phone')}\nIzoh: {o.get('note')}\nVaqt: {o.get('time')}")

async def send_order_to_group_async(order):
    if not bot:
        print("Bot not configured.")
        return
    text = build_text(order)
    try:
        if ORDER_GROUP_ID:
            await bot.send_message(ORDER_GROUP_ID, text)
        else:
            print("ORDER_GROUP_ID not set — order saved locally.")
    except Exception as e:
        print("Telegram send error:", e)

# /start handler — sends WebApp button
async def on_start(message: types.Message):
    text = "Добро пожаловать"
    kb = []
    # prefer WEB_URL from env; if empty use web host when user opens — it's fine to provide without url
    web = WEB_URL if WEB_URL else ""
    if web:
        kb.append([types.InlineKeyboardButton(text="Открыть", web_app=types.WebAppInfo(url=f"{web}?lang=ru"))])
    else:
        # fallback: open bot's own hosted web (if accessible) — can't guess, so just send text
        pass
    kb.append([types.InlineKeyboardButton(text="✍️ Оставить отзыв", web_app=types.WebAppInfo(url=f"{web}?lang=ru"))]) if web else None

    if kb:
        markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
        await message.answer(text, reply_markup=markup)
    else:
        await message.answer(text + "\n(Web URL not configured)")

async def on_report(message: types.Message):
    if ORDER_GROUP_ID and message.chat.id != ORDER_GROUP_ID:
        return await message.reply("Ruxsat yo'q.")
    try:
        if DATA_FILE.exists():
            with DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []
    except:
        data = []
    total = len(data)
    kg = 0.0
    total_sum = 0.0
    for d in data:
        try:
            q = float(d.get('qty',0))
            p = float(d.get('price',0))
            kg += q
            total_sum += q*p
        except:
            pass
    await message.reply(f"📊 Oy yakunlari:\nBuyurtma: {total}\nJami kg: {kg}\nJami summa: {int(total_sum)} so'm")

# register handlers if bot configured
if bot:
    dp.message.register(on_start, Command(commands=["start"]))
    dp.message.register(on_report, Command(commands=["report"]))
else:
    print("BOT_TOKEN not set — Telegram bot disabled.")

# ---------- Run Flask in background and aiogram in main loop ----------
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # start Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Flask started in background thread.")

    # if bot not configured, keep running only flask
    if not bot:
        print("No BOT_TOKEN — only web is active. Set BOT_TOKEN and restart to enable bot.")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping.")
        raise SystemExit

    # start aiogram loop in main thread
    aioloop = asyncio.new_event_loop()
    globals()['aioloop'] = aioloop
    asyncio.set_event_loop(aioloop)
    print("Starting aiogram polling...")
    try:
        aioloop.run_until_complete(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        print("Stopped by user.")
    except Exception as e:
        print("Polling error:", e)
    finally:
        try:
            aioloop.run_until_complete(aioloop.shutdown_asyncgens())
            aioloop.close()
        except Exception:
            pass
