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
BOT_WA_LINK = "https://wa.me/249909590325"

FOOTER = "\n\nــــــــــــــــــــــــــــــــــــــــ\n0️⃣ ❌ لإلغاء الطلب والعودة للقائمة\n🎧 للدعم الفني المباشر: أرسل كلمة (دعم)"

user_states = {}

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def get_bot_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT aed_price_sdg, aed_price_egp, sar_price_sdg, sar_price_egp, egp_sell_price, egp_buy_price, is_busy FROM settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    if row: 
        return {
            'aed_price_sdg': row[0], 
            'aed_price_egp': row[1], 
            'sar_price_sdg': row[2], 
            'sar_price_egp': row[3], 
            'egp_sell_price': row[4], 
            'egp_buy_price': row[5], 
            'is_busy': row[6]
        }
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
    cursor.execute("SELECT 1 FROM orders WHERE user_id = %s AND status IN ('PENDING', 'AWAITING_ACCOUNT', 'PENDING_RECEIPT', 'LOCKED_FOR_PROCESSING')", (int(phone),))
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

def notify_telegram_admin_text(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': ADMIN_ID, 'text': text, 'parse_mode': 'Markdown'}
    requests.post(url, json=payload)

def get_currency_name(choice):
    mapping = {
        "1": "الدرهم الإماراتي", "2": "الدرهم الإماراتي",
        "3": "الريال السعودي", "4": "الريال السعودي",
        "5": "الجنيه المصري", "6": "الجنيه المصري"
    }
    return mapping.get(choice, "العملة")

def handle_whatsapp_message(sender_phone, msg_text, msg_type, image_id=None):
    global user_states
    msg_text = str(msg_text).strip() if msg_text else ""
    
    if is_user_banned(sender_phone):
        return send_whatsapp_message(sender_phone, "⛔️ عذراً، حسابك محظور من استخدام النظام بسبب مخالفة شروط الاستخدام.")

    if msg_text == "دعم" or msg_text == "مساعدة":
        send_whatsapp_message(sender_phone, f"🎧 *الدعم الفني المباشر:*\nفريقنا متواجد للرد على استفساراتك فوراً عبر الرابط التالي:\nhttps://wa.me/249117017444\n\n(طلبك الحالي إن وجد لا يزال محفوظاً بأمان).")
        return

    if has_pending_order(sender_phone):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT order_id, status FROM orders WHERE user_id = %s AND status IN ('PENDING', 'AWAITING_ACCOUNT', 'PENDING_RECEIPT', 'LOCKED_FOR_PROCESSING')", (int(sender_phone),))
        current_db_status = cursor.fetchone()
        
        if current_db_status:
            order_id, db_stat = current_db_status
            
            if msg_type == 'image' and image_id and db_stat == 'PENDING_RECEIPT':
                cursor.execute("UPDATE orders SET status = 'PENDING' WHERE order_id = %s RETURNING amount, order_type, wallet_address", (order_id,))
                updated_order = cursor.fetchone()
                conn.commit(); conn.close()
                
                if updated_order:
                    amount, o_type, w_addr = updated_order
                    send_whatsapp_message(sender_phone, "🕒 *تم استلام إشعارك المالي بنجاح!*\n\n✅ جارٍ التحقق من الدفع والاعتمادات البنكية...\n✅ الإدارة تقوم الآن بتجهيز أموالك للإرسال الفوري...\n\n(سيصلك إشعار التنفيذ النهائي قريباً، يرجى الانتظار)" + FOOTER)
                    photo_bytes = get_whatsapp_media(image_id)
                    user_info = is_user_registered(sender_phone)
                    full_name = user_info[0] if user_info else "غير مسجل"
                    admin_alert = f"🚨 *تأكيد دفع (واتساب) لطلب #{order_id}!*\n\n👤 العميل: `{full_name}`\n🔗 [💬 تواصل مع العميل مباشرة](https://wa.me/{sender_phone})\n\nالعميل قام برفع الإشعار المرفق لتأكيد تحويله للطلب."
                    if photo_bytes: notify_telegram_admin_with_photo(photo_bytes, admin_alert, order_id)
                    return

            if msg_text == "0":
                if db_stat in ['AWAITING_ACCOUNT', 'PENDING_RECEIPT']:
                    cursor.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
                    conn.commit()
                    conn.close()
                    notify_telegram_admin_text(f"⚠️ *إلغاء عميل واتساب استباقي:* العميل `+{sender_phone}` ألغى الطلب `#{order_id}`.")
                    if sender_phone in user_states: del user_states[sender_phone]
                    send_whatsapp_message(sender_phone, "🚫 تم إلغاء الطلب بأمان.\nأرسل (مرحبا) للبدء من جديد أو لعرض القائمة." + FOOTER)
                elif db_stat == 'LOCKED_FOR_PROCESSING':
                    conn.close()
                    send_whatsapp_message(sender_phone, "🛡️ *إجراء أمني:*\nالإدارة بدأت فعلياً في تأمين السيولة وفتح الاعتمادات لطلبك. لا يمكن الإلغاء في هذه المرحلة المستعجلة." + FOOTER)
                else:
                    conn.close()
                    trust_msg = "🛡️ *إجراء أمني:*\nعذراً، لا يمكن إلغاء الطلب بعد رفع الإشعار المالي حفاظاً على أمان أموالك.\nلا تقلق، طلبك في أيادي أمينة وقيد التنفيذ المالي."
                    send_whatsapp_message(sender_phone, trust_msg + FOOTER)
                return

            conn.close()
            if db_stat == 'AWAITING_ACCOUNT': trust_msg = "🕒 *طلبك قيد التجهيز*\nنحن نقوم الآن بتجهيز الحساب البنكي الآمن لتقوم بالدفع إليه، سيصلك خلال ثوانٍ معدودة..."
            elif db_stat == 'LOCKED_FOR_PROCESSING': trust_msg = "🛡️ *الطلب قيد التنفيذ المالي*\nالإدارة بدأت فعلياً في تأمين السيولة. يرجى الانتظار لحظياً."
            elif db_stat == 'PENDING_RECEIPT': trust_msg = "🕒 *نحن في انتظار إشعارك*\nالرجاء إرفاق صورة إشعار الدفع هنا لكي نقوم بإرسال أموالك فوراً."
            else: trust_msg = "🕒 *طلبك قيد التنفيذ والمراجعة*\nنحن نقوم بمطابقة العملية الآن. التنفيذ سريع وآمن."
            send_whatsapp_message(sender_phone, trust_msg + FOOTER)
            return
            
        conn.close()

    if msg_text == "0":
        if sender_phone in user_states: del user_states[sender_phone]
        send_whatsapp_message(sender_phone, "🚫 تم إلغاء الطلب بأمان.\nأرسل (مرحبا) للبدء من جديد أو لعرض القائمة." + FOOTER)
        return

    state = user_states.get(sender_phone, {}).get('step')
    settings = get_bot_settings()

    if not state and msg_text in ["1", "2", "3", "4", "5", "6"] and settings['is_busy']:
        return send_whatsapp_message(sender_phone, "⏱️ عذراً، الإدارة في وضع الانشغال أو خارج أوقات العمل حالياً. يرجى المحاولة لاحقاً." + FOOTER)

    if not state:
        if msg_text.startswith("تقييم"):
            try:
                numbers = re.findall(r'\d+', msg_text)
                if numbers:
                    stars = int(numbers[0])
                    if 1 <= stars <= 5:
                        user_states[sender_phone] = {'step': 'write_review', 'stars': stars}
                        send_whatsapp_message(sender_phone, "✍️ شكراً لتقييمك الرائع! يرجى كتابة تعليق قصير عن تجربتك الموثوقة معنا لتشجيع الآخرين:" + FOOTER)
                        return
            except: pass

        if msg_text in ["1", "2", "3", "4", "5", "6"]:
            if not is_user_registered(sender_phone):
                user_states[sender_phone] = {'step': 'auth_name', 'next_action': msg_text}
                return send_whatsapp_message(sender_phone, "🛡️ مرحباً بك في *واصِل دايركت - Wasel Direct*.\n\n👤 لضمان حقوقك المالية وتسهيل المطابقة، يرجى كتابة *اسمك الكامل* (كما يظهر في حسابك البنكي):" + FOOTER)
            
            user_states[sender_phone] = {'step': 'transfer_amount', 'transfer_type': msg_text}
            currency_from = get_currency_name(msg_text)
            
            hint = ""
            if msg_text in ["1", "3", "5"]:
                hint = "\n\n💡 نستلم منك المبلغ ونسلم أهلك بالجنيه السوداني فوراً بأقصى سرعة."
            elif msg_text in ["2", "4", "6"]:
                hint = "\n\n💡 نشحن لك حسابك في مصر مباشرة (إنستاباي / فودافون كاش)."

            send_whatsapp_message(sender_phone, f"👇 الرجاء كتابة كمية *{currency_from}* التي تريد تحويلها (أرقام فقط):{hint}" + FOOTER)
            
        elif msg_text == "7":
            prices_msg = (
                f"📊 *أسعار الصرف للحوالات اليوم:*\n\n"
                f"🇦🇪 *الإمارات إلى السودان:* {settings['aed_price_sdg']} جنيه سوداني\n"
                f"🇦🇪 *الإمارات إلى مصر:* {settings['aed_price_egp']} جنيه مصري\n"
                f"🇸🇦 *السعودية إلى السودان:* {settings['sar_price_sdg']} جنيه سوداني\n"
                f"🇸🇦 *السعودية إلى مصر:* {settings['sar_price_egp']} جنيه مصري\n"
                f"🇪🇬 *مصر إلى السودان:* {settings['egp_sell_price']} جنيه سوداني\n"
                f"🔄 *شحن حساب مصري (بالجنيه السوداني):* {settings['egp_buy_price']} جنيه سوداني\n\n"
                f"📢 انضم لقناتنا الرسمية لمتابعة الأسعار والتحديثات الفورية لحظة بلحظة:\n{WA_CHANNEL_LINK}"
            )
            send_whatsapp_message(sender_phone, prices_msg + FOOTER)
            
        elif msg_text == "8":
            if not is_user_registered(sender_phone):
                return send_whatsapp_message(sender_phone, "⚠️ حسابك غير مسجل في النظام بعد، يرجى طلب خدمة للتسجيل أولاً." + FOOTER)
            user_states[sender_phone] = {'step': 'update_name'}
            send_whatsapp_message(sender_phone, "⚙️ *تحديث بياناتي*\n\n👤 يرجى كتابة *اسمك الكامل الجديد*:" + FOOTER)
            
        elif msg_text == "9":
            send_whatsapp_message(sender_phone, "🎧 *قسم الدعم الفني والمتابعة*\nلأي استفسار مالي أو لمتابعة حوالتك، نحن هنا لخدمتك على مدار الساعة:\nhttps://wa.me/249117017444" + FOOTER)
            
        elif msg_text == "10":
            send_whatsapp_message(sender_phone, f"📢 *قناة التحديثات الرسمية على الواتساب:*\n\nتابع القناة الرسمية لتصلك نشرة الأسعار اليومية وتقارير التداول بشكل فوري وآمن:\n👉 {WA_CHANNEL_LINK}" + FOOTER)
            
        elif msg_text == "11":
            trust_msg = (
                "🛡️ *إثبات الأمان والضمان المالي (Wasel Direct)* 🛡️\n\n"
                "أهلاً بك عميلنا العزيز! نحن نقدر جداً أهمية الثقة الكاملة عند التعامل ماليًا عبر الإنترنت، ولذلك نوفر لك بيئة تداول محمية وموثوقة بالكامل:\n\n"
                "✅ *توثيق كامل للهوية:* حساباتنا وتداولاتنا موثقة رسمياً بالهوية الوطنية (KYC) في أكبر المنصات العالمية.\n"
                "🤝 *نصيحة ذهبية للأمان:* إذا كانت هذه أول تجربة لك معنا، **ننصحك بقوة وبشدة بتقسيم المبالغ الكبيرة إلى دفعات صغيرة متتالية** لتجربة سرعتنا وبناء الثقة خطوة بخطوة!\n"
                "🔒 *حفظ الأموال:* أموالك معنا في أيدٍ أمينة ومحمية بالكامل، وفي حال حدوث أي عطل أو تأخير يزيد عن 15 دقيقة، يحق لك استرداد كامل المبلغ فوراً دون أي قيود.\n"
                "📊 *الشفافية اليومية:* ننشر جميع الصفقات الناجحة وآراء وتقييمات العملاء باستمرار في قناتنا لتعزيز المصداقية والوضوح.\n\n"
                f"📢 تابع قناتنا للمؤشرات اليومية:\n👉 {WA_CHANNEL_LINK}"
            )
            send_whatsapp_message(sender_phone, trust_msg + FOOTER)
            
        else:
            status = "🟢 متصل (التنفيذ سريع وآمن)" if not settings['is_busy'] else "⏱️ وضع الانشغال"
            welcome = (
                f"مرحباً بك في 🛡️ *واصِل دايركت - Wasel Direct* 🛡️\n"
                f"بوابتك الأسرع والأكثر أماناً لتحويل وسحب الأموال ماليًا.\n\n"
                f"📡 حالة النظام: {status}\n\n"
                f"يرجى إرسال الرقم المطلوب لاختيار الخدمة:\n\n"
                f"1️⃣ 🇦🇪 تحويل من الإمارات ⬅️ للسودان\n"
                f"2️⃣ 🇦🇪 تحويل من الإمارات ⬅️ لمصر\n"
                f"3️⃣ 🇸🇦 تحويل من السعودية ⬅️ للسودان\n"
                f"4️⃣ 🇸🇦 تحويل من السعودية ⬅️ لمصر\n"
                f"5️⃣ 🇪🇬 تحويل من مصر ⬅️ للسودان\n"
                f"6️⃣ 🔄 شحن حساب مصري (تدفع سوداني)\n"
                f"7️⃣ 📊 أسعار الصرف للحوالات اليوم\n"
                f"8️⃣ ⚙️ تحديث بياناتي المحفوظة\n"
                f"9️⃣ 🎧 التحدث مع الدعم الفني\n"
                f"🔟 📢 متابعة قناة الواتساب للتحديثات اليومية\n"
                f"1️⃣1️⃣ 🛡️ إثبات الثقة والأمان والضمان المالي\n" + FOOTER
            )
            send_whatsapp_message(sender_phone, welcome)

    elif state == 'auth_name':
        user_states[sender_phone]['full_name'] = msg_text
        user_states[sender_phone]['step'] = 'auth_bank'
        send_whatsapp_message(sender_phone, "💳 ممتاز جداً. يرجى إرسال *رقم حسابك الأساسي* في تطبيق (بنكك) أو محفظتك التي تريد أن نسلمك عليها مستقبلاً:" + FOOTER)

    elif state == 'auth_bank':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, full_name, phone_number, bank_account, platform) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET full_name=EXCLUDED.full_name, bank_account=EXCLUDED.bank_account", (int(sender_phone), user_states[sender_phone]['full_name'], str(sender_phone), msg_text, 'whatsapp'))
        conn.commit(); conn.close()
        send_whatsapp_message(sender_phone, "🎉 تم توثيق وحفظ حسابك الشخصي بنجاح مالي تام!")
        
        nxt = user_states[sender_phone].get('next_action')
        user_states[sender_phone] = {'step': 'transfer_amount', 'transfer_type': nxt}
        currency_from = get_currency_name(nxt)
        send_whatsapp_message(sender_phone, f"👇 الرجاء كتابة كمية *{currency_from}* التي تريد تحويلها (أرقام فقط):" + FOOTER)

    elif state == 'update_name':
        user_states[sender_phone]['new_name'] = msg_text
        user_states[sender_phone]['step'] = 'update_bank'
        send_whatsapp_message(sender_phone, "💳 ممتاز، يرجى كتابة *رقم حسابك البنكي الجديد* للتحديث:" + FOOTER)
        
    elif state == 'update_bank':
        new_bank = msg_text
        new_name = user_states[sender_phone]['new_name']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET full_name = %s, bank_account = %s WHERE user_id = %s", (new_name, new_bank, int(sender_phone)))
        conn.commit(); conn.close()
        del user_states[sender_phone]
        send_whatsapp_message(sender_phone, "✅ تم تحديث بياناتك الشخصية والبنكية بنجاح وأمان!" + FOOTER)

    elif state == 'write_review':
        stars = user_states[sender_phone]['stars']
        comment = msg_text
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO reviews (user_id, stars, comment) VALUES (%s, %s, %s)', (int(sender_phone), stars, comment))
        conn.commit(); conn.close()
        del user_states[sender_phone]
        send_whatsapp_message(sender_phone, "❤️ شكرًا جزيلاً لك على مشاركتنا تقييمك الجميل وتجربتك الموثوقة معنا!" + FOOTER)

    elif state == 'transfer_amount':
        try:
            amount = float(msg_text)
            choice = user_states[sender_phone]['transfer_type']
            settings = get_bot_settings()
            
            if choice == "1": rate, dest, c_type = settings['aed_price_sdg'], "SDG", "AED"
            elif choice == "2": rate, dest, c_type = settings['aed_price_egp'], "EGP", "AED"
            elif choice == "3": rate, dest, c_type = settings['sar_price_sdg'], "SDG", "SAR"
            elif choice == "4": rate, dest, c_type = settings['sar_price_egp'], "EGP", "SAR"
            elif choice == "5": rate, dest, c_type = settings['egp_sell_price'], "SDG", "EGP"
            elif choice == "6": rate, dest, c_type = settings['egp_buy_price'], "EGP", "BUY_EGP"
            
            if choice == "6":
                total_sdg_to_pay = amount * rate
                total_receive = amount
                msg = f"🔄 أنت تريد شحن: {amount} جنيه مصري\nالمطلوب دفعه: *{total_sdg_to_pay} جنيه سوداني*\n\n👇 الرجاء كتابة *رقم إنستاباي أو فودافون كاش* الذي تريد الاستلام عليه في مصر:"
            else:
                total_receive = amount * rate
                currency_name = "جنيه سوداني" if dest == "SDG" else "جنيه مصري"
                
                if dest == "SDG":
                    user_info = is_user_registered(sender_phone)
                    saved_bank = user_info[1] if user_info else "غير مسجل"
                    msg = f"الكمية المرسلة: {amount} {c_type}\nتستلم في السودان: *{total_receive} {currency_name}*\n\nحسابك المسجل في بنكك هو: {saved_bank}\n\nأرسل *1* للاستلام عليه، أو اكتب رقم واسم الحساب الجديد إذا أردت تغييره:"
                else:
                    msg = f"الكمية المرسلة: {amount} {c_type}\nتستلم في مصر: *{total_receive} {currency_name}*\n\n👇 الرجاء كتابة *رقم إنستاباي أو فودافون كاش* الذي تريد الاستلام عليه في مصر:"
            
            user_states[sender_phone].update({'amount': amount, 'total_receive': total_receive, 'rate': rate, 'dest': dest, 'c_type': c_type, 'step': 'transfer_bank'})
            if choice == "6": user_states[sender_phone]['total_sdg_to_pay'] = total_sdg_to_pay
            
            send_whatsapp_message(sender_phone, msg + FOOTER)
        except:
            send_whatsapp_message(sender_phone, "⚠️ أرقام فقط من فضلك." + FOOTER)

    elif state == 'transfer_bank':
        dest = user_states[sender_phone]['dest']
        if dest == "SDG" and msg_text == "1":
            user_info = is_user_registered(sender_phone)
            client_bank = user_info[1]
        else:
            client_bank = msg_text
            
        user_states[sender_phone]['client_bank'] = client_bank
        user_states[sender_phone]['step'] = 'transfer_confirm'
        
        confirm_msg = (
            "⚠️ *تأكيد هام جداً قبل تحويل الأموال:*\n\n"
            "هل المبلغ متوفر بالكامل وجاهز في حسابك للتحويل الفوري الآن؟\n\n"
            "⏱️ (بمجرد تزويدك بالحساب من قبل الإدارة، ستكون نافذة الدفع صالحة لمدة *30 دقيقة* فقط كحد أقصى، وبعدها قد تتغير الأسعار أو يُلغى الطلب تلقائياً لضمان الشفافية).\n\n"
            "👉 أرسل كلمة *نعم* للتأكيد وبدء المعالجة، أو أرسل *0* للإلغاء."
        )
        send_whatsapp_message(sender_phone, confirm_msg + FOOTER)

    elif state == 'transfer_confirm':
        if msg_text.strip() == "نعم":
            order = user_states[sender_phone]
            choice = order['transfer_type']
            
            if choice == "1": o_type = "SELL_AED_SDG"
            elif choice == "2": o_type = "SELL_AED_EGP"
            elif choice == "3": o_type = "SELL_SAR_SDG"
            elif choice == "4": o_type = "SELL_SAR_EGP"
            elif choice == "5": o_type = "SELL_EGP_SDG"
            elif choice == "6": o_type = "BUY_EGP"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if choice == "6":
                cursor.execute('''INSERT INTO orders (user_id, order_type, amount, total_sdg, wallet_address, status, platform) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING order_id''', (int(sender_phone), o_type, order['amount'], order['total_sdg_to_pay'], f"مصري: {order['client_bank']}", 'AWAITING_ACCOUNT', 'whatsapp'))
            else:
                cursor.execute('''INSERT INTO orders (user_id, order_type, amount, total_sdg, wallet_address, status, platform) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING order_id''', (int(sender_phone), o_type, order['amount'], order['total_sdg'], f"بنك العميل: {order['client_bank']}", 'AWAITING_ACCOUNT', 'whatsapp'))
                 
            order_id = cursor.fetchone()[0]
            conn.commit(); conn.close()
            
            user_info = is_user_registered(sender_phone)
            full_name = user_info[0] if user_info else "غير مسجل"
            
            send_whatsapp_message(sender_phone, "🕒 *تم تأكيد طلبك بنجاح، والآن نقوم بتهيئة مسار الدفع...*\n\nالرجاء الانتظار قليلاً، نقوم حالياً بتجهيز وتخصيص حساب بنكك الآمن لتتمكن من التحويل إليه بشكل مضمون ماليًا..." + FOOTER)
            
            pay_amount = order.get('total_sdg_to_pay') if choice == "6" else order['amount']
            receive_amount = order['amount'] if choice == "6" else order['total_receive']
            
            admin_alert = f"🚨 *حوالة جديدة (واتساب)!* `#{order_id}`\n\n👤 العميل: `{full_name}`\n📱 الهاتف: `+{sender_phone}`\n🔗 [💬 تواصل مع العميل](https://wa.me/{sender_phone})\n\nالنوع: `{o_type}`\nالمطلوب من العميل دفعه: `{pay_amount}`\nالاستلام للعميل: `{receive_amount}`\nحساب العميل: `{order['client_bank']}`\n\nاضغط الزر لتزويده بالحساب:"
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            reply_markup = {"inline_keyboard": [[{"text": "🔒 قفل الطلب وبدء التنفيذ", "callback_data": f"lock_order_{order_id}"}], [{"text": "💳 إرسال بيانات الدفع للعميل", "callback_data": f"provide_account_{order_id}"}]]}
            payload = {'chat_id': ADMIN_ID, 'text': admin_alert, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
            requests.post(url, json=payload)
            
            del user_states[sender_phone]
        else:
            send_whatsapp_message(sender_phone, "⚠️ يرجى التأكيد بإرسال كلمة (نعم) أو الإلغاء بإرسال 0." + FOOTER)

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