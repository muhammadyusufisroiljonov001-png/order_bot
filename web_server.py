from flask import Flask, send_from_directory, request, jsonify
import json, os, datetime, uuid

app = Flask(__name__, static_folder='web')

ORDERS_FILE = "orders.json"

@app.route('/')
def index():
    return send_from_directory('web', 'index.html')

@app.route('/<path:p>')
def static_proxy(p):
    return send_from_directory('web', p)

# optional API fallback for non-telegram testing
@app.route('/api/order', methods=['POST'])
def api_order():
    data = request.get_json()
    try:
        order = {
            "id": str(uuid.uuid4()),
            "product": data.get("product"),
            "qty": data.get("qty"),
            "address": data.get("address"),
            "timestamp": data.get("time") or datetime.datetime.utcnow().isoformat(),
            "lang": data.get("lang", "uz"),
            "fromWebApp": data.get("fromWebApp", False)
        }
        # ensure orders file exists
        if not os.path.exists(ORDERS_FILE):
            with open(ORDERS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        # append
        with open(ORDERS_FILE, "r+", encoding="utf-8") as f:
            arr = json.load(f)
            arr.append(order)
            f.seek(0); f.truncate()
            json.dump(arr, f, ensure_ascii=False, indent=2)
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","err":str(e)}),500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
