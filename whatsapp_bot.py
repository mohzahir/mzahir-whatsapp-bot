from flask import Flask, request, jsonify
import requests
import psycopg2
import os

app = Flask(__name__)

# ==========================================
# الإعدادات والمفاتيح
# ==========================================
VERIFY_TOKEN = 'Zahir_Token_2026'
WHATSAPP_TOKEN = 'EAAOpSEHAORABR5XUosAdquyZCAET50zZB2dFWhYf8bgo5xsHzQGshwRwvWc3OXZA5fHk5N7b85OKITT03ZB73no0FNK5bn1wGAnl7zcJxO7ZCu65boWrVGmgYiA3Kz62HUFMMFjbb3AHg1lvo6oSZBerTersTRAbPBLHCn2VzTiWIF6mMwKHmRe3ZBGP9vSB0Ip5QZDZD'
PHONE_NUMBER_ID = '1162606406942576'
TELEGRAM_BOT_TOKEN = '8627720505:AAHZB7HNeGBP9k8eYJLy-D7mxbsDfOhu-Nc'
ADMIN_ID = 7197788608
CHANNEL_USERNAME = "@MZahir_P2P"
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://neondb_owner:npg_yaTgVL9m4NlA@ep-nameless-butterfly-ada3hsu3-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

# التذييل الدائم لكل رسائل الواتساب
FOOTER = "\n\nــــــــــــــــــــــــــــــــــــــــ\n0️⃣ ❌ لإلغاء الطلب والعودة للقائمة\n🎧 للدعم الفني المباشر: wa.me/249117017444"

user_states = {}

# ==========================================
# دوال المساعدة
# ==========================================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def get_bot_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT buy_price, sell_price, usdt_balance, sdg_balance, allow_buy, allow_sell, is_busy FROM settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    if row: return {'buy': row[0], 'sell': row[1], 'usdt_balance': row[2], 'sdg_balance': row[3], 'allow_buy': row[4], 'allow_sell': row[5], 'is_busy': row[6]}
    return None

def is_user_registered(phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT full_name, bank_account FROM users WHERE user_id = %s', (int(phone),))
    result = cursor.fetchone()
    conn.close()
    return result

def send_whatsapp_message(to_phone, text):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_phone, "type": "text", "text": {"body": text}}
    requests.post(url, headers=headers, json=payload)

def notify_telegram_admin(text, send_to_channel=False):
    target = CHANNEL_USERNAME if send_to_channel else ADMIN_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': target, 'text': text, 'parse_mode': 'HTML' if send_to_channel else 'Markdown'}
    requests.post(url, json=payload)

# ==========================================
# المنطق الأساسي للردود (WhatsApp Logic)
# ==========================================
def handle_whatsapp_message(sender_phone, msg_text, msg_type):
    global user_states
    msg_text = str(msg_text).strip() if msg_text else ""
    
    # --- الإلغاء والعودة للقائمة ---
    if msg_text == "0":
        if sender_phone in user_states: del user_states[sender_phone]
        send_whatsapp_message(sender_phone, "🚫 تم إلغاء الطلب بأمان.\nأرسل (مرحبا) للبدء من جديد أو لعرض القائمة." + FOOTER)
        return

    state = user_states.get(sender_phone, {}).get('step')
    settings = get_bot_settings()

    # --- القائمة الرئيسية ---
    if not state:
        # نظام التقييم السريع: إذا أرسل رقم من 1 إلى 5 وليس في طلب، نعتبره تقييم لطلبه الأخير
        if msg_text in ["1", "2", "3", "4", "5"]:
            user_states[sender_phone] = {'step': 'write_review', 'stars': int(msg_text)}
            send_whatsapp_message(sender_phone, "✍️ شكراً لتقييمك! يرجى كتابة تعليق قصير عن خدمتنا لتشجيع الآخرين:" + FOOTER)
            return

        if msg_text == "1": # شراء
            if not settings['allow_buy']: return send_whatsapp_message(sender_phone, "🔷 خدمة الشراء متوقفة مؤقتاً." + FOOTER)
            if not is_user_registered(sender_phone):
                user_states[sender_phone] = {'step': 'auth_name', 'next_action': 'buy'}
                send_whatsapp_message(sender_phone, "🛡️ مرحباً بك. لضمان أمان المعاملات، يرجى ملء بيانات التحقق لمرة واحدة فقط.\n\n👤 الرجاء كتابة *اسمك الكامل* (كما يظهر في تطبيق بنكك):" + FOOTER)
                return
            user_states[sender_phone] = {'step': 'buy_amount'}
            send_whatsapp_message(sender_phone, f"🟢 *طلب شراء USDT*\nالسيولة المتوفرة: {settings['usdt_balance']} USDT\n\nالرجاء كتابة الكمية التي ترغب في شرائها (رقم فقط):" + FOOTER)
            
        elif msg_text == "2": # بيع
            if not settings['allow_sell']: return send_whatsapp_message(sender_phone, "🔷 خدمة البيع متوقفة مؤقتاً." + FOOTER)
            if not is_user_registered(sender_phone):
                user_states[sender_phone] = {'step': 'auth_name', 'next_action': 'sell'}
                send_whatsapp_message(sender_phone, "🛡️ مرحباً بك. لضمان أمان المعاملات، يرجى ملء بيانات التحقق لمرة واحدة فقط.\n\n👤 الرجاء كتابة *اسمك الكامل* (كما يظهر في تطبيق بنكك):" + FOOTER)
                return
            max_buy = round(settings['sdg_balance'] / settings['buy'], 2) if settings['buy'] > 0 else 0
            user_states[sender_phone] = {'step': 'sell_amount'}
            send_whatsapp_message(sender_phone, f"🔵 *طلب بيع USDT*\nالحد الأقصى لاستيعابنا: {max_buy} USDT\n\nالرجاء كتابة الكمية التي ترغب في بيعها لنا (رقم فقط):" + FOOTER)
            
        elif msg_text == "3": # تفاوض
            if not is_user_registered(sender_phone):
                user_states[sender_phone] = {'step': 'auth_name', 'next_action': 'neg'}
                send_whatsapp_message(sender_phone, "🛡️ مرحباً بك في قسم التفاوض. يرجى ملء بيانات التحقق لمرة واحدة.\n\n👤 الرجاء كتابة *اسمك الكامل* (كما يظهر في تطبيق بنكك):" + FOOTER)
                return
            user_states[sender_phone] = {'step': 'neg_type'}
            send_whatsapp_message(sender_phone, "🤝 *قسم التفاوض المباشر:*\n\nأرسل:\n🟢 *1* لتقديم عرض شراء\n🔵 *2* لتقديم عرض بيع" + FOOTER)
            
        elif msg_text == "4": # أسعار
            send_whatsapp_message(sender_phone, f"📊 *أسعار الصرف اليوم:*\n🔹 نشتري منك بـ: {settings['buy']} جنيه\n🔹 نبيع لك بـ: {settings['sell']} جنيه" + FOOTER)
        elif msg_text == "5": # حالة
            status = "🟢 التاجر متصل وجاهز (التنفيذ 1-15 دقيقة)" if not settings['is_busy'] else "⏱️ التاجر في وضع الانشغال حالياً"
            send_whatsapp_message(sender_phone, f"📡 *حالة المنصة:* {status}" + FOOTER)
        elif msg_text == "6": # تقييمات
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT stars, comment FROM reviews ORDER BY review_date DESC LIMIT 5')
            rows = cursor.fetchall()
            conn.close()
            txt = "🌟 *آراء عملائنا:*\n\n"
            for r in rows: txt += f"{'⭐'*r[0]}\n💬 \"{r[1]}\"\n\n"
            send_whatsapp_message(sender_phone, txt if rows else "لا توجد تقييمات بعد." + FOOTER)
        elif msg_text == "7": # إثبات
            send_whatsapp_message(sender_phone, "🛡️ *الأمان والثقة المؤسسية*\n\nحساب تاجر موثق (KYC) في Binance P2P بسجل حافل.\nالرابط لملفنا الموثق:\nhttps://www.binance.com/en/qr/dplkdf9e9827882d42e49f144ad09998fd0d" + FOOTER)
        elif msg_text == "8": # كيف يعمل
            send_whatsapp_message(sender_phone, "💡 *كيف يعمل النظام؟*\nتختار الخدمة > نرسل التفاصيل > ترفق الإشعار > المعالجة خلال 15 دقيقة بحد أقصى.\n\nفي حال التأخير لك حق المطالبة باسترجاع أموالك فوراً." + FOOTER)
        else:
            status = "🟢 متصل الآن" if not settings['is_busy'] else "⏱️ وضع الانشغال"
            welcome = (
                f"مرحباً بك في منصة تداول USDT الآمنة 🚀\n"
                f"📡 حالة التاجر: {status}\n\n"
                f"يرجى إرسال الرقم المطلوب:\n"
                f"1️⃣ 🟢 شراء USDT\n"
                f"2️⃣ 🔵 بيع USDT\n"
                f"3️⃣ 🤝 تقديم عرض سعر (تفاوض)\n"
                f"4️⃣ 📊 عرض أسعار الصرف\n"
                f"5️⃣ 📡 حالة المنصة\n"
                f"6️⃣ ⭐ آراء وتقييمات العملاء\n"
                f"7️⃣ 🛡️ إثبات الثقة والموثوقية\n"
                f"8️⃣ 💡 كيف يعمل النظام؟\n" + FOOTER
            )
            send_whatsapp_message(sender_phone, welcome)

    # --- مسار التوثيق ---
    elif state == 'auth_name':
        user_states[sender_phone]['full_name'] = msg_text
        user_states[sender_phone]['step'] = 'auth_bank'
        send_whatsapp_message(sender_phone, "💳 ممتاز. يرجى إرسال *رقم حسابك الأساسي* في (بنكك):" + FOOTER)

    elif state == 'auth_bank':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, full_name, phone_number, bank_account, platform) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET full_name=EXCLUDED.full_name, bank_account=EXCLUDED.bank_account", (int(sender_phone), user_states[sender_phone]['full_name'], f"+{sender_phone}", msg_text, 'whatsapp'))
        conn.commit()
        conn.close()
        send_whatsapp_message(sender_phone, "🎉 تم توثيق حسابك بنجاح!")
        
        # استكمال ما كان يريده العميل
        nxt = user_states[sender_phone].get('next_action')
        if nxt == 'buy':
            user_states[sender_phone] = {'step': 'buy_amount'}
            send_whatsapp_message(sender_phone, f"🟢 *شراء USDT*\nالكمية المتوفرة: {settings['usdt_balance']}\nاكتب الكمية (رقم فقط):" + FOOTER)
        elif nxt == 'sell':
            max_buy = round(settings['sdg_balance'] / settings['buy'], 2) if settings['buy'] > 0 else 0
            user_states[sender_phone] = {'step': 'sell_amount'}
            send_whatsapp_message(sender_phone, f"🔵 *بيع USDT*\nالحد الأقصى: {max_buy}\nاكتب الكمية (رقم فقط):" + FOOTER)
        elif nxt == 'neg':
            user_states[sender_phone] = {'step': 'neg_type'}
            send_whatsapp_message(sender_phone, "🤝 *التفاوض:*\nأرسل 1 للشراء، 2 للبيع" + FOOTER)

    # --- مسار التقييم والنشر للقناة ---
    elif state == 'write_review':
        stars = user_states[sender_phone]['stars']
        comment = msg_text
        user_info = is_user_registered(sender_phone)
        name = user_info[0] if user_info else "عميل"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO reviews (user_id, stars, comment) VALUES (%s, %s, %s)', (int(sender_phone), stars, comment))
        conn.commit()
        conn.close()
        
        del user_states[sender_phone]
        send_whatsapp_message(sender_phone, "❤️ شكرًا جزيلاً لك على وقتك ورأيك الجميل!" + FOOTER)
        
        # النشر في القناة
        stars_display = "⭐" * stars
        review_msg = f"🌟 <b>تقييم جديد من عملاء الواتساب</b> 🌟\n\n👤 <b>العميل:</b> {name}\n⭐️ <b>التقييم:</b> {stars_display}\n\n💬 <i>\"{comment}\"</i>\n\nــــــــــــــــــــــــــــــــــــــ\n🤖 <b>للتداول:</b> {CHANNEL_USERNAME}"
        notify_telegram_admin(review_msg, send_to_channel=True)

    # --- مسار الشراء ---
    elif state == 'buy_amount':
        try:
            amount = float(msg_text)
            if amount > settings['usdt_balance']: return send_whatsapp_message(sender_phone, f"💡 المتاح حالياً {settings['usdt_balance']} USDT. اكتب كمية أقل:" + FOOTER)
            total_sdg = amount * settings['sell']
            user_states[sender_phone].update({'amount': amount, 'total_sdg': total_sdg, 'step': 'buy_wallet'})
            send_whatsapp_message(sender_phone, f"💰 مطلوب دفع: {total_sdg} جنيه.\n\n👇 أرسل *محفظتك (TRC20)* أو *Binance Pay ID*:" + FOOTER)
        except: send_whatsapp_message(sender_phone, "⚠️ أرقام فقط." + FOOTER)

    elif state == 'buy_wallet':
        user_states[sender_phone].update({'wallet': msg_text, 'step': 'buy_receipt'})
        order = user_states[sender_phone]
        text = (f"🛡️ *خطوة أخيرة*\n🔹 الكمية: {order['amount']} USDT\n🔹 المحفظة: {order['wallet']}\n🔹 المبلغ: *{order['total_sdg']} جنيه*\n\n"
                f"🏦 *حسابنا (بنكك):*\n`3290549`\nمحمد زاهر عبدالله علي\n\n📸 *أرسل صورة إشعار الدفع هنا (صورة فقط).*" + FOOTER)
        send_whatsapp_message(sender_phone, text)

    elif state == 'buy_receipt':
        if msg_type == 'image':
            order = user_states[sender_phone]
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO orders (user_id, order_type, amount, total_sdg, wallet_address, status, platform) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING order_id''', (int(sender_phone), 'BUY', order['amount'], order['total_sdg'], order['wallet'], 'PENDING', 'whatsapp'))
            order_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            send_whatsapp_message(sender_phone, "🕒 *تم الاستلام!* جاري المعالجة..." + FOOTER)
            notify_telegram_admin(f"🚨 *طلب شراء واتساب!* `#{order_id}`\n\n📱 عميل: `+{sender_phone}`\n[💬 مراسلة واتساب](wa.me/{sender_phone})\nيطلب: `{order['amount']}` USDT\nدفع: `{order['total_sdg']}` جنيه\nالمحفظة:\n`{order['wallet']}`")
            del user_states[sender_phone]
        else: send_whatsapp_message(sender_phone, "⚠️ أرسل *صورة* الإشعار فقط." + FOOTER)

    # --- مسار البيع ---
    elif state == 'sell_amount':
        try:
            amount = float(msg_text)
            total_sdg = amount * settings['buy']
            max_buy = round(settings['sdg_balance'] / settings['buy'], 2) if settings['buy'] > 0 else 0
            if amount > max_buy: return send_whatsapp_message(sender_phone, f"💡 المتاح للشراء {max_buy} USDT. اكتب كمية أقل:" + FOOTER)
            user_info = is_user_registered(sender_phone)
            saved_bank = user_info[1] if user_info else "غير مسجل"
            user_states[sender_phone].update({'amount': amount, 'total_sdg': total_sdg, 'step': 'sell_bank_confirm'})
            send_whatsapp_message(sender_phone, f"أنت تبيع {amount} USDT.\nالجنيه: {total_sdg}\n\nحسابك المسجل هو: {saved_bank}\n\nأرسل *1* للاستلام عليه، أو اكتب رقم الحساب واسمك الجديد إذا أردت تغييره:" + FOOTER)
        except: send_whatsapp_message(sender_phone, "⚠️ أرقام فقط." + FOOTER)

    elif state == 'sell_bank_confirm':
        user_info = is_user_registered(sender_phone)
        client_bank = user_info[1] if msg_text == "1" else msg_text
        user_states[sender_phone].update({'client_bank': client_bank, 'step': 'sell_receipt'})
        order = user_states[sender_phone]
        text = (f"🛡️ *خطوة أخيرة*\n🔹 تبيع: {order['amount']} USDT\n🔹 بنكك: {order['client_bank']}\n🔹 نرسل لك: *{order['total_sdg']} جنيه*\n\n"
                f"🔵 *حول الـ USDT إلى:*\nPay ID: `950533501`\nTRC20: `TR7C9B3914CnDZ9Sii6yMhw5pjNojB51BH`\n\n📸 *أرسل صورة الإشعار هنا.*" + FOOTER)
        send_whatsapp_message(sender_phone, text)

    elif state == 'sell_receipt':
        if msg_type == 'image':
            order = user_states[sender_phone]
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO orders (user_id, order_type, amount, total_sdg, wallet_address, status, platform) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING order_id''', (int(sender_phone), 'SELL', order['amount'], order['total_sdg'], f"بنك العميل: {order['client_bank']}", 'PENDING', 'whatsapp'))
            order_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            send_whatsapp_message(sender_phone, "🕒 *تم الاستلام!* جاري المعالجة..." + FOOTER)
            notify_telegram_admin(f"🚨 *طلب بيع واتساب!* `#{order_id}`\n\n📱 عميل: `+{sender_phone}`\n[💬 مراسلة واتساب](wa.me/{sender_phone})\nأرسل: `{order['amount']}` USDT\nيجب تحويل: *{order['total_sdg']}* جنيه\nلحساب:\n`{order['client_bank']}`")
            del user_states[sender_phone]
        else: send_whatsapp_message(sender_phone, "⚠️ أرسل *صورة* التحويل فقط." + FOOTER)

    # --- مسار التفاوض ---
    elif state == 'neg_type':
        if msg_text == "1":
            user_states[sender_phone] = {'step': 'neg_amount', 'neg_order': 'buy'}
            send_whatsapp_message(sender_phone, f"🟢 *تفاوض شراء*\nالمتاح: {settings['usdt_balance']} USDT\nاكتب الكمية:" + FOOTER)
        elif msg_text == "2":
            user_states[sender_phone] = {'step': 'neg_amount', 'neg_order': 'sell'}
            max_buy = round(settings['sdg_balance'] / settings['buy'], 2) if settings['buy'] > 0 else 0
            send_whatsapp_message(sender_phone, f"🔵 *تفاوض بيع*\nالحد الأقصى: {max_buy} USDT\nاكتب الكمية:" + FOOTER)
    
    elif state == 'neg_amount':
        try:
            amount = float(msg_text)
            neg_order = user_states[sender_phone]['neg_order']
            if neg_order == 'buy' and amount > settings['usdt_balance']: return send_whatsapp_message(sender_phone, "الكمية أكبر من المتاح. اكتب كمية أقل:" + FOOTER)
            user_states[sender_phone].update({'amount': amount, 'step': 'neg_price'})
            send_whatsapp_message(sender_phone, f"الكمية: {amount} USDT.\nالسعر الرسمي: {settings['sell'] if neg_order=='buy' else settings['buy']}\n\n👇 **كم السعر المقترح للـ USDT الواحد؟**" + FOOTER)
        except: send_whatsapp_message(sender_phone, "⚠️ أرقام فقط." + FOOTER)

    elif state == 'neg_price':
        try:
            price = float(msg_text)
            order = user_states[sender_phone]
            amount = order['amount']
            neg_order = order['neg_order']
            total = amount * price
            
            # نغلق مسار الواتساب هنا وننتظر أدمن تيليجرام ليرد (أو نعامله كطلب قيد الانتظار)
            send_whatsapp_message(sender_phone, f"⏳ *تم رفع العرض!*\n{amount} USDT بسعر {price}\nالإجمالي: {total}\n\nالرجاء الانتظار قليلاً للرد من الإدارة..." + FOOTER)
            
            user_info = is_user_registered(sender_phone)
            name = user_info[0] if user_info else "العميل"
            op_text = "شراء" if neg_order == 'buy' else "بيع"
            
            notify_telegram_admin(f"🤝 *طلب تفاوض واتساب!*\n👤 العميل: `{name}`\n[💬 راسله واتساب](wa.me/{sender_phone})\nيرغب في: **{op_text}**\nالكمية: `{amount}`\nالسعر المعروض: `{price}`\n\n*(قم بمراسلته مباشرة على واتساب للاتفاق أو قبول العرض)*")
            del user_states[sender_phone]
        except: send_whatsapp_message(sender_phone, "⚠️ أرقام فقط." + FOOTER)

# ==========================================
# الخادم المستضيف (Webhook Server)
# ==========================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Forbidden', 403

    if request.method == 'POST':
        try:
            body = request.json
            entry = body.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            
            if 'messages' in value:
                message_data = value['messages'][0]
                sender_phone = message_data['from']
                msg_type = message_data.get('type')
                msg_text = message_data['text']['body'] if msg_type == 'text' else ""
                handle_whatsapp_message(sender_phone, msg_text, msg_type)
        except Exception as e: pass
        return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)