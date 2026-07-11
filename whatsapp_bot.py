from flask import Flask, request, jsonify
import requests
import psycopg2
import os
import json
import re

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
ADMIN_WA_NUMBER = '249117017444'
WA_CHANNEL_LINK = "https://whatsapp.com/channel/0029VbDXBPq8V0toBVu2CE41"

FOOTER = "\n\nــــــــــــــــــــــــــــــــــــــــ\n0️⃣ ❌ لإلغاء الطلب والعودة للقائمة\n🎧 للدعم الفني المباشر: أرسل كلمة (دعم)"

user_states = {}

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def get_bot_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT sar_price, aed_price, egp_buy_price, egp_sell_price, is_busy FROM settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    if row: return {'sar_price': row[0], 'aed_price': row[1], 'egp_buy_price': row[2], 'egp_sell_price': row[3], 'is_busy': row[4]}
    return None

def is_user_registered(phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT full_name, bank_account FROM users WHERE user_id = %s', (int(phone),))
    result = cursor.fetchone()
    conn.close()
    return result

def is_user_banned(phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM banned_users WHERE user_id = %s', (int(phone),))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

def has_pending_order(phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM orders WHERE user_id = %s AND status IN ('PENDING', 'AWAITING_ACCOUNT', 'PENDING_RECEIPT')", (int(phone),))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

def send_whatsapp_message(to_phone, text):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_phone, "type": "text", "text": {"body": text}}
    requests.post(url, headers=headers, json=payload)

def get_whatsapp_media(media_id):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    res = requests.get(f"https://graph.facebook.com/v17.0/{media_id}", headers=headers)
    if res.status_code == 200:
        media_url = res.json().get('url')
        media_res = requests.get(media_url, headers=headers)
        if media_res.status_code == 200:
            return media_res.content
    return None

def notify_telegram_admin_with_photo(photo_bytes, caption, order_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {'photo': ('receipt.jpg', photo_bytes, 'image/jpeg')}
    reply_markup = {
        "inline_keyboard": [
            [{"text": "🔄 جاري المعالجة (تطمين العميل)", "callback_data": f"process_order_{order_id}"}],
            [{"text": "✅ تأكيد وإكمال", "callback_data": f"approve_order_{order_id}"},
             {"text": "❌ رفض الطلب", "callback_data": f"reject_order_{order_id}"}]
        ]
    }
    data = {'chat_id': ADMIN_ID, 'caption': caption, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    requests.post(url, files=files, data=data)

def notify_telegram_admin_action(text, order_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    reply_markup = {"inline_keyboard": [[{"text": "💳 إرسال بيانات الدفع للعميل", "callback_data": f"provide_account_{order_id}"}]]}
    payload = {'chat_id': ADMIN_ID, 'text': text, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    requests.post(url, json=payload)

def handle_whatsapp_message(sender_phone, msg_text, msg_type, image_id=None):
    global user_states
    msg_text = str(msg_text).strip() if msg_text else ""
    
    if is_user_banned(sender_phone):
        return send_whatsapp_message(sender_phone, "⛔️ عذراً، حسابك محظور من استخدام النظام بسبب مخالفة شروط الاستخدام.")

    if msg_text == "دعم" or msg_text == "مساعدة":
        send_whatsapp_message(sender_phone, "🎧 *الدعم الفني المباشر:*\nنحن متواجدون للرد على استفساراتك فوراً عبر الرابط:\nwa.me/249117017444\n\n(طلبك الحالي إن وجد لا يزال محفوظاً).")
        return

    if has_pending_order(sender_phone):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM orders WHERE user_id = %s AND status IN ('PENDING', 'AWAITING_ACCOUNT', 'PENDING_RECEIPT')", (int(sender_phone),))
        current_db_status = cursor.fetchone()
        conn.close()
        
        if current_db_status:
            db_stat = current_db_status[0]
            if msg_type == 'image' and image_id and db_stat == 'PENDING_RECEIPT':
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE orders SET status = 'PENDING' WHERE user_id = %s AND status = 'PENDING_RECEIPT' RETURNING order_id, amount, order_type, wallet_address", (int(sender_phone),))
                updated_order = cursor.fetchone()
                conn.commit(); conn.close()
                
                if updated_order:
                    order_id, amount, o_type, w_addr = updated_order
                    send_whatsapp_message(sender_phone, "🕒 *تم استلام الإشعار المالي بنجاح!*\n\n✅ جارٍ التحقق من التحويل والبنك...\n✅ الإدارة تقوم الآن بتجهيز أموالك للإرسال...\n\n(سيصلك إشعار التنفيذ النهائي قريباً، يرجى الانتظار)" + FOOTER)
                    photo_bytes = get_whatsapp_media(image_id)
                    user_info = is_user_registered(sender_phone)
                    full_name = user_info[0] if user_info else "غير مسجل"
                    admin_alert = f"🚨 *تأكيد دفع (واتساب) لطلب #{order_id}!*\n\n👤 العميل: `{full_name}`\n🔗 [💬 مراسلة واتساب](wa.me/{sender_phone})\n\nالعميل قام برفع الإشعار المرفق لتأكيد تحويله مبلغ `{amount}`."
                    if photo_bytes: notify_telegram_admin_with_photo(photo_bytes, admin_alert, order_id)
                    return

            if msg_text == "0":
                trust_msg = "🛡️ *إجراء أمني:*\nعذراً، لا يمكن إلغاء الطلب أثناء معالجته مالياً حفاظاً على حقوقك.\nلا تقلق، طلبك في أيادي أمينة وقيد المراجعة."
            else:
                if db_stat == 'AWAITING_ACCOUNT': trust_msg = "🕒 *طلبك قيد التجهيز*\nنحن نقوم الآن بتجهيز الحساب البنكي الآمن لتقوم بالتحويل عليه، سيصلك خلال ثوانٍ..."
                elif db_stat == 'PENDING_RECEIPT': trust_msg = "🕒 *نحن في انتظار إشعارك*\nالرجاء إرفاق صورة إشعار التحويل البنكي هنا لكي نقوم بإرسال أموالك فوراً."
                else: trust_msg = "🕒 *طلبك قيد التنفيذ والمراجعة*\nنحن نقوم بمطابقة الإشعار المالي الآن. التنفيذ آلي وسريع."
            send_whatsapp_message(sender_phone, trust_msg + FOOTER)
            return

    if msg_text == "0":
        if sender_phone in user_states: del user_states[sender_phone]
        send_whatsapp_message(sender_phone, "🚫 تم إلغاء الطلب بأمان.\nأرسل (مرحبا) للبدء من جديد أو لعرض القائمة." + FOOTER)
        return

    state = user_states.get(sender_phone, {}).get('step')
    settings = get_bot_settings()

    if not state and msg_text in ["1", "2", "3", "4"] and settings['is_busy']:
        return send_whatsapp_message(sender_phone, "⏱️ عذراً، الإدارة في وضع الانشغال أو خارج أوقات العمل حالياً. يرجى المحاولة لاحقاً." + FOOTER)

    if not state:
        # نظام التقاط التقييم السهل جداً
        if msg_text.startswith("تقييم"):
            try:
                numbers = re.findall(r'\d+', msg_text)
                if numbers:
                    stars = int(numbers[0])
                    if 1 <= stars <= 5:
                        user_states[sender_phone] = {'step': 'write_review', 'stars': stars}
                        send_whatsapp_message(sender_phone, "✍️ شكراً لتقييمك! يرجى كتابة تعليق قصير عن خدمتنا لتشجيع الآخرين:" + FOOTER)
                        return
            except: pass

        if msg_text == "1":
            if not is_user_registered(sender_phone):
                user_states[sender_phone] = {'step': 'auth_name', 'next_action': 'sell_sar'}
                return send_whatsapp_message(sender_phone, "🛡️ مرحباً بك في منصة التحويل الآمن.\n\n👤 لضمان حقوقك، يرجى كتابة *اسمك الكامل* (الذي يظهر في حسابك البنكي):" + FOOTER)
            user_states[sender_phone] = {'step': 'sell_sar_amount'}
            send_whatsapp_message(sender_phone, f"🇸🇦 *تحويل من السعودية (استلام بنكك)*\n\nنستلم منك الريال السعودي، ونسلم أهلك بالجنيه السوداني فوراً.\n\n💡 *للمبالغ الكبيرة:* يمكنك تقسيم التحويل والبدء بمبلغ صغير للتجربة والشعور بالأمان.\n\nالرجاء كتابة كمية الريال التي تريد تحويلها (رقم فقط):" + FOOTER)
            
        elif msg_text == "2":
            if not is_user_registered(sender_phone):
                user_states[sender_phone] = {'step': 'auth_name', 'next_action': 'sell_aed'}
                return send_whatsapp_message(sender_phone, "🛡️ مرحباً بك في منصة التحويل الآمن.\n\n👤 لضمان حقوقك، يرجى كتابة *اسمك الكامل* (الذي يظهر في حسابك البنكي):" + FOOTER)
            user_states[sender_phone] = {'step': 'sell_aed_amount'}
            send_whatsapp_message(sender_phone, f"🇦🇪 *تحويل من الإمارات (استلام بنكك)*\n\nنستلم منك الدرهم الإماراتي، ونسلم أهلك بالجنيه السوداني فوراً.\n\n💡 *للمبالغ الكبيرة:* ابدأ بمبلغ صغير للتجربة أولاً.\n\nالرجاء كتابة كمية الدرهم التي تريد تحويلها (رقم فقط):" + FOOTER)
            
        elif msg_text == "3":
            if not is_user_registered(sender_phone):
                user_states[sender_phone] = {'step': 'auth_name', 'next_action': 'sell_egp'}
                return send_whatsapp_message(sender_phone, "🛡️ مرحباً بك في منصة التحويل الآمن.\n\n👤 لضمان حقوقك، يرجى كتابة *اسمك الكامل* (الذي يظهر في حسابك البنكي):" + FOOTER)
            user_states[sender_phone] = {'step': 'sell_egp_amount'}
            send_whatsapp_message(sender_phone, f"🇪🇬 *تحويل من مصر (استلام بنكك)*\n\nنستلم منك الجنيه المصري، ونسلمك بالجنيه السوداني.\n\nالرجاء كتابة كمية الجنيه المصري التي تريد تحويلها (رقم فقط):" + FOOTER)
            
        elif msg_text == "4":
            if not is_user_registered(sender_phone):
                user_states[sender_phone] = {'step': 'auth_name', 'next_action': 'buy_egp'}
                return send_whatsapp_message(sender_phone, "🛡️ مرحباً بك في منصة التحويل الآمن.\n\n👤 لضمان حقوقك، يرجى كتابة *اسمك الكامل* (الذي يظهر في حسابك البنكي):" + FOOTER)
            user_states[sender_phone] = {'step': 'buy_egp_amount'}
            send_whatsapp_message(sender_phone, f"🔄 *شحن حساب مصري (إنستاباي/فودافون كاش)*\n\nنستلم منك الجنيه السوداني، ونشحن لك حسابك في مصر.\n\nالرجاء كتابة كمية *الجنيه المصري* التي تريد شحنها (رقم فقط):" + FOOTER)
            
        elif msg_text == "5":
            prices_msg = (
                f"📊 *أسعار التحويل وصرف العملات اليوم:*\n\n"
                f"🇸🇦 *الريال السعودي (استلام في بنكك):* {settings['sar_price']} جنيه\n"
                f"🇦🇪 *الدرهم الإماراتي (استلام في بنكك):* {settings['aed_price']} جنيه\n"
                f"🇪🇬 *الجنيه المصري (تحويل من مصر لسودان - استلام بنكك):* {settings['egp_sell_price']} جنيه\n"
                f"🔄 *الجنيه المصري (تحويل من سودان لمصر - شحن إنستاباي):* {settings['egp_buy_price']} جنيه\n"
            )
            send_whatsapp_message(sender_phone, prices_msg + FOOTER)
        elif msg_text == "6":
            send_whatsapp_message(sender_phone, "🎧 *قسم الدعم الفني*\nلأي استفسار مالي أو لمتابعة حوالتك الكبيرة، نحن هنا لخدمتك:\nwa.me/249117017444" + FOOTER)
        else:
            status = "🟢 متصل (التنفيذ سريع)" if not settings['is_busy'] else "⏱️ وضع الانشغال"
            welcome = (
                f"مرحباً بك في منصة الحوالات السريعة والآمنة 🚀\n"
                f"📡 حالة النظام: {status}\n\n"
                f"يرجى إرسال الرقم المطلوب لاختيار الخدمة:\n\n"
                f"1️⃣ 🇸🇦 تحويل من السعودية (تستلم بنكك)\n"
                f"2️⃣ 🇦🇪 تحويل من الإمارات (تستلم بنكك)\n"
                f"3️⃣ 🇪🇬 تحويل من مصر (تستلم بنكك)\n"
                f"4️⃣ 🔄 شحن حساب مصري (إنستاباي/محافظ)\n"
                f"5️⃣ 📊 أسعار الصرف للحوالات اليوم\n"
                f"6️⃣ 🎧 التحدث مع الدعم الفني\n" + FOOTER
            )
            send_whatsapp_message(sender_phone, welcome)

    elif state == 'auth_name':
        user_states[sender_phone]['full_name'] = msg_text
        user_states[sender_phone]['step'] = 'auth_bank'
        send_whatsapp_message(sender_phone, "💳 ممتاز. يرجى إرسال *رقم حسابك الأساسي* في تطبيق (بنكك) لنسلمك عليه:" + FOOTER)

    elif state == 'auth_bank':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, full_name, bank_account, platform) VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET full_name=EXCLUDED.full_name, bank_account=EXCLUDED.bank_account", (int(sender_phone), user_states[sender_phone]['full_name'], msg_text, 'whatsapp'))
        conn.commit(); conn.close()
        send_whatsapp_message(sender_phone, "🎉 تم توثيق حسابك بنجاح!")
        
        nxt = user_states[sender_phone].get('next_action')
        if nxt == 'sell_sar':
            user_states[sender_phone] = {'step': 'sell_sar_amount'}
            send_whatsapp_message(sender_phone, f"🇸🇦 *تحويل من السعودية*\nاكتب كمية الريال التي تريد تحويلها للسودان (رقم فقط):" + FOOTER)
        elif nxt == 'sell_aed':
            user_states[sender_phone] = {'step': 'sell_aed_amount'}
            send_whatsapp_message(sender_phone, f"🇦🇪 *تحويل من الإمارات*\nاكتب كمية الدرهم التي تريد تحويلها للسودان (رقم فقط):" + FOOTER)
        elif nxt == 'sell_egp':
            user_states[sender_phone] = {'step': 'sell_egp_amount'}
            send_whatsapp_message(sender_phone, f"🇪🇬 *تحويل من مصر*\nاكتب كمية الجنيه المصري التي تريد تحويلها (رقم فقط):" + FOOTER)
        elif nxt == 'buy_egp':
            user_states[sender_phone] = {'step': 'buy_egp_amount'}
            send_whatsapp_message(sender_phone, f"🔄 *شحن حساب مصري*\nاكتب كمية الجنيه المصري التي تريد شحنها لحسابك (رقم فقط):" + FOOTER)

    elif state == 'write_review':
        stars = user_states[sender_phone]['stars']
        comment = msg_text
        user_info = is_user_registered(sender_phone)
        name = user_info[0] if user_info else "عميل"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO reviews (user_id, stars, comment) VALUES (%s, %s, %s)', (int(sender_phone), stars, comment))
        conn.commit(); conn.close()
        del user_states[sender_phone]
        send_whatsapp_message(sender_phone, "❤️ شكرًا جزيلاً لك على وقتك ورأيك الجميل!" + FOOTER)

    # --- Flow 1: Client sends Foreign (SAR/AED/EGP), gets SDG ---
    elif state in ['sell_sar_amount', 'sell_aed_amount', 'sell_egp_amount']:
        try:
            amount = float(msg_text)
            c_type = 'SAR' if 'sar' in state else 'AED' if 'aed' in state else 'EGP'
            rate = settings[f'{c_type.lower()}_price'] if c_type != 'EGP' else settings['egp_sell_price']
            total_sdg = amount * rate
            
            user_info = is_user_registered(sender_phone)
            saved_bank = user_info[1] if user_info else "غير مسجل"
            user_states[sender_phone].update({'amount': amount, 'total_sdg': total_sdg, 'c_type': c_type, 'step': 'sell_foreign_bank_confirm'})
            send_whatsapp_message(sender_phone, f"الكمية: {amount} {c_type}\nتستلم في السودان: {total_sdg} جنيه\n\nحسابك المسجل في بنكك هو: {saved_bank}\n\nأرسل *1* للاستلام عليه، أو اكتب رقم واسم الحساب الجديد إذا أردت تغييره:" + FOOTER)
        except: send_whatsapp_message(sender_phone, "⚠️ أرقام فقط." + FOOTER)

    elif state == 'sell_foreign_bank_confirm':
        user_info = is_user_registered(sender_phone)
        client_bank = user_info[1] if msg_text == "1" else msg_text
        order = user_states[sender_phone]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO orders (user_id, order_type, amount, total_sdg, wallet_address, status, platform) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING order_id''', (int(sender_phone), f"SELL_{order['c_type']}", order['amount'], order['total_sdg'], f"بنكك: {client_bank}", 'AWAITING_ACCOUNT', 'whatsapp'))
        order_id = cursor.fetchone()[0]
        conn.commit(); conn.close()
        
        send_whatsapp_message(sender_phone, "🕒 *جارٍ تجهيز التحويل...*\n\nالرجاء الانتظار قليلاً، نحن نقوم الآن بتجهيز الحساب البنكي الموثوق لتقوم بالتحويل إليه لضمان أمان أموالك..." + FOOTER)
        
        admin_alert = f"🚨 *حوالة جديدة من واتساب!* `#{order_id}`\n\nالعميل يريد إرسال `{order['amount']}` {order['c_type']}\nيجب تسليمه: `{order['total_sdg']}` جنيه سوداني.\n\nاضغط الزر أدناه لتزويده برقم الحساب (STC Pay/Bank) ليقوم بالتحويل عليه:"
        notify_telegram_admin_action(admin_alert, order_id)
        del user_states[sender_phone]

    # --- Flow 2: Client sends SDG, gets EGP ---
    elif state == 'buy_egp_amount':
        try:
            amount = float(msg_text)
            rate = settings['egp_buy_price']
            total_sdg = amount * rate
            user_states[sender_phone].update({'amount': amount, 'total_sdg': total_sdg, 'step': 'buy_egp_account'})
            send_whatsapp_message(sender_phone, f"أنت تريد استلام: {amount} جنيه مصري\nالمطلوب دفعه: {total_sdg} جنيه سوداني\n\n👇 الرجاء كتابة *رقم إنستاباي أو فودافون كاش* الذي تريد الاستلام عليه في مصر:" + FOOTER)
        except: send_whatsapp_message(sender_phone, "⚠️ أرقام فقط." + FOOTER)

    elif state == 'buy_egp_account':
        client_egp_account = msg_text
        order = user_states[sender_phone]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO orders (user_id, order_type, amount, total_sdg, wallet_address, status, platform) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING order_id''', (int(sender_phone), 'BUY_EGP', order['amount'], order['total_sdg'], f"مصري: {client_egp_account}", 'PENDING_RECEIPT', 'whatsapp'))
        order_id = cursor.fetchone()[0]
        conn.commit(); conn.close()
        
        text = (f"🛡️ *خطوة أخيرة*\n\n🔹 حساب الاستلام في مصر: `{client_egp_account}`\n🔹 المبلغ المطلوب منك: *{order['total_sdg']} جنيه سوداني*\n\n"
                f"🏦 *حسابنا (بنكك):*\n• الحساب: `3290549`\n• الاسم: محمد زاهر عبدالله علي\n• التعليق: حوالة الكترونية\n\n📸 *قم بتحويل المبلغ وأرسل صورة الإشعار هنا.*" + FOOTER)
        send_whatsapp_message(sender_phone, text)
        del user_states[sender_phone]

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN: return request.args.get('hub.challenge'), 200
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
                image_id = message_data['image']['id'] if msg_type == 'image' else None
                handle_whatsapp_message(sender_phone, msg_text, msg_type, image_id)
        except Exception: pass
        return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)