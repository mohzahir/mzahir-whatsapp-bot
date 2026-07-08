from flask import Flask, request, jsonify
import requests
import psycopg2
import os

app = Flask(__name__)

# ==========================================
# 1. الإعدادات والمفاتيح (Tokens)
# ==========================================
VERIFY_TOKEN = 'Zahir_Token_2026'

# ⚠️ ضع هنا مفتاح ميتا ومعرف الهاتف الذي استخرجته من شاشة API Setup
WHATSAPP_TOKEN = 'EAAOpSEHAORABR5XUosAdquyZCAET50zZB2dFWhYf8bgo5xsHzQGshwRwvWc3OXZA5fHk5N7b85OKITT03ZB73no0FNK5bn1wGAnl7zcJxO7ZCu65boWrVGmgYiA3Kz62HUFMMFjbb3AHg1lvo6oSZBerTersTRAbPBLHCn2VzTiWIF6mMwKHmRe3ZBGP9vSB0Ip5QZDZD'
PHONE_NUMBER_ID = '1162606406942576'

# إعدادات تيليجرام للإشعارات للإدارة (لا تقم بتغييرها)
TELEGRAM_BOT_TOKEN = '8627720505:AAHZB7HNeGBP9k8eYJLy-D7mxbsDfOhu-Nc'
ADMIN_ID = 7197788608

# قاعدة البيانات (نفس قاعدة تيليجرام المركزية)
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://neondb_owner:npg_yaTgVL9m4NlA@ep-nameless-butterfly-ada3hsu3-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

# ذاكرة مؤقتة لحفظ مسار العميل في الواتساب
user_states = {}

# ==========================================
# 2. دوال مساعدة (قاعدة البيانات وإرسال الرسائل)
# ==========================================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def get_bot_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT buy_price, sell_price, usdt_balance, sdg_balance, allow_buy, allow_sell, is_busy FROM settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'buy': row[0], 'sell': row[1], 'usdt_balance': row[2], 'sdg_balance': row[3], 'allow_buy': row[4], 'allow_sell': row[5], 'is_busy': row[6]}
    return None

def send_whatsapp_message(to_phone, text):
    """إرسال رسالة للعميل في الواتساب"""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=payload)

def notify_telegram_admin(text):
    """إرسال إشعار للإدارة في تيليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': ADMIN_ID, 'text': text, 'parse_mode': 'Markdown'}
    requests.post(url, json=payload)

# ==========================================
# 3. المنطق الأساسي للردود (WhatsApp Logic)
# ==========================================
def handle_whatsapp_message(sender_phone, msg_text, msg_type):
    global user_states
    
    # تنظيف النص وتجهيزه
    msg_text = str(msg_text).strip() if msg_text else ""
    
    # 1. زر الطوارئ (الإلغاء في أي وقت)
    if msg_text == "0" or msg_text == "إلغاء":
        if sender_phone in user_states:
            del user_states[sender_phone]
        send_whatsapp_message(sender_phone, "🚫 تم إلغاء الطلب الحالي.\nأرسل (مرحبا) للبدء من جديد.")
        return

    state = user_states.get(sender_phone, {}).get('step')

    # 2. القائمة الرئيسية (إذا لم يكن العميل في طلب نشط)
    if not state:
        settings = get_bot_settings()
        if msg_text == "1": # مسار الشراء
            if not settings['allow_buy']:
                send_whatsapp_message(sender_phone, "🔷 خدمة الشراء متوقفة مؤقتاً للتحديثات.")
                return
            user_states[sender_phone] = {'step': 'buy_amount'}
            send_whatsapp_message(sender_phone, f"🟢 *طلب شراء USDT*\nالسيولة المتوفرة: {settings['usdt_balance']} USDT\n\nالرجاء كتابة الكمية التي ترغب في شرائها (رقم فقط):\n\n*(أرسل 0 في أي وقت للإلغاء)*")
        
        elif msg_text == "2": # مسار البيع
            if not settings['allow_sell']:
                send_whatsapp_message(sender_phone, "🔷 خدمة البيع متوقفة مؤقتاً للتحديثات.")
                return
            max_buy = round(settings['sdg_balance'] / settings['buy'], 2) if settings['buy'] > 0 else 0
            user_states[sender_phone] = {'step': 'sell_amount'}
            send_whatsapp_message(sender_phone, f"🔵 *طلب بيع USDT*\nالحد الأقصى المتاح لاستيعابه: {max_buy} USDT\n\nالرجاء كتابة الكمية التي ترغب في بيعها لنا (رقم فقط):\n\n*(أرسل 0 في أي وقت للإلغاء)*")
        
        elif msg_text == "3": # عرض الأسعار
            send_whatsapp_message(sender_phone, f"📊 *أسعار الصرف اليوم:*\nنشتري منك بـ: {settings['buy']} جنيه\nنبيع لك بـ: {settings['sell']} جنيه\n\nأرسل أي رسالة للعودة للقائمة.")
        
        else:
            # رسالة الترحيب الأولى
            status = "🟢 متصل الآن (التنفيذ فوري)" if not settings['is_busy'] else "⏱️ التاجر في وضع الانشغال"
            welcome = (
                f"مرحباً بك في منصة تداول USDT الآمنة 🚀\n"
                f"📡 حالة المنصة: {status}\n\n"
                f"يرجى اختيار الخدمة بإرسال الرقم المناسب:\n\n"
                f"1️⃣ 🟢 شراء USDT\n"
                f"2️⃣ 🔵 بيع USDT\n"
                f"3️⃣ 📊 عرض أسعار الصرف\n"
                f"0️⃣ ❌ إلغاء أي طلب والعودة\n"
            )
            send_whatsapp_message(sender_phone, welcome)

    # 3. استكمال مسار الشراء
    elif state == 'buy_amount':
        try:
            amount = float(msg_text)
            settings = get_bot_settings()
            if amount > settings['usdt_balance']:
                send_whatsapp_message(sender_phone, f"💡 نعتذر، المتاح حالياً {settings['usdt_balance']} USDT.\nاكتب كمية أقل أو مساوية للمتاح:")
                return
            
            total_sdg = amount * settings['sell']
            user_states[sender_phone].update({'amount': amount, 'total_sdg': total_sdg, 'step': 'buy_wallet'})
            send_whatsapp_message(sender_phone, f"أنت تطلب شراء {amount} USDT.\nالمطلوب دفعه: {total_sdg} جنيه.\n\n👇 يرجى إرسال *عنوان محفظتك (TRC20)* أو *معرف باينانس Pay ID* لتستلم عليه:")
        except ValueError:
            send_whatsapp_message(sender_phone, "⚠️ الرجاء إدخال أرقام صحيحة فقط.")

    elif state == 'buy_wallet':
        user_states[sender_phone]['wallet'] = msg_text
        user_states[sender_phone]['step'] = 'buy_receipt'
        order = user_states[sender_phone]
        text = (
            f"🛡️ *خطوة أخيرة لإتمام الطلب*\n\n"
            f"🔹 الكمية: {order['amount']} USDT\n"
            f"🔹 المحفظة: {order['wallet']}\n"
            f"🔹 المبلغ المطلوب: *{order['total_sdg']} جنيه*\n\n"
            f"🏦 *حسابنا البنكي (بنكك):*\n"
            f"• الحساب: `3290549`\n"
            f"• الاسم: محمد زاهر عبدالله علي\n"
            f"• التعليق: إلى محمد زاهر مقابل خدمة الكترونية\n\n"
            f"📸 *الرجاء تحويل المبلغ وإرسال صورة إشعار الدفع هنا (صورة فقط).* \n*(ملاحظة: إذا أرسلت نصاً لن يتم قبوله كإشعار)*"
        )
        send_whatsapp_message(sender_phone, text)

    elif state == 'buy_receipt':
        if msg_type == 'image':
            order = user_states[sender_phone]
            # حفظ في قاعدة البيانات (نفس قاعدة التيليجرام)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO orders (user_id, order_type, amount, total_sdg, wallet_address, status) 
                              VALUES (%s, %s, %s, %s, %s, %s) RETURNING order_id''', 
                           (int(sender_phone), 'BUY', order['amount'], order['total_sdg'], order['wallet'], 'PENDING'))
            order_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            
            send_whatsapp_message(sender_phone, "🕒 *تم استلام الطلب!* جاري مراجعة الإشعار... سيتم تحويل الـ USDT لك قريباً.\n(لا تقم بإرسال رسائل أخرى حتى لا تتأخر مراجعة طلبك).")
            
            # إرسال إشعار للإدارة في تيليجرام
            admin_alert = (
                f"🚨 *طلب شراء جديد من واتساب!* `#{order_id}`\n\n"
                f"📱 رقم العميل: `+{sender_phone}`\n"
                f"يطلب: `{order['amount']}` USDT\n"
                f"يجب أن يدفع: `{order['total_sdg']}` جنيه\n"
                f"المحفظة:\n`{order['wallet']}`\n\n"
                f"⚠️ *العميل أرسل صورة إشعار. افتح (واتساب الأعمال) في هاتفك لتأكيد الإشعار وتحويل الكمية له.*"
            )
            notify_telegram_admin(admin_alert)
            del user_states[sender_phone]
        else:
            send_whatsapp_message(sender_phone, "⚠️ *تنبيه:* الرجاء إرسال **صورة** لإشعار الدفع فقط لإتمام الطلب.")

    # 4. استكمال مسار البيع
    elif state == 'sell_amount':
        try:
            amount = float(msg_text)
            settings = get_bot_settings()
            total_sdg = amount * settings['buy']
            max_buy = round(settings['sdg_balance'] / settings['buy'], 2) if settings['buy'] > 0 else 0
            
            if amount > max_buy:
                send_whatsapp_message(sender_phone, f"💡 السيولة المتاحة حالياً تكفي لشراء {max_buy} USDT كحد أقصى. اكتب كمية أقل:")
                return
            
            user_states[sender_phone].update({'amount': amount, 'total_sdg': total_sdg, 'step': 'sell_bank'})
            send_whatsapp_message(sender_phone, f"أنت تريد بيع {amount} USDT.\nسنقوم بتحويل: {total_sdg} جنيه لك.\n\n👇 يرجى كتابة *رقم حسابك في بنكك + اسمك الكامل* لنحول لك عليه:")
        except ValueError:
            send_whatsapp_message(sender_phone, "⚠️ الرجاء إدخال أرقام صحيحة فقط.")

    elif state == 'sell_bank':
        user_states[sender_phone]['client_bank'] = msg_text
        user_states[sender_phone]['step'] = 'sell_receipt'
        order = user_states[sender_phone]
        text = (
            f"🛡️ *خطوة أخيرة لإتمام الطلب*\n\n"
            f"🔹 الكمية التي ستبيعها: {order['amount']} USDT\n"
            f"🔹 حسابك للاستلام: {order['client_bank']}\n\n"
            f"🔵 *يرجى تحويل الـ USDT إلى أحد الحسابات التالية:*\n"
            f"1️⃣ معرف باينانس (Pay ID): `950533501`\n"
            f"2️⃣ محفظة (TRC20):\n`TR7C9B3914CnDZ9Sii6yMhw5pjNojB51BH`\n\n"
            f"📸 *بمجرد التحويل، أرسل صورة إشعار النجاح هنا (صورة فقط).* \n*(ملاحظة: إذا أرسلت نصاً لن يتم قبوله كإشعار)*"
        )
        send_whatsapp_message(sender_phone, text)

    elif state == 'sell_receipt':
        if msg_type == 'image':
            order = user_states[sender_phone]
            # حفظ في قاعدة البيانات
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO orders (user_id, order_type, amount, total_sdg, wallet_address, status) 
                              VALUES (%s, %s, %s, %s, %s, %s) RETURNING order_id''', 
                           (int(sender_phone), 'SELL', order['amount'], order['total_sdg'], f"بنك العميل: {order['client_bank']}", 'PENDING'))
            order_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            
            send_whatsapp_message(sender_phone, "🕒 *تم استلام الطلب!* جاري مراجعة التحويل... سيتم تحويل الجنيهات لحسابك قريباً.\n(لا تقم بإرسال رسائل أخرى حتى لا تتأخر مراجعة طلبك).")
            
            # إرسال إشعار للإدارة في تيليجرام
            admin_alert = (
                f"🚨 *طلب بيع جديد من واتساب!* `#{order_id}`\n\n"
                f"📱 رقم العميل: `+{sender_phone}`\n"
                f"أرسل لنا: `{order['amount']}` USDT\n"
                f"يجب أن تحول له: *{order['total_sdg']}* جنيه\n"
                f"إلى الحساب:\n`{order['client_bank']}`\n\n"
                f"⚠️ *العميل أرسل صورة التحويل. افتح (واتساب الأعمال) في هاتفك للتأكد وإرسال إشعار البنك إليه.*"
            )
            notify_telegram_admin(admin_alert)
            del user_states[sender_phone]
        else:
            send_whatsapp_message(sender_phone, "⚠️ *تنبيه:* الرجاء إرسال **صورة** لإشعار تحويل الـ USDT فقط.")

# ==========================================
# 4. الخادم المستضيف (Webhook Server)
# ==========================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # التحقق من ميتا (تمام الربط)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return 'Forbidden', 403

    # استقبال الرسائل الجديدة
    if request.method == 'POST':
        body = request.json
        try:
            entry = body.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            
            # التأكد من وجود رسالة وتخطي رسائل تحديث الحالة (مستلمة، مقروءة)
            if 'messages' in value:
                message_data = value['messages'][0]
                sender_phone = message_data['from']
                msg_type = message_data.get('type')
                
                msg_text = ""
                if msg_type == 'text':
                    msg_text = message_data['text']['body']
                
                # توجيه الرسالة لدالة المعالجة الخاصة بنا
                handle_whatsapp_message(sender_phone, msg_text, msg_type)
                
        except Exception as e:
            pass # تجاهل الأخطاء العابرة من تحديثات الواتساب غير النصية

        return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)