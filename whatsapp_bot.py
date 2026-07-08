from flask import Flask, request
import os

app = Flask(__name__)

# كلمة السر التي ستكتبها في شاشة ميتا
VERIFY_TOKEN = 'Zahir_Token_2026'

@app.route('/')
def home():
    return "WhatsApp Bot Server is Running!"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. هذا الجزء مخصص للنجاح في اختبار الربط من شاشة ميتا
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("✅ Meta Webhook Verified Successfully!")
            return challenge, 200
        else:
            return 'Forbidden', 403

    # 2. هذا الجزء مخصص لاستقبال رسائل العملاء لاحقاً
    if request.method == 'POST':
        body = request.json
        print("📥 Received data from WhatsApp:", body)
        return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)