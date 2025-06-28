import re
from urllib.parse import urlparse
from pyrofork.errors import *
from pyrofork import Client, filters, errors, enums
from pyrofork.enums import ChatMemberStatus
from pyrofork.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, User
import json, math
from functools import partial
import random,asyncio
import os,sqlite3
import traceback
import itertools
from pyrofork import errors as pg_errors

#=======مجلد الجهات=======
VCF_DIR = "vcf_files"
if not os.path.exists(VCF_DIR):
    os.makedirs(VCF_DIR)

# انشاء مجلد قاعدة البيانات
DATABASE_DIR = "database"
if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)


# ملف JSON لتخزين المعرفات داخل مجلد vcf_files  
bot = Client("my_bot", api_id=27535729, api_hash="0725649506c2f7083ebdb9ad437b0aaa", bot_token="7673276959:AAEgZtIx6EMVQpv239ubyhhvHh60FcvTwcM")
STOP_ADD = False
  # Initialize the set to track blocked users
EXPECTING_JSON = set()

# ملف تخزين الاعضاء داخل members.json
MEMBERS_JSON = os.path.join(DATABASE_DIR, "members.json")
if not os.path.exists(MEMBERS_JSON):
    with open(MEMBERS_JSON, "w", encoding="utf-8") as f:
        json.dump({"add_members": [], "admins": [], "bots": []}, f, ensure_ascii=False, indent=4)


# دالة تشغيل البوت
@bot.on_message(filters.command("stop_add") & filters.user(Config.OWNER_ID))
async def stop_add_handler(client, message):
    global STOP_ADD
    STOP_ADD = True
    await bot.send_message(Config.OWNER_ID, "🛑 تم إيقاف عملية الإضافة.")

class database:
    def __init__(self) :
        if not os.path.isfile("database/data.db"):
            with sqlite3.connect("database/data.db") as connection:
                cursor = connection.cursor()
                cursor.execute("CREATE TABLE IF NOT EXISTS accounts (ses TEXT,number TEXT,id TEXT)")
                connection.commit()
        os.makedirs("database", exist_ok=True)
        self.db_path = "database/data.db"
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            # existing table
            cur.execute("CREATE TABLE IF NOT EXISTS accounts (ses TEXT, number TEXT, id TEXT)")
            # new table for vcf filenames
            cur.execute("CREATE TABLE IF NOT EXISTS vcffiles (filename TEXT)")
            conn.commit()

# New: generate vcf content helper
        
    def AddAcount(self,ses,numbers,id):
        with sqlite3.connect("database/data.db") as connection:
            cursor = connection.cursor()
            cursor.execute(f"INSERT INTO accounts VALUES ('{ses}','{numbers}','{id}')")
            connection.commit()

    def RemoveAllAccounts(self):
        with sqlite3.connect("database/data.db") as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM accounts")
            connection.commit()

    def RemoveAccount(self, numbers):
        with sqlite3.connect("database/data.db") as connection:
            cursor = connection.cursor()
            cursor.execute(f"DELETE FROM accounts WHERE number = '{numbers}' ")
            connection.commit()
    
    def accounts(self):
        list = []
        with sqlite3.connect("database/data.db") as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM accounts")	
            entry = cursor.fetchall()
            for i in entry:
                list.append([i[0],i[1]])
        return list
    def AddBackupAcount(self,ses,numbers,id):
        with sqlite3.connect("database/data.db") as connection:
            cursor = connection.cursor()
            cursor.execute(f"INSERT INTO accounts VALUES ('{ses}','{numbers}','{id}')")
            connection.commit()
    def backupaccounts(self):
        list = []
        with sqlite3.connect("database/data.db") as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM accounts")	
            entry = cursor.fetchall()
            for i in entry:
                list.append(i)
        return list

async def list_vcf_pages(call, page: int = 0):
    files = [f for f in os.listdir(VCF_DIR) if os.path.isfile(os.path.join(VCF_DIR, f))]
    if not files:
        return await call.message.edit_text(
            "لا يوجد ملفات للحذف.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
            )
        )

    per_page = 14  # 7 صفوف × 2 أعمدة
    total_pages = math.ceil(len(files) / per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    page_files = files[start : start + per_page]

    buttons = []
    # عرض الملفات بعمودين
    for i in range(0, len(page_files), 2):
        row = []
        fname = page_files[i]
        row.append(InlineKeyboardButton(fname, callback_data=f"ask_delete:{fname}"))
        if i + 1 < len(page_files):
            fname2 = page_files[i+1]
            row.append(InlineKeyboardButton(fname2, callback_data=f"ask_delete:{fname2}"))
        buttons.append(row)

    # أزرار التنقل
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⏮️ السابق", callback_data=f"del_json_page:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ⏭️", callback_data=f"del_json_page:{page+1}"))
    if nav:
        buttons.append(nav)

    # زر الرجوع
    buttons.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="back")
    ])

    await call.message.edit_text(
        "اختر الملف لحذفه:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
async def list_exp_pages(call, page: int = 0):
    """
    Lists VCF files in pages and displays inline keyboard for selection.
    """
    files = [f for f in os.listdir(VCF_DIR) if os.path.isfile(os.path.join(VCF_DIR, f))]
    if not files:
        return await call.message.edit_text(
            "لا يوجد ملفات للاستخراج.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
            )
        )

    per_page = 14  # 7 rows x 2 columns
    total_pages = math.ceil(len(files) / per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    page_files = files[start:start + per_page]

    buttons = []
    # عرض الملفات بعمودين
    for i in range(0, len(page_files), 2):
        row = []
        fname = page_files[i]
        row.append(InlineKeyboardButton(fname, callback_data=f"extract_file:{fname}"))
        if i + 1 < len(page_files):
            fname2 = page_files[i+1]
            row.append(InlineKeyboardButton(fname2, callback_data=f"extract_file:{fname2}"))
        buttons.append(row)

    # أزرار التنقل بين الصفحات
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⏮️ السابق", callback_data=f"extract_json_page:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ⏭️", callback_data=f"extract_json_page:{page+1}"))
    if nav:
        buttons.append(nav)

    # زر الرجوع
    buttons.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="back")
    ])

    await call.message.edit_text(
        "اختر الملف لاستخراجه:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def show_clear_accounts(call, current_page: int):
    acs = database().accounts()  # قائمة [(session_string, number), …]
    buttons_per_page = 14  # 7 صفوف × عمودين
    buttons = []

    # بناء أزرار الحسابات
    for ses, num in acs:
        label = f"الرقم: {num}"
        data  = f"clear_exec:{ses}"
        buttons.append(InlineKeyboardButton(label, callback_data=data))

    # تقسيم الأزرار إلى صفحات
    pages = [buttons[i : i + buttons_per_page] for i in range(0, len(buttons), buttons_per_page)]
    # تحقّق من وجود صفحة
    if not pages or current_page < 0 or current_page >= len(pages):
        return await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text="*لا توجد حسابات حالياً.*",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("رجوع 🛎", callback_data="back")]]
            )
        )

    # أزرار التنقل
    nav = []
    if current_page > 0:
        nav.append(InlineKeyboardButton("السابق ◀️", callback_data=f"page_clear-{current_page-1}"))
    if current_page < len(pages) - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"page_clear-{current_page+1}"))
    nav.append(InlineKeyboardButton("رجوع 🛎", callback_data="back"))

    # ترتيب الأزرار في صفّين
    page_buttons = pages[current_page]
    keyboard = [page_buttons[i:i+2] for i in range(0, len(page_buttons), 2)]
    keyboard.append(nav)

    await bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.id,
        text="*اختر الحساب لمسح جهاته:*",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # أزرار التنقل
    nav = []
    if current_page > 0:
        nav.append(InlineKeyboardButton("السابق ◀️", callback_data=f"page_clear-{current_page-1}"))
    if current_page < len(pages) - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"page_clear-{current_page+1}"))
    nav.append(InlineKeyboardButton("رجوع 🛎", callback_data="back"))

    # ترتيب الأزرار في صفّين
    page_buttons = pages[current_page]
    keyboard = [ page_buttons[i:i+2] for i in range(0, len(page_buttons), 2) ]
    keyboard.append(nav)

    await bot.edit_message_text(
        call.message.chat.id,
        call.message.message_id,
        "*اختر الحساب لمسح جهاته:*",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
class Custem :
    async def add_users_contact(self, group_link: str, bot: Client, nmcount: int):
        """
        إضافة جميع جهات الاتصال من كل حساب إلى مجموعة واحدة دفعة واحدة.
        يتوقف عند إيقاف يدوي أو الوصول للعدد المطلد.
        لكل حساب حد 50 إضافة و7 إخفاقات.
        تقسيم المستخدمين إلى:
          - add_users: سيتم إضافتهم
          - not_add_users: موجودين مسبقًا
          - privacy_blocked: خصوصية تمنعهم
        وتتبع الحد اليومي لكل حساب.
        """
        global STOP_ADD
        STOP_ADD = False
    
        total_to_add = nmcount
        total_added = 0
        total_failed = 0
        initial_count = None
        final_count = None
        session_success = False
    
        # استخراج chat_id من الرابط
        chat_id = group_link.split("/")[-1]
    
        # جلب الحسابات
        accounts = database().accounts()  # قائمة tuples: (session_string, account_label)
        if not accounts:
            return await bot.send_message(
                Config.OWNER_ID,
                "❌ لا توجد حسابات متاحة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
            )
    
        daily_limit = 50
        daily_counts = {}
        blocked_accounts = set()
        total_accounts = len(accounts)
    
        add_users = set()
        not_add_users = set()
        privacy_blocked = set()
        tried_users = set()
    
        index = 0  # مؤشر الحساب الحالي
    
        # ابدأ الدورة الحسابيّة
        while not STOP_ADD and total_added < total_to_add:
            ses_str, account_label = accounts[index]
            index = (index + 1) % total_accounts  # للعودة أوتوماتيكيًا للبداية
    
            # تجاهل إذا وصل حد الحساب اليومي أو محظور
            used_today = daily_counts.get(account_label, 0)
            if used_today >= daily_limit or account_label in blocked_accounts:
                continue
    
            account_added = 0
            session_success = False
    
            # تسجيل الدخول
            try:
                client_app = Client(
                    ":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                    session_string=ses_str, no_updates=True, in_memory=True, lang_code="ar"
                )
                await client_app.start()
                session_success = True
            except Exception as login_err:
                total_failed += 1
                await bot.send_message(
                    Config.OWNER_ID,
                    f"❌ فشل تسجيل الدخول للحساب {account_label}:\n{login_err}"
                )
                continue
    
            try:
                # انضمام للمجموعة (مرة واحدة)
                try:
                    await asyncio.sleep( random.randint(1, 3) )
                    await client_app.join_chat(chat_id)
                except errors.UserAlreadyParticipant:
                    pass
                except errors.InviteRequestSent:
                    total_failed += 1
                    blocked_accounts.add(account_label)
                    await bot.send_message(
                        Config.OWNER_ID,
                        f"تم إرسال طلب انضمام بحساب {account_label} للمجموعة"
                    )
                    continue
                except Exception as join_err:
                    total_failed += 1
                    await bot.send_message(
                        Config.OWNER_ID,
                        f"⚠️ خطأ في الانضمام بالقروب ({account_label}):\n{join_err}"
                    )
                    continue
    
                # حفظ عدد الأعضاء الابتدائي
                if initial_count is None:
                    initial_count = (await client_app.get_chat(chat_id)).members_count
    
                # جلب جهات الاتصال وتصفيتها
                contacts = await client_app.get_contacts()
                for u in contacts:
                    if not u.username:
                        continue
                    common = await client_app.get_common_chats(u.username)
                    if any(str(c.id) == chat_id for c in common):
                        not_add_users.add(u.username)
                    else:
                        add_users.add(u.username)
    
                # حساب كم يمكن إضافته اليوم
                remaining = min(daily_limit - used_today, total_to_add - total_added)
                to_add = [u for u in add_users if u not in tried_users][:remaining]
    
                # عملية الإضافة
                for username in to_add:
                    if STOP_ADD or total_added >= total_to_add:
                        break
                    tried_users.add(username)
                    try:
                        await asyncio.sleep(random.randint(1, 3))
                        await client_app.add_chat_members(chat_id, username)
                        # تحقق عبر البوت
                        await bot.get_chat_member(chat_id, username)
                        total_added += 1
                        account_added += 1
                        daily_counts[account_label] = daily_counts.get(account_label, 0) + 1
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"✅ إضافة @{username} بواسطة {account_label}"
                        )
                    except (errors.UserPrivacyRestricted, errors.UserNotMutualContact) as priv_err:
                        total_failed += 1
                        privacy_blocked.add(username)
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"⚠️ خصوصية تمنع إضافة @{username}"
                        )
                    except errors.FloodWait as e:
                        total_failed += 1
                       
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"⏳ {account_label} محظور {e.value} ثانية"
                        )
                        break
                    except errors.PeerFlood:
                        total_failed += 1
                        blocked_accounts.add(account_label)
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"⏳ الحساب {account_label} متقيّد حالياً"
                        )
                        
                        break
                    except errors.UserBannedInChannel:
                        total_failed += 1
                        blocked_accounts.add(account_label)
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"⏳ الحساب {account_label} متقيد من تيليجرام قم يالتحقق من الحساب من بوت تيليجرام @SpamBot" 
                        )
                        break
                    except Exception as err:
                        total_failed += 1
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"❌ خطأ إضافة @{username}:\n{err}"
                        )
    
                # تحديث العدد النهائي للحساب
                final_count = (await client_app.get_chat(chat_id)).members_count
    
            finally:
                await client_app.stop()
    
            # ملخص الحساب
            await bot.send_message(
                Config.OWNER_ID,
                f"📋 الحساب: {account_label} — ✅ إضافات: {account_added}"
            )
    
        # إذا لم تنجح أي جلسة
        if not session_success:
            return await bot.send_message(
                Config.OWNER_ID,
                "❌ لا توجد جلسات صالحة، رجاءً أعد إدخال الحسابات.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
            )
    
    
        # إحصائيات نهائية
        status = "🛑 تم الإيقاف يدويًا" if STOP_ADD else "✅ انتهاء الإضافة"
        await bot.send_message(
            Config.OWNER_ID,
            (
                f"{status}\n"
                "ᯓ 𓏺˛ SouRce MoNj .⚡️ - إشعـــــار النقل من الجهات ⛞\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                f"عدد الاضافات كامل: {total_added} عضو\n"
                f"عدد الاضافات الفاشله: {total_failed} عضو\n"
                f"اعضاء المجموعه قبل: {initial_count}\n"
                f"اعضاء المجموعه بعد: {final_count}\n"
                f"عدد الاضافات المحققه: {final_count - initial_count}\n"
                f"عدد الحسابات الموجودة: {total_accounts}\n"
                f"عدد الحسابات المحظورة: {len(blocked_accounts)}\n"
                f"عدد الحسابات النشطه: {total_accounts - len(blocked_accounts)}\n"
                f"مجموع الاضافات لكل الحسابات: {sum(daily_counts.values())}\n"
                f"عدد الاضافات المتبقية لكل الحسابات: {total_accounts * daily_limit - sum(daily_counts.values())}"
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
        )
    async def ask_limit(self, client, message, user_info: dict):
        try:
            user_id = message.from_user.id
            # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
            if user_id != Config.OWNER_ID and user_id not in Config.Devs:
                await message.message.reply(
                    "عذرا الأوامر ليست لك"
                )
            pass
            limit_value = int(message.text.strip())
        except ValueError:
            return await bot.send_message(
                message.chat.id,
                "⚠️ يرجى إدخال رقم صحيح للحد الأقصى"
            )
        user_info['limit'] = limit_value
        await bot.send_message(
            message.chat.id,
            "قم بارسال رابط القروب المراد إضافة الأعضاء له\n⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\nمثل:\n`https://t.me/Libya_15`",
        )
        # register next handler with limit included
        bot.register_next_step_handler(
            partial(statement2hide, user_info=user_info)
        )
    async def ADDuserhide(self, data, inGRob, grop2, bot: Client, nmcount):
        """
        إضافة مستخدمين مخفيين إلى مجموعة بشكل متكرر عبر الحسابات بعداد أقصى لكل حساب
        يتوقف فقط عند تفعيل STOP_ADD أو الوصول للعدد المطلوب
        ولا ينتقل للحساب التالي إلا عند الانتهاء من إضافة الحد اليومي أو وقوع خطأ FloodWait/PeerFlood
        يعرض كافة الأخطاء بصيغة شيل قابلة للنسخ
        على أي خطأ في الحساب يتم تخطيه واستكمال الحسابات الأخرى
        """
        global STOP_ADD
        STOP_ADD = False
    
        # === 0. إعداد متغيرات العدّ اليومي والمتتبعات ===
        daily_limit = 50
        daily_counts = {}                # عدد الإضافات لكل حساب في هذه الجلسة
        blocked_accounts = set()         # حسابات تجاوزت الحد اليومي أو تقيدت
        add_queue = []                   # قائمة الانتظار للإضافة (FIFO)
        privacy_blocked = set()          # المحظورون بالخصوصية
        not_add_users = set()            # الموجودون مسبقاً
    
        # === 1. قراءة وإعداد الحسابات ===
        raw_accounts = database().accounts()
        if not raw_accounts:
            return await bot.send_message(
                Config.OWNER_ID,
                "❌ لا توجد حسابات متاحة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
            )
    
        valid_accounts = []
        for session_str, account_label in raw_accounts:
            daily_counts[account_label] = 0
            try:
                test_client = Client(
                    ":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                    session_string=session_str, no_updates=True, in_memory=True, lang_code="ar"
                )
                await test_client.start()
                await test_client.stop()
                valid_accounts.append((session_str, account_label))
            except Exception as login_err:
                await bot.send_message(
                    Config.OWNER_ID,
                    f"⚠️ تخطي الحساب {account_label}؛ فشل تسجيل الدخول:\n```shell\n{login_err}```"
                )
    
        if not valid_accounts:
            return await bot.send_message(
                Config.OWNER_ID,
                "❌ لا توجد جلسات صالحة بعد اختبار الحسابات.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
            )
    
        total_accounts = len(valid_accounts)
    
        # === 2. إعداد ملف الأعضاء ===
        if not os.path.exists(MEMBERS_JSON):
            with open(MEMBERS_JSON, "w", encoding="utf-8") as f:
                json.dump({"add_members": []}, f, ensure_ascii=False, indent=4)
    
        # === 3. قراءة قائمة الأعضاء من الملف ===
        try:
            with open(MEMBERS_JSON, "r", encoding="utf-8") as f:
                members_data = json.load(f)
                raw_usernames = members_data.get("add_members", [])
        except Exception as e:
            return await bot.send_message(
                Config.OWNER_ID,
                f"❌ خطأ في قراءة الملف {MEMBERS_JSON}:\n```shell\n{e}```"
            )
    
        total_to_add = int(nmcount)
        total_added = 0
        total_failed = 0
        initial_count = None
        final_count = None
    
        inGRob = inGRob.split("/")[3]
        session_success = False
    
        # === 4. حلقة الإضافة الرئيسية ===
        # إعداد قائمة الانتظار أول مرة
        for username in raw_usernames:
            if username and username not in not_add_users and username not in privacy_blocked:
                add_queue.append(username)
    
        while not STOP_ADD and total_added < total_to_add:
            for session_str, account_label in valid_accounts:
                if STOP_ADD or total_added >= total_to_add:
                    break
    
                # تخطي الحسابات التي تجاوزت الحد اليومي أو المقيدة
                if daily_counts[account_label] >= daily_limit:
                    blocked_accounts.add(account_label)
                    continue
    
                account_added = 0
                client = None
    
                try:
                    client = Client(
                        ":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                        session_string=session_str, no_updates=True, in_memory=True, lang_code="ar"
                    )
                    await client.start()
                    session_success = True
    
                    # انضمام للمجموعتين
                    try:
                        await asyncio.sleep(random.randint(1, 3))
                        await client.join_chat(inGRob)
                 
                    except errors.InviteRequestSent:
                        total_failed += 1
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"تم ارسال طلب انضمام بالحساب {account_label} للقروبين بنجاح"
                        )
                        raise
                    except Exception as join_err:
                        total_failed += 1
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"⚠️ خطأ في انضمام الحساب {account_label} للقروبين:\n```shell\n{join_err}```"
                        )
                        raise
    
                    if initial_count is None:
                        initial_count = (await client.get_chat(inGRob)).members_count
    
                    # === 4.1: حل الإضافة اليومية من قائمة الانتظار ===
                    while (
                        not STOP_ADD
                        and total_added < total_to_add
                        and account_added < (daily_limit - daily_counts[account_label])
                        and add_queue
                    ):
                        username = add_queue.pop(0)
                        try:
                            await asyncio.sleep(random.randint(1, 3))
                            # محاولة الإضافة مع تحقق سريع
                            await client.add_chat_members(inGRob, username)
                            await bot.get_chat_member(inGRob, username)
                            # إضافة ناجحة
                            total_added += 1
                            account_added += 1
                            daily_counts[account_label] += 1
                            not_add_users.add(username)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"✅ إضافة ناجحة بواسطة: {account_label} - @{username}"
                            )
                        except errors.UserPrivacyRestricted:
                            total_failed += 1
                            privacy_blocked.add(username)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"⚠️ خصوصية المستخدم تمنع الاضافة: @{username}"
                            )
                        except errors.FloodWait as e:
                            total_failed += 1
                            
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"⏳ الحساب {account_label} محظور مؤقتاً: {e.value} ثانية"
                            )
                            break
                        except errors.PeerFlood:
                            total_failed += 1
                            blocked_accounts.add(account_label)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"⏳ الحساب {account_label} متقيد حالياً"
                            )
                            break
                        except errors.UserBannedInChannel:
                            total_failed += 1
                            blocked_accounts.add(account_label)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"⏳ الحساب {account_label} متقيد من تيليجرام قم يالتحقق من الحساب من بوت تيليجرام @SpamBot" 
                            )
                            break
                        except Exception as add_err:
                            total_failed += 1
                            # سجل الخطأ وأعد وضع المستخدم في قائمة الانتظار للمحاولة لاحقاً
                            add_queue.append(username)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"❌ خطأ عند إضافة @{username} عبر {account_label}:\n```shell\n{add_err}```"
                            )
                        finally:
                            # لا إعادة الإضافة إذا نجح أو خصوصية أو مستخدم مسبق
                            pass
    
                    final_count = (await client.get_chat(inGRob)).members_count
    
                except Exception:
                    continue
    
                finally:
                    if client:
                        await client.stop()
    
                # تقرير عن الحساب
                await bot.send_message(
                    Config.OWNER_ID,
                    f"📋 الحساب: {account_label}\n✅ إضافات اليوم: {account_added}"
                )
    
            # عند انتهاء الدورة، يستأنف من الحساب الأول إذا لم يتم الإيقاف
            # while سيعيد التنفيذ تلقائياً
    
        if not session_success:
            return await bot.send_message(
                Config.OWNER_ID,
                "❌ لا توجد جلسات صالحة، يرجى إعادة إدخال الحسابات.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
            )
    
        # === 5. إرسال الإحصائيات النهائية ===
        status = "🛑 تم الإيقاف يدوياً" if STOP_ADD else "✅ انتهاء الإضافة"
        await bot.send_message(
            Config.OWNER_ID,
            (
                f"ᯓ 𓏺˛ SouRce MoNj .⚡️ - إحصــائيات النقل المــخفي {status} ⛞\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                f"عدد الاضافات كامل: {total_added} عضو\n"
                f"عدد الاضافات الفاشله: {total_failed} عضو\n"
                f"اعضاء المجموعة قبل: {initial_count}\n"
                f"اعضاء المجموعة بعد: {final_count}\n"
                f"مجموع الاضافات لكل الحسابات: {sum(daily_counts.values())}\n"
                f"عدد الحسابات: {total_accounts}\n"
                f"محظورة: {len(blocked_accounts)}\n"
                f"نشطة: {total_accounts - len(blocked_accounts)}\n"
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
        )
    
    
    
    
    async def ADDuser(self, inGRob, grop2, bot: Client, nmcount):
        """
        إضافة مستخدمين مخفيين إلى مجموعة بشكل متكرر عبر الحسابات بعداد أقصى لكل حساب
        يتوقف فقط عند تفعيل STOP_ADD أو الوصول للعدد المطلوب
        ولا ينتقل للحساب التالي إلا عند الانتهاء من إضافة الحد اليومي أو وقوع خطأ FloodWait/PeerFlood
        يعرض كافة الأخطاء بصيغة شيل قابلة للنسخ
        على أي خطأ في الحساب يتم تخطيه واستكمال الحسابات الأخرى
        """
        global STOP_ADD
        STOP_ADD = False
    
        # === 0. إعداد متغيرات العدّ اليومي والمتتبعات ===
        daily_limit = 50
        daily_counts = {}                # عدد الإضافات لكل حساب في هذه الجلسة
        blocked_accounts = set()         # حسابات تجاوزت الحد اليومي أو تقيدت
        add_queue = []                   # قائمة الانتظار للإضافة (FIFO)
        privacy_blocked = set()          # المحظورون بالخصوصية
        not_add_users = set()            # الموجودون مسبقاً
    
        # === 1. قراءة وإعداد الحسابات ===
        raw_accounts = database().accounts()
        if not raw_accounts:
            return await bot.send_message(
                Config.OWNER_ID,
                "❌ لا توجد حسابات متاحة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
            )
    
        valid_accounts = []
        for session_str, account_label in raw_accounts:
            daily_counts[account_label] = 0
            try:
                test_client = Client(
                    ":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                    session_string=session_str, no_updates=True, in_memory=True, lang_code="ar"
                )
                await test_client.start()
                await test_client.stop()
                valid_accounts.append((session_str, account_label))
            except Exception as login_err:
                await bot.send_message(
                    Config.OWNER_ID,
                    f"⚠️ تخطي الحساب {account_label}؛ فشل تسجيل الدخول:\n```shell\n{login_err}```"
                )
    
        if not valid_accounts:
            return await bot.send_message(
                Config.OWNER_ID,
                "❌ لا توجد جلسات صالحة بعد اختبار الحسابات.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
            )
    
        total_accounts = len(valid_accounts)
    
        # === 2. إعداد ملف الأعضاء ===
        if not os.path.exists(MEMBERS_JSON):
            with open(MEMBERS_JSON, "w", encoding="utf-8") as f:
                json.dump({"add_members": []}, f, ensure_ascii=False, indent=4)
    
        # === 3. قراءة قائمة الأعضاء من الملف ===
        try:
            with open(MEMBERS_JSON, "r", encoding="utf-8") as f:
                members_data = json.load(f)
                raw_usernames = members_data.get("add_members", [])
        except Exception as e:
            return await bot.send_message(
                Config.OWNER_ID,
                f"❌ خطأ في قراءة الملف {MEMBERS_JSON}:\n```shell\n{e}```"
            )
    
        total_to_add = int(nmcount)
        total_added = 0
        total_failed = 0
        initial_count = None
        final_count = None
    
        inGRob = inGRob.split("/")[3]
        session_success = False
    
        # === 4. حلقة الإضافة الرئيسية ===
        # إعداد قائمة الانتظار أول مرة
        for username in raw_usernames:
            if username and username not in not_add_users and username not in privacy_blocked:
                add_queue.append(username)
    
        while not STOP_ADD and total_added < total_to_add:
            for session_str, account_label in valid_accounts:
                if STOP_ADD or total_added >= total_to_add:
                    break
    
                # تخطي الحسابات التي تجاوزت الحد اليومي أو المقيدة
                if daily_counts[account_label] >= daily_limit:
                    blocked_accounts.add(account_label)
                    continue
    
                account_added = 0
                client = None
    
                try:
                    client = Client(
                        ":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                        session_string=session_str, no_updates=True, in_memory=True, lang_code="ar"
                    )
                    await client.start()
                    session_success = True
    
                    # انضمام للمجموعتين
                    try:
                        await asyncio.sleep(random.randint(1, 3))
                        await client.join_chat(inGRob)
                 
                    except errors.InviteRequestSent:
                        total_failed += 1
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"تم ارسال طلب انضمام بالحساب {account_label} للقروبين بنجاح"
                        )
                        raise
                    except Exception as join_err:
                        total_failed += 1
                        await bot.send_message(
                            Config.OWNER_ID,
                            f"⚠️ خطأ في انضمام الحساب {account_label} للقروبين:\n```shell\n{join_err}```"
                        )
                        raise
    
                    if initial_count is None:
                        initial_count = (await client.get_chat(inGRob)).members_count
    
                    # === 4.1: حل الإضافة اليومية من قائمة الانتظار ===
                    while (
                        not STOP_ADD
                        and total_added < total_to_add
                        and account_added < (daily_limit - daily_counts[account_label])
                        and add_queue
                    ):
                        username = add_queue.pop(0)
                        try:
                            await asyncio.sleep(random.randint(1, 3))
                            # محاولة الإضافة مع تحقق سريع
                            await client.add_chat_members(inGRob, username)
                            await bot.get_chat_member(inGRob, username)
                            # إضافة ناجحة
                            total_added += 1
                            account_added += 1
                            daily_counts[account_label] += 1
                            not_add_users.add(username)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"✅ إضافة ناجحة بواسطة: {account_label} - @{username}"
                            )
                        except errors.UserPrivacyRestricted:
                            total_failed += 1
                            privacy_blocked.add(username)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"⚠️ خصوصية المستخدم تمنع الاضافة: @{username}"
                            )
                        except errors.FloodWait as e:
                            total_failed += 1
                           
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"⏳ الحساب {account_label} محظور مؤقتاً: {e.value} ثانية"
                            )
                            break
                        except errors.PeerFlood:
                            total_failed += 1
                            blocked_accounts.add(account_label)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"⏳ الحساب {account_label} متقيد حالياً"
                            )
                            break
                        except errors.UserBannedInChannel:
                            total_failed += 1
                            blocked_accounts.add(account_label)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"⏳ الحساب {account_label} متقيد من تيليجرام قم يالتحقق من الحساب من بوت تيليجرام @SpamBot" 
                            )
                            break
                        except Exception as add_err:
                            total_failed += 1
                            # سجل الخطأ وأعد وضع المستخدم في قائمة الانتظار للمحاولة لاحقاً
                            add_queue.append(username)
                            await bot.send_message(
                                Config.OWNER_ID,
                                f"❌ خطأ عند إضافة @{username} عبر {account_label}:\n```shell\n{add_err}```"
                            )
                        finally:
                            # لا إعادة الإضافة إذا نجح أو خصوصية أو مستخدم مسبق
                            pass
    
                    final_count = (await client.get_chat(inGRob)).members_count
    
                except Exception:
                    continue
    
                finally:
                    if client:
                        await client.stop()
    
                # تقرير عن الحساب
                await bot.send_message(
                    Config.OWNER_ID,
                    f"📋 الحساب: {account_label}\n✅ إضافات اليوم: {account_added}"
                )
    
            # عند انتهاء الدورة، يستأنف من الحساب الأول إذا لم يتم الإيقاف
            # while سيعيد التنفيذ تلقائياً
    
        if not session_success:
            return await bot.send_message(
                Config.OWNER_ID,
                "❌ لا توجد جلسات صالحة، يرجى إعادة إدخال الحسابات.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
            )
    
        # === 5. إرسال الإحصائيات النهائية ===
        status = "🛑 تم الإيقاف يدوياً" if STOP_ADD else "✅ انتهاء الإضافة"
        await bot.send_message(
            Config.OWNER_ID,
            (
                f"ᯓ 𓏺˛ SouRce MoNj .⚡️ - إحصــائيات النقل الظـــاهر {status} ⛞\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                f"عدد الاضافات كامل: {total_added} عضو\n"
                f"عدد الاضافات الفاشله: {total_failed} عضو\n"
                f"اعضاء المجموعة قبل: {initial_count}\n"
                f"اعضاء المجموعة بعد: {final_count}\n"
                f"مجموع الاضافات لكل الحسابات: {sum(daily_counts.values())}\n"
                f"عدد الحسابات: {total_accounts}\n"
                f"محظورة: {len(blocked_accounts)}\n"
                f"نشطة: {total_accounts - len(blocked_accounts)}\n"
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
        )
    
    
    
    
    async def add_users_hide(self, group_link: str, bot: Client, nmcount: int):
        """
        إضافة مستخدمين مخفيين إلى مجموعة معينة مع:
        - تقسيم الأعضاء إلى ثلاث مجموعات: للإضافة، ممنوعين بالخصوصية، وموجودين مسبقاً.
        - حد يومي لكل حساب بواقع 50 إضافة، ويتم التتبع عبر ملف JSON حتى عند إعادة تشغيل الأمر.
        - تخطي الحساب عند حدوث FloodWait أو PeerFlood ووضعه في قائمة المحظورين.
        - لا يتوقف إلا بإيقاف يدوي.
        """
    
        global STOP_ADD
        STOP_ADD = False
    
        # === 0. إعداد تتبع الإضافات اليومية ===
        import os, json, datetime, asyncio
        import random
    
        daily_limit = 50
        today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        counts_file = "daily_counts.json"
    
        # تحميل العدادات
        if os.path.exists(counts_file):
            with open(counts_file, "r") as f:
                all_counts = json.load(f)
        else:
            all_counts = {}
        # إعادة تعيين يوم جديد
        if today_str not in all_counts:
            all_counts = {today_str: {}}
        daily_counts = all_counts[today_str]
    
        blocked_accounts = set()       # حسابات تعرضت لـFlood/PeerFlood اليوم
        add_users = set()             # الأعضاء الذين سنتحقق منهم للإضافة
        privacy_blocked = set()       # الأعضاء المحجوبين بالخصوصية
        not_add_users = set()         # الأعضاء المنضمين مسبقاً
    
        # === 1. جلب الأعضاء والحسابات ===
        members_list = await self.get_users_saved()
        total_to_add = nmcount
        total_added = 0
        total_failed = 0
        username_index = 0
    
        accounts = database().accounts()
        total_accounts = len(accounts)
        if not accounts:
            return await bot.send_message(
                Config.OWNER_ID,
                "❌ لا توجد حسابات متاحة للإضافة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
            )
    
        chat_id = group_link.split("/")[-1]
    
        # === 2. الحصول على عدد الأعضاء الابتدائي ===
        tmp = Client(":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                     session_string=accounts[0][0], no_updates=True, in_memory=True, lang_code="ar")
        await tmp.start()
        initial_count = (await tmp.get_chat(chat_id)).members_count
        await tmp.stop()
    
        # === 3. حلقة الإضافة الرئيسية بتتابع حسابي منتظم ===
        account_index = 0
        while not STOP_ADD and total_added < total_to_add:
            # تدوير قائمة الأسماء
            if username_index >= len(members_list):
                username_index = 0
            username = members_list[username_index]
            username_index += 1
            if not username:
                total_failed += 1
                continue
    
            # البحث عن الحساب التالي المتاح
            chosen = None
            for _ in range(total_accounts):
                session_str, account_label = accounts[account_index]
                account_index = (account_index + 1) % total_accounts
                if daily_counts.get(account_label, 0) < daily_limit and account_label not in blocked_accounts:
                    chosen = (session_str, account_label)
                    break
            if not chosen:
                # لا حسابات متاحة
                break
            session_str, account_label = chosen
    
            # تسجيل الدخول
            try:
                client = Client(":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                                session_string=session_str, no_updates=True, in_memory=True, lang_code="ar")
                await client.start()
            except Exception as login_err:
                total_failed += 1
                await bot.send_message(Config.OWNER_ID,
                                       f"❌ فشل تسجيل الدخول للحساب {account_label}:\n```shell\n{login_err}\n```")
                continue
    
            # فحص المجموعات المشتركة
            try:
                common = await client.get_common_chats(username)
                if any(c.id == int(chat_id) for c in common):
                    not_add_users.add(username)
                    await client.stop()
                    continue
                add_users.add(username)
            except Exception:
                add_users.add(username)
    
            # الانضمام للقروب إذا لزم
            try:
                await asyncio.sleep(random.randint(1, 3))
                await client.join_chat(chat_id)
            except errors.UserAlreadyParticipant:
                pass
            except Exception as join_err:
                total_failed += 1
                await bot.send_message(Config.OWNER_ID,
                                       f"⚠️ فشل انضمام الحساب {account_label} للقروب:\n```shell\n{join_err}\n```")
                await client.stop()
                continue
    
            # محاولة إضافة العضو
            try:
                await asyncio.sleep(random.randint(1, 3))
                await client.add_chat_members(chat_id, username)
                total_added += 1
                # تحديث العداد اليومي وحفظه
                daily_counts[account_label] = daily_counts.get(account_label, 0) + 1
                all_counts[today_str] = daily_counts
                with open(counts_file, "w") as f:
                    json.dump(all_counts, f)
                await bot.send_message(Config.OWNER_ID,
                                       f"✅ إضافة ناجحة\nبواسطة: {account_label}\nمعرف العضو: @{username}")
                not_add_users.add(username)
            except errors.UserPrivacyRestricted:
                total_failed += 1
                privacy_blocked.add(username)
                await bot.send_message(Config.OWNER_ID,
                                       f"⚠️ خصوصية المستخدم تمنع الاضافة: @{username}")
            except errors.UserNotMutualContact:
                total_failed += 1
                await bot.send_message(Config.OWNER_ID,
                                       f"⚠️ الحساب لا يضيف إلا جهات اتصال مشتركة: {account_label}")
            except errors.FloodWait as e:
                total_failed += 1
                blocked_accounts.add(account_label)
                wait_time = getattr(e, "value", 30000)
                await bot.send_message(Config.OWNER_ID,
                                       f"⏳ الحساب {account_label} محظور مؤقتاً لمدة {wait_time} ثانية")
            except errors.PeerFlood:
                total_failed += 1
                blocked_accounts.add(account_label)
                await bot.send_message(Config.OWNER_ID,
                                       f"⏳ الحساب {account_label} متقيد حالياً")
            except Exception as add_err:
                total_failed += 1
                await bot.send_message(Config.OWNER_ID,
                                       f"❌ خطأ عند إضافة @{username}:\n```shell\n{add_err}\n```")
            finally:
                await client.stop()
    
        # === 4. الحصول على عدد الأعضاء النهائي ===
        tmp = Client(":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                     session_string=accounts[0][0], no_updates=True, in_memory=True, lang_code="ar")
        await tmp.start()
        final_count = (await tmp.get_chat(chat_id)).members_count
        await tmp.stop()
    
        # === 5. إرسال الإحصائيات النهائية الجديدة ===
        await bot.send_message(
            Config.OWNER_ID,
            "ᯓ 𓏺˛ SouRce MoNj .⚡️ - إشعـــــار النقل من الملفات ⛞\n"
            "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
            f"عدد الاضافات الكامل: {total_added} عضو\n"
            f"عدد الاضافات الفاشله: {total_failed} عضو\n"
            f"اعضاء المجموعه قبل: {initial_count}\n"
            f"اعضاء المجموعه بعد: {final_count}\n"
            f"عدد الاضافات المحققه: {final_count - initial_count}\n"
            f"عدد الحسابات الموجودة: {total_accounts}\n"
            f"عدد الحسابات المحظورة: {len(blocked_accounts)}\n"
            f"عدد الحسابات النشطه: {total_accounts - len(blocked_accounts)}\n"
            f"مجموع الاضافات لكل الحسابات: {sum(daily_counts.values())}\n"
            f"عدد الاضافات المتبقية لكل الحسابات: {total_accounts * daily_limit - sum(daily_counts.values())}\n",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
        )


    async def get_users_saved(self) -> list:
        """
        جلب الأعضاء من جميع ملفات JSON في مجلد VCF_DIR.
        """
        all_usernames = []
        for filename in os.listdir(VCF_DIR):
            if filename.lower().endswith('.json'):
                path = os.path.join(VCF_DIR, filename)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        all_usernames.extend(data.get('add_members', []))
                except Exception as e:
                    await bot.send_message(
                        Config.OWNER_ID,
                        f"⚠️ خطأ في قراءة الملف {path}: {e}"
                    )
        # إزالة التكرارات مع الحفاظ على الترتيب
        seen = set()
        return [u for u in all_usernames if u and not (u in seen or seen.add(u))]
    async def GETuser(self, GrobUser):
        """
        جلب أعضاء المجموعة وحفظهم في ملف MEMBERS_JSON
        مع تحديد عدد الرسائل وفقاً لقيمة limiting
        """
        accounts = database().accounts()
        random.shuffle(accounts)
        GrobUser = GrobUser.split("/")[-1]

        unique_admins = set()
        unique_bots = set()
        unique_usernames = set()

        # نجرب كل حساب واحداً تلو الآخر ونتخطى الحسابات التي تحدث بها مشاكل
        for session in accounts:
            session_string = session[0]
            try:
                async with Client(
                    ":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                    session_string=session_string, no_updates=True, in_memory=True, lang_code="ar"
                ) as app:
                    await asyncio.sleep(random.randint(3, 5))
                    await app.join_chat(GrobUser)

                    # جلب كل الأعضاء مرة واحدة وفرزهم
                    try:
                        
                        async for member in app.get_chat_members(GrobUser, limit=50000):
                            user = member.user
                            if not user or not user.username:
                                continue

                            uname = user.username
                            # إذا كان بوت
                            if user.is_bot:
                                unique_bots.add(uname)
                            # إذا كان مشرفاً (مالك أو أدمن)
                            elif hasattr(member, "status") and member.status in (
                                enums.ChatMemberStatus.ADMINISTRATOR,
                                enums.ChatMemberStatus.OWNER
                            ):
                                unique_admins.add(uname)
                            # وإلا فهو عضو عادي
                            else:
                                unique_usernames.add(uname)

                    except errors.ChatAdminRequired:
                        # إذا ظهر هذا الخطأ نواصل دون قطيعة
                        pass

                # إذا نجح الحساب من دون استثناء، نوقف التجربة
                break

            except Exception:
                # تخطي هذا الحساب والمحاولة مع التالي
                continue

        # نحذف أي تكرار بين الأعضاء والمشرفين
        members_only = [u for u in unique_usernames if u not in unique_admins]

        # نضمن وجود الـ "@" في بداية كل اسم
    

        data = {
            "add_members": members_only,
            "admins": list(unique_admins),
            "bots": list(unique_bots)
        }

        try:
            with open(MEMBERS_JSON, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as err:
            return f"❌ خطأ في حفظ الملف {MEMBERS_JSON}:\n```shell\n{err}\n```"

        return members_only, list(unique_admins), list(unique_bots)

    async def GETuserhide(self, GrobUser, limit: int):
        """
        جلب أعضاء المجموعة وحفظهم في ملف MEMBERS_JSON
        مع تحديد عدد الرسائل وفقاً لقيمة limiting
        """
        accounts = database().accounts()
        random.shuffle(accounts)
        GrobUser = GrobUser.split("/")[-1]
    
        unique_admins = set()
        unique_bots = set()
        unique_usernames = set()
    
        # نجرب كل حساب واحداً تلو الآخر ونتخطى الحسابات التي تحدث بها مشاكل
        for session in accounts:
            session_string = session[0]
            try:
                async with Client(
                    ":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                    session_string=session_string, no_updates=True, in_memory=True, lang_code="ar"
                ) as app:
                    await app.join_chat(GrobUser)
    
                    # جلب المشرفين
                    async for member in app.get_chat_members(
                        GrobUser,
                        filter=enums.ChatMembersFilter.ADMINISTRATORS
                    ):
                        user = member.user
                        if user and user.username:
                            unique_admins.add(user.username)
    
                    # جلب تاريخ الرسائل بعدد محدد
                    async for msg in app.get_chat_history(GrobUser, limit=limit):
                        user = msg.from_user
                        if not user or not user.username:
                            continue
                        if user.is_bot:
                            unique_bots.add(user.username)
                        else:
                            unique_usernames.add(user.username)
    
                # إذا نجح الحساب من دون استثناء، نوقف التجربة
                break
    
            except Exception:
                # تخطي هذا الحساب والمحاولة مع التالي
                continue
    
        members_only = [u for u in unique_usernames if u not in unique_admins]
    
        data = {
            "add_members": members_only,
            "admins": list(unique_admins),
            "bots": list(unique_bots)
        }
    
        try:
            with open(MEMBERS_JSON, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as err:
            return f"❌ خطأ في حفظ الملف {MEMBERS_JSON}:\n```shell\n{err}\n```"
    
        return members_only, list(unique_admins), list(unique_bots)
    async def GETusersavecontact(self, group_link: str, json_name: str, limit:int):
        # مسار ملف JSON حسب اسم الملف المدخل
        path = os.path.join(VCF_DIR, f"{json_name}.json")
        # تحضير بنية JSON الافتراضية
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"add_members": [], "admins": [], "bots": []}, f, ensure_ascii=False, indent=4)
    
        # جلب بيانات المجموعة
        accounts = database().accounts()
        random.shuffle(accounts)
        group_id = group_link.split('/')[-1]
    
        unique_admins = set()
        unique_bots = set()
        unique_usernames = set()
    
        # استيراد الأخطاء المحددة لتخطي الحساب عند حدوثها
        
    
        # تجربة كل حساب حتى إيجاد أول حساب سليم أو تجاوز الأخطاء المحددة
        for account in accounts:
            session_string = account[0]
            try:
                async with Client(
                    ":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                    session_string=session_string, no_updates=True, in_memory=True, lang_code="ar"
                ) as app:
                    await app.join_chat(group_id)
                    # المشرفين
                    try:
                        async for member in app.get_chat_members(group_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                            if member.user and member.user.username:
                                unique_admins.add(member.user.username)
                    except:
                        pass
                    # باقي الأعضاء
                    try:
                        async for msg in app.get_chat_history(group_id, limit=limit):
                            u = msg.from_user
                            if u and u.username:
                                if u.is_bot:
                                    unique_bots.add(u.username)
                                else:
                                    unique_usernames.add(u.username)
                    except:
                        pass
                # إذا نجحت العملية دون رفع أحد الأخطاء المحددة، نخرج من الحلقة
                break
            except Exception:
                # تجاوز الحساب الحالي والاستمرار بالحساب التالي
                continue
    
        members_only = [u for u in unique_usernames if u not in unique_admins]
    
        # تحميل ودمج البيانات القديمة مع الجديدة
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except:
            existing = {"add_members": [], "admins": [], "bots": []}
    
        data = {
            "add_members": list(set(existing.get("add_members", [])) | set(members_only)),
            "admins": list(set(existing.get("admins", [])) | unique_admins),
            "bots": list(set(existing.get("bots", [])) | unique_bots)
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
        return data["add_members"]
    
    
    MAX_MESSAGE_LENGTH = 4096
    def chunk_text(text, limit=MAX_MESSAGE_LENGTH):
        """
        يقسم النص إلى أجزاء لا تتجاوز الحدود المحددة.
        """
        for i in range(0, len(text), limit):
            yield text[i:i+limit]
    async def joinbar(self, client, message):
        # جلب الحسابات وترتيبها عشوائياً
        accounts = database().accounts()
        random.shuffle(accounts)
    
        # استخراج معرف القروب
        group_id = message.text.split("/")[-1]
        if not accounts:
            return await message.reply("❌ لا يوجد حسابات متاحة للانضمام!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")],]))
    
        success = 0
        failed = 0
        errors = []  # لتجميع تفاصيل الأخطاء
    
        for session_string, account_name in accounts:
            try:
                async with Client(
                    "::memory::",
                    api_id=Config.APP_ID,
                    api_hash=Config.API_HASH,
                    no_updates=True,
                    in_memory=True,
                    lang_code="ar",
                    session_string=session_string
                ) as app:
                    await app.join_chat(group_id)
                    success += 1
    
            except (FloodWait, PeerFlood):
                failed += 1
                # الحظر المؤقت بسبب Flood wait أو PeerFlood
                await message.reply(f"الحساب: {account_name} محظور مؤقتا")
    
            except InviteRequestSent:
                failed += 1
                # في حال كانت المجموعة تحتاج موافقة (طلب انضمام)
                await message.reply(f"تم ارسال طلب انضمام بالحساب: {account_name}")
    
            except (UserBannedInChannel, ChannelInvalid):
                failed += 1
                # الحساب محظور من المجموعة
                await message.reply(f"الحساب: {account_name} قد يكون محظور من القروب")
    
            except RPCError:
                failed += 1
                # أي خطأ آخر من API تلجرام نجمعه للمعاينة لاحقاً
                err = traceback.format_exc()
                errors.append(f"# الحساب: {account_name}\\n# الخطأ:\n```shell\n{err}\n```")
    
            # تأخير متغير بين كل محاولة
            await asyncio.sleep(random.uniform(1, 3))
        if errors:
            formatted = "\n".join(errors)
            for part in Custem.chunk_text(formatted):
                await message.reply(f"```shell\n{part}\n```")
        # إرسال ملخص النتائج
        await message.reply(
            f"✅ تم انضمام {success} حساب بنجاح! 🚀\n"
            f"❌ فشل {failed} حساب.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")],]))
    async def leavebar(self, client, message):
        # جلب الحسابات وترتيبها عشوائياً
        accounts = database().accounts()
        random.shuffle(accounts)
    
        # استخراج معرف القروب
        group_id = message.text.split("/")[-1]
        if not accounts:
            return await message.reply(
                "❌ لا يوجد حسابات متاحة للمغادرة!",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("رجوع 🛎", callback_data="back")]]
                )
            )
    
        success = 0
        failed = 0
        errors = []  # لتجميع تفاصيل الأخطاء
    
        for session_string, account_name in accounts:
            try:
                async with Client(
                    "::memory::",
                    api_id=Config.APP_ID,
                    api_hash=Config.API_HASH,
                    no_updates=True,
                    in_memory=True,
                    lang_code="ar",
                    session_string=session_string
                ) as app:
                    await app.leave_chat(group_id)
                    success += 1
    
            except (FloodWait, PeerFlood):
                failed += 1
                # الحظر المؤقت بسبب Flood wait أو PeerFlood
                await message.reply(f"الحساب: {account_name} محظور مؤقتا")
    
            except (UserNotParticipant, UserBannedInChannel):
                failed += 1
                # في حال أن الحساب غير موجود أو محظور من المجموعة
                await message.reply(f"الحساب: {account_name} غير موجود في القروب")
    
            except RPCError:
                failed += 1
                # أي خطأ آخر من API تلجرام نجمعه للمعاينة لاحقاً
                err = traceback.format_exc()
                await message.reply(f"# الحساب: {account_name}\n# الخطأ:\n```shell\n{err}\n```")
    
            # تأخير متغير بين كل محاولة
            await asyncio.sleep(random.uniform(1, 3))
    
        # إرسال ملخص النتائج
        await message.reply(
            f"👋 تم مغادرة {success} حساب بنجاح!\n"
            f"❌ فشل {failed} حساب.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("رجوع 🛎", callback_data="back")]]
            )
        )

    async def get_users_con(self) -> list:
        """
        جلب الأعضاء من جميع ملفات JSON في مجلد VCF_DIR.
        """
        all_usernames = []
        for filename in os.listdir(VCF_DIR):
            if filename.lower().endswith('.json'):
                path = os.path.join(VCF_DIR, filename)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        all_usernames.extend(data.get('add_members', []))
                except Exception:
                    continue
        seen = set()
        return [u for u in all_usernames if u and not (u in seen or seen.add(u))]
    
    async def add_contacts(self, call):
        """
        إضافة ملف جهات اتصال واحد لكل حساب بالترتيب:
        الحساب الأول يستخدم الملف الأول، والثاني الملف الثاني، وهكذا.
        وإذا انتهت الملفات قبل الحسابات، يُرسل رسالة خطأ ويتوقف.
        """
        # تعديل الرسالة لبدء العملية
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text='⏳ جاري إضافة جهات الاتصال إلى الحسابات...'
        )
    
        # جلب وترتيب ملفات الأعضاء
        files = [f for f in sorted(os.listdir(VCF_DIR)) if f.lower().endswith('.json')]
        if not files:
            return await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.id,
                text='❌ لا توجد ملفات أو بيانات لإضافتها.',
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton('🔙 رجوع', callback_data='back')]]
                )
            )
    
        # جلب الحسابات من قاعدة البيانات
        accounts = database().accounts()
        if not accounts:
            return await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.id,
                text='❌ لا توجد حسابات متاحة.',
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton('🔙 رجوع', callback_data='back')]]
                )
            )
    
        total_contacts = 0
        total_failures = 0
        file_counter = 0  # مؤشر على الملف الجاري استخدامه
    
        # لكل حساب، استخدم ملفًا مختلفًا
        for session_string, account_label in accounts:
            # إذا نفدت الملفات قبل الحسابات
            if file_counter >= len(files):
                await bot.send_message(
                    chat_id=call.message.chat.id,
                    text='❌ نفذت ملفات الأعضاء، قم بتخزين أو إضافة ملفات.'
                )
                break
    
            # مسار الملف الحالي
            file_path = os.path.join(VCF_DIR, files[file_counter])
            file_counter += 1
    
            # تحميل الأعضاء من الملف
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    users = data.get('add_members', [])
            except Exception:
                # إذا كان الملف تالفًا، ننتقل للملف التالي دون عد الحساب
                continue
    
            contacts_added = 0
            failures = 0
    
            # إضافة الأعضاء من ذلك الملف (حتى 300)
            try:
                async with Client(
                    "::memory::",
                    api_id=Config.APP_ID,
                    api_hash=Config.API_HASH,
                    no_updates=True,
                    in_memory=True,
                    lang_code="ar",
                    session_string=session_string
                ) as app:
                    for idx, username in enumerate(users[:300], start=1):
                        contact_name=f"عضو نقل {idx}"
                        try:
                            # وقت انتظار قصير لتجنب الفيض
                            await asyncio.sleep(random.randint(4, 7))
                            await app.add_contact(username, first_name=contact_name)
                            total_contacts += 1
                            contacts_added += 1
                        except Exception:
                            failures += 1
                            total_failures += 1
                            continue
            except Exception:
                # إذا فشل الاتصال بالحساب، ننتقل للحساب التالي
                continue
    
            # إرسال ملخص عن الحساب
            await asyncio.sleep(random.randint(4, 7))
            await bot.send_message(
                chat_id=call.message.chat.id,
                text=(
                    f'✅ حساب {account_label}: أُضيف {contacts_added} جهات اتصال، '
                    f'وفشل {failures}'
                )
            )
    
        # رسالة ختامية بالإجمالي بعد الانتهاء
        await bot.send_message(
            chat_id=call.message.chat.id,
            text=(
                f'✅ المجموع الكلي: تم إضافة {total_contacts} جهة اتصال، '
                f'وفشل إضافة {total_failures} جهة عبر {file_counter} حسابات.'
            )
        )

    async def clear_contacts(self, client, call):
        """
        حذف كل جهات الاتصال من كل الحسابات.
        تعديل الرسالة لبداية العملية، ثم رسالة نهائية.
        """
    
        # تعديل الرسالة لبداية عملية الحذف
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text='⏳ انتظر، سيتم حذف جميع جهات الاتصال من الحسابات...'
        )
    
        # جلب الحسابات من قاعدة البيانات
        accounts = database().accounts()
        if not accounts:
            return await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.id,
                text='❌ لا توجد حسابات متاحة.',
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton('🔙 رجوع', callback_data='back')]]
                )
            )
    
        deleted_accounts = 0
    
        # لكل حساب، حذف جميع جهات الاتصال
        for session_string, account_label in accounts:
            try:
                async with Client(
                    # نستخدم session_string مباشرة كاسم الجلسة حتى يحمل بيانات الجلسة
                    "::memory::",
                    api_id=Config.APP_ID,
                    api_hash=Config.API_HASH,
                    no_updates=True,
                    in_memory=True,
                    lang_code="ar",
                    session_string=session_string
                ) as app:
                    # نجلب جميع جهات الاتصال
                    users = await app.get_contacts()
                    # نحضر قائمة بكل user.id
                    user_ids = [user.id for user in users]
                    if user_ids:
                        # نحذفهم دفعة واحدة
                        await app.delete_contacts(user_ids)
                deleted_accounts += 1
    
            except Exception as e:
                # من الأفضل تسجيل الخطأ للمراجعة لاحقاً
                bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.id,
                text=f'فشل حذف جهات الاتصال في الحساب {account_label}: {e}')
                continue
    
        # رسالة نهائية
        return await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=f'✅ تم حذف جميع جهات الاتصال من {deleted_accounts} حساب.',
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton('🔙 رجوع', callback_data='back')]]
            )
        )

@bot.on_message(filters.command('start') & filters.private)
async def admin(client, message):
    if message.from_user.id == Config.OWNER_ID or message.from_user.id in Config.Devs:
        buttons = [
            [InlineKeyboardButton("إضافة حساب جديد 🆕", callback_data="AddAccount"), InlineKeyboardButton("حذف حساب 🗑️", callback_data="RemoveAccount")],
            [InlineKeyboardButton("انضمام للقروب 🛎", callback_data="joinGroup"), InlineKeyboardButton("مغادرة قروب 🛑", callback_data="leaveGroup")],
            [InlineKeyboardButton("حساباتك المسجلة 📋", callback_data="Accounts")],
            [InlineKeyboardButton("نقل الأعضاء الظاهرين👤", callback_data="addshow"),
            InlineKeyboardButton("نقل اعضاء مخفيين 👤", callback_data="addhide")],
            [InlineKeyboardButton("نقل من جهات الاتصال", callback_data="contact_hire"),
            InlineKeyboardButton("نقل اعضاء من الملفات 🔄", callback_data="addmem_json")],
            [InlineKeyboardButton("تخزين مخفي ☁️", callback_data="save_json")],
            [InlineKeyboardButton("حذف ملف اعضاء 📁", callback_data="del_json"),
            InlineKeyboardButton("رفع ملف اعضاء 📁", callback_data="add_json")],
            [InlineKeyboardButton("استخراج ملفات اعضاء 📂", callback_data="extract_json")],
            [InlineKeyboardButton("اضافة الى جهات الاتصال ➕", callback_data="add_contacts"),
            InlineKeyboardButton("حذف جهات الاتصال 🚫", callback_data="clear_contacts")],
            [InlineKeyboardButton("نسخة احتياطية  📂", callback_data="BackupAccounts"),
            InlineKeyboardButton("رفع نسخة احتياطية  📤", callback_data="AddBackupAccounts")],
            [InlineKeyboardButton("حذف كل الحسابات", callback_data="del_all_accounts")],
            [InlineKeyboardButton("فحص الحسابات 🔍", callback_data="check_accounts")]
        ]
        
        # تهيئة لوحة المفاتيح
        inline_keyboard = InlineKeyboardMarkup(buttons)

        # إرسال رسالة الترحيب مع الأزرار
        await client.send_message(message.chat.id, "مرحبا عزيزي الأدمن في بوت نقل V3.2 الخاص بك\nإليك ازرار التحكم قم بإختيار ما تريد\n\n⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\nلا تنسى الاشتراك في قناة التحديثات\n[𓏺˛ SouRce MoNj .⚡️](https://t.me/Libya_15)", reply_markup=inline_keyboard)
    else:
        await client.send_message(message.chat.id,"عذرا البوت ليس لك لا يمكنك استخدامه\n⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\nلطلب بوت مشابه قم بالتواصل مع المطور: @e_8ii و @cnvno")




@bot.on_callback_query()
async def call_handler(client, call):
    user_id = call.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم استخدام الأزرار
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        # عرض رسالة في صندوق الحوار
        await call.answer(
            "عذرا البوت ليس لك لا يمكنك استخدامه\n"
            "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
            "لطلب بوت مشابه قم بالتواصل مع المطور: @e_8ii و @cnvno",
            show_alert=True
        )
        pass

    data = call.data
    # زر الرجوع
    if data == "back":
        buttons = [
            [InlineKeyboardButton("إضافة حساب جديد 🆕", callback_data="AddAccount"), InlineKeyboardButton("حذف حساب 🗑️", callback_data="RemoveAccount")],
            [InlineKeyboardButton("انضمام للقروب 🛎", callback_data="joinGroup"), InlineKeyboardButton("مغادرة قروب 🛑", callback_data="leaveGroup")],
            [InlineKeyboardButton("حساباتك المسجلة 📋", callback_data="Accounts")],
            [InlineKeyboardButton("نقل الأعضاء الظاهرين👤", callback_data="addshow"), InlineKeyboardButton("نقل اعضاء مخفيين 👤", callback_data="addhide")],
            [InlineKeyboardButton("نقل من جهات الاتصال", callback_data="contact_hire"), InlineKeyboardButton("نقل اعضاء من الملفات 🔄", callback_data="addmem_json")],
            [InlineKeyboardButton("تخزين مخفي ☁️", callback_data="save_json")],
            [InlineKeyboardButton("حذف ملف اعضاء 📁", callback_data="del_json"), InlineKeyboardButton("رفع ملف اعضاء 📁", callback_data="add_json")],
            [InlineKeyboardButton("استخراج ملفات اعضاء 📂", callback_data="extract_json")],
            [InlineKeyboardButton("اضافة الى جهات الاتصال ➕", callback_data="add_contacts"), InlineKeyboardButton("حذف جهات الاتصال 🚫", callback_data="clear_contacts")],
            [InlineKeyboardButton("نسخة احتياطية  📂", callback_data="BackupAccounts"), InlineKeyboardButton("رفع نسخة احتياطية  📤", callback_data="AddBackupAccounts")],
            [InlineKeyboardButton("حذف كل الحسابات", callback_data="del_all_accounts")],
            [InlineKeyboardButton("فحص الحسابات 🔍", callback_data="check_accounts")]
        ]
        inline_keyboard = InlineKeyboardMarkup(buttons)
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=(
                "مرحبا عزيزي الأدمن في بوت نقل V3.2 الخاص بك\n"
                "إليك ازرار التحكم قم بإختيار ما تريد\n\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n"
                "لا تنسى الاشتراك في قناة التحديثات\n"
                "[𓏺˛ SouRce MoNj .⚡️](https://t.me/Libya_15)"
            ),
            reply_markup=inline_keyboard
        )

    # إضافة حساب
    elif data == "AddAccount":
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=(
                "قم بارسال الرقم الذي تريد اضافته\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                "مثال:\n`+20123456789`"
            ),
        )
        bot.register_next_step_handler(AddAccount)

    elif data == "del_all_accounts":
        database().RemoveAllAccounts()
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text="✅ تم حذف جميع الحسابات بنجاح!",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("رجوع 🛎", callback_data="back")]]
            )
        )

    # انضمام حسابات
    elif data == "joinGroup":
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=(
                "قم بارسال رابط القروب للانضمام له\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                "مثال:\n`https://t.me/Libya_15`"
            ),
        )
        bot.register_next_step_handler(Custem().joinbar)

    # مغادرة حسابات
    elif data == "leaveGroup":
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=(
                "قم بارسال رابط القروب للمغادرة منه\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                "مثال:\n`https://t.me/Libya_15`"
            ),
        )
        bot.register_next_step_handler(Custem().leavebar)

    # حذف حساب
    elif data == "RemoveAccount":
        await show_accounts_as_buttons(call, 0, "RemoveAccount")

    # عرض الحسابات
    elif data == "Accounts":
        await show_accounts_as_buttons(call, 0, "Accounts")

    elif data.startswith("page_"):
        pross, current_page = data.split("_")[1].split("-")
        await show_accounts_as_buttons(call, int(current_page), pross)

    elif data.startswith("delaccount_"):
        del_number = data.split("_")[1]
        database().RemoveAccount(del_number)
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=f"✅ تم حذف الرقم: {del_number} بنجاح!",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("رجوع 🛎", callback_data="back")]]
            )
        )

    # باك اب حسابات
    elif data == "BackupAccounts":
        accounts = database().backupaccounts()
        with open('./WhiskeyBackUp.json', 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=4)
        await bot.send_document(
            chat_id=call.message.chat.id,
            document='./WhiskeyBackUp.json',
            caption="📂 النسخة الاحتياطية من الحسابات"
        )
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=(
                "✨ تم حفظ البيانات في ملف WhiskeyBackUp.json بنجاح. "
                "استمتع بالإدارة المنظمة! 📁"
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("رجوع 🛎", callback_data="back")]]
            )
        )
        os.remove('./WhiskeyBackUp.json')

    # رفع النسخة الاحتياطية
    elif data == "AddBackupAccounts":
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text="قم برفع ملف النسخة الاحتياطية (WhiskeyBackUp.json)"
        )
        bot.register_next_step_handler(AddBackupAccounts)

    # نقل الأعضاء ظاهر
    elif data == "addshow":
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=(
                "قم بارسال العدد المراد اضافته للقروب\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                "لا تنسى الانضمام للقناة:\n"
                "[𓏺˛ SouRce MoNj .⚡️](https://t.me/Libya_15)"
            ),
        )
        bot.register_next_step_handler(statement)

    # حفظ ملف الأعضاء
    elif data == "save_json":
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=(
                "📁 ارسل اسم الملف المراد حفظ فيه لاعضاء\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                "مثل:\n`ملف نقل 1`"
            )
        )
        bot.register_next_step_handler(partial(ask_group_link, user_info={}))

    # نقل الأعضاء مخفي
    elif data == "addhide":
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=(
                "قم بارسال العدد المراد اضافته للقروب\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                "لا تنسى الانضمام للقناة:\n"
                "[𓏺˛ SouRce MoNj .⚡️](https://t.me/Libya_15)"
            ),
        )
        bot.register_next_step_handler(statementhide)

    elif data == 'clear_contacts':
        await Custem().clear_contacts(client, call)

    elif data == "addmem_json":
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=(
                "قم بارسال رابط القرول المراد اضافة الأعضاء له\n"
                "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
                "مثل:\n`https://t.me/Libya_15`"
            )
        )
        async def _read_link(c, message):
            await handle_group(c, message)
        bot.register_next_step_handler(_read_link)

    elif data == 'extract_json':
        return await list_exp_pages(call, page=0)

    elif data.startswith('extract_json_page:'):
        _, page_str = data.split(':', 1)
        return await list_exp_pages(call, page=int(page_str))

    elif data.startswith('extract_file:'):
        _, fname = data.split(':', 1)
        path = os.path.join(VCF_DIR, fname)
        if os.path.exists(path):
            await call.message.edit_text(
                f'✅ تم استخراج الملف بنجاح: {fname}',
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton('🔙 رجوع', callback_data='back')]]
                )
            )
            return await call.message.reply_document(path, file_name=fname)
        else:
            return await call.answer('❌ الملف غير موجود.', show_alert=True)

    elif data == 'add_contacts':
        await Custem().add_contacts(call)

    elif data == "contact_hire":

        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text="📁 قم بارسال الرابط المراد اضافة الجهات له:"
        )
        async def _read_link(c, message):
            await han_group(c, message)
        bot.register_next_step_handler(_read_link)

    elif data == 'del_json':
        return await list_vcf_pages(call, page=0)

    elif data.startswith('del_json_page:'):
        _, page_str = data.split(':', 1)
        return await list_vcf_pages(call, page=int(page_str))

    elif data.startswith('ask_delete:'):
        _, fname = data.split(':', 1)
        buttons = [
            [InlineKeyboardButton("✅ نعم", callback_data=f"confirm_delete:{fname}")],
            [InlineKeyboardButton("❌ لا", callback_data="del_json")]
        ]
        return await call.message.edit_text(
            f"⚠️ هل تريد حذف الملف {fname}؟",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith('confirm_delete:'):
        user_id = call.from_user.id
        # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
        if user_id != Config.OWNER_ID and user_id not in Config.Devs:
            await call.message.reply(
                "عذرا الأوامر ليست لك"
            )
        pass
        _, fname = data.split(':', 1)
        path = os.path.join(VCF_DIR, fname)
        if os.path.exists(path):
            os.remove(path)
            buttons = [[InlineKeyboardButton("🔙 رجوع", callback_data="del_json")]]
            return await call.message.edit_text(
                f"✅ تم حذف الملف {fname} بنجاح.",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            return await call.answer('❌ الملف غير موجود', show_alert=True)

    elif data == 'add_json':
        user_id = call.from_user.id
        # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
        if user_id != Config.OWNER_ID and user_id not in Config.Devs:
            await call.message.reply(
                "عذرا الأوامر ليست لك"
            )
        pass
        EXPECTING_JSON.add(call.message.chat.id)
        await call.answer()
        await call.message.reply("من فضلك أرسل ملف الأعضاء بصيغة JSON:")


@bot.on_message(filters.document & filters.private)
async def handle_json_file(client, message):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        return

    chat_id = message.chat.id
    if chat_id not in EXPECTING_JSON:
        return

    EXPECTING_JSON.remove(chat_id)
    file_name = message.document.file_name
    if not file_name.lower().endswith('.json'):
        await message.reply('❌ الملف غير مدعوم، الرجاء إرسال ملف بصيغة JSON فقط.')
        return

    save_path = os.path.join(VCF_DIR, file_name)
    await client.download_media(message.document, file_name=save_path)
    await message.reply(f'✅ تم حفظ الملف بنجاح: `{file_name}`')
@bot.on_message(filters.private)
async def handle_check_link(client, message, orig_call):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    link = message.text.strip()
    # استخراج معرف المجموعة (آخر جزء من الرابط)
    group_username = link.split("/")[-1]

    # نعلم المستخدم ببدء الفحص
    status_msg = await bot.send_message(
        chat_id=message.chat.id,
        text=f"⏳ جارٍ فحص الحسابات بالانضمام إلى @{group_username}..."
    )

    db = database()
    raw_accounts = db.accounts()  # [(session_str, label), ...]
    total_accounts = len(raw_accounts)

    # عدادات النتائج
    restricted = 0
    success = 0
    problems = 0
    to_delete = 0
    blocked_accounts = set()

    for session_str, label in raw_accounts:
        client_ok = None
        try:
            client_ok = Client(
                ":memory:", api_id=Config.APP_ID, api_hash=Config.API_HASH,
                session_string=session_str, no_updates=True, in_memory=True, lang_code="ar"
            )
            await client_ok.start()
            # نجرب الانضمام للمجموعة
            await client_ok.join_chat(group_username)
            # إذا وصل هنا بدون استثناء → انضمام ناجح
            success += 1

        except FloodWait:
            restricted += 1

        except PeerFlood:
            restricted += 1

        except (SessionRevoked, AuthKeyInvalid) as e:
            # حساب به مشكلة جلسة → نعدّه للحذف
            to_delete += 1
            blocked_accounts.add(label)
            db.RemoveAccount(label)

        except Exception:
            # أخطاء أخرى
            problems += 1

        finally:
            if client_ok:
                await client_ok.stop()

    # الحسابات النشطة بعد الحذف
    active_after = total_accounts - len(blocked_accounts)

    # 3) نعدل رسالة الحالة لتظهر النتائج النهائية
    report = (
        "ᯓ 𓏺˛ SouRce MoNj .⚡️ - فاحص الحسابات  ⛞\n"
        "⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
        f"عدد الحسابات بالكامل: {total_accounts} حساب\n"
        f"انضمام ناجح: {success} حساب\n"
        f"حسابات مقيدة (Flood/FloodWait): {restricted} حساب\n"
        f"الحسابات المحذوفة أو المنتهية الجلسة: {to_delete} حساب\n"
        f"الأخطاء الأخرى: {problems} حالة\n"
        f"الحسابات النشطة بعد الفحص: {active_after} حساب\n"
    )
    await bot.send_message(
        chat_id=message.chat.id, 
        text=report,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("رجوع 🛎", callback_data="back")]]
        )
    )

@bot.on_message(filters.private)
async def han_group(client, message):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    group_link = message.text.strip()
    await message.reply("📤 ارسل عدد الأعضاء المراد إضافتهم:")
    bot.register_next_step_handler(partial(start_add_con, group_link=group_link))
@bot.on_message(filters.private)
async def start_add_con(client, message, group_link):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        return
    try:
        count = int(message.text.strip())
    except ValueError:
        return await message.reply("❗️ الرجاء إدخال رقم صحيح.")
    await message.reply("⏳ جاري اضافة جهات الاتصال...")
    await message.reply(
        "ᯓ 𓏺˛ SouRce MoNj .⚡️ - إشعـــــار النقل جهات الاتصال⛞\n"
        "⋆─┄─┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
        f"الطلب : {count} عضو\n"
        f"النقل الى : `{group_link}`\n\n"
        "لإلغاء العملية أرسل : /stop_add"
    )
    await Custem().add_users_contact(group_link, bot, count)



@bot.on_message(filters.private)
async def handle_group(client, message):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    group_link = message.text.strip()
    await message.reply("📤 ارسل عدد الأعضاء المراد إضافتهم:")
    # هنا نمرّر group_link للخطوة التالية عبر partial
    bot.register_next_step_handler(
        partial(start_adding, group_link=group_link)
    )
@bot.on_message(filters.private)
async def start_adding(client, message, group_link):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    try:
        count = int(message.text.strip())
    except ValueError:
        return await message.reply("❗️ الرجاء إدخال رقم صحيح.")
    await message.reply("⏳ جاري اضافة الاعضاء للقروب...")
    numUser = len(await Custem().get_users_saved())
    await message.reply(
        "ᯓ 𓏺˛ SouRce MoNj .⚡️ - إشعـــــار النقل الاعضاء محفوظه⛞\n"
        "⋆─┄─┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
        f"المتاحين للاضافة : {numUser} عضو\n"
        f"الطلب : {count} عضو\n"
        f"النقل الى : `{group_link}`\n\n"
        "لإلغاء العملية أرسل : /stop_add"
    )
    await Custem().add_users_hide(group_link, client, count)
####################################################################
#اضافه حساب
@bot.on_message(filters.private)
async def AddAccount(client, message):    
    # تجاهل الأوامر السابقة عند إعادة التشغيل
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await client.send_message(
            "عذرا الأوامر ليست لك"
        )
        pass
    if message.text == '/start':
        return
    # التحقق من وجود رمز الدولة (+)
    if not message.text.startswith('+'):
        await bot.send_message(message.chat.id, "*يرجى إدخال رمز الدولة مع رقم الهاتف (مثال: +20123456789)*")
        return
    # متابعة التدفق الأصلي عند إدخال رقم صحيح
    await bot.send_message(message.chat.id, "*انتظر قليلاً... جاري الفحص ⏱*",)
    # API credentials (api_id & api_hash) and session storage are obtained as described at:
    # https://telegram.tools/session-string-generator#pyrogram
    _client = Client(
        "::memory::", in_memory=True,
        api_id=Config.APP_ID,
        api_hash=Config.API_HASH,
        lang_code="ar"
        
    )
    await _client.connect()
    SendCode = await _client.send_code(message.text)
    await bot.send_message(message.chat.id, "قم بإرسال الرمز المرسل من التيليجرام بالشكل التالي:\n⋆─┄─┄─┄─┄─┄┄─┄┄─┄─⋆\n\n1 2 3 4 5",)
    user_info = {
        "client": _client,
        "phone": message.text,
        "hash": SendCode.phone_code_hash,
        "name": message.text
    }
    bot.register_next_step_handler(partial(sigin_up, user_info=user_info))
@bot.on_message(filters.private)
async def sigin_up(client, message, user_info: dict):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    try:
        await bot.send_message(message.chat.id, "*انتظر قليلا ⏱*",)
        # Support codes entered as "1 2 3 4 5" by stripping spaces:
        code = message.text.replace(" ", "")
        await user_info['client'].sign_in(
            user_info['phone'],
            user_info['hash'],
            phone_code=code
        )
        await bot.send_message(message.chat.id, "*تم تاكيد الحساب بنجاح ✅ *",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton('🔙 رجوع', callback_data='back')]]
                )
            )
        ses = await user_info['client'].export_session_string()
        database().AddAcount(ses, user_info['name'], message.chat.id)
    except SessionPasswordNeeded:
        await bot.send_message(message.chat.id, "*أدخل كلمة المرور الخاصة بحسابك 🔐*",)
        bot.register_next_step_handler(partial(AddPassword, user_info=user_info))
@bot.on_message(filters.private)
async def AddPassword(client, message, user_info: dict):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    try:
        await user_info['client'].check_password(message.text)
        ses = await user_info['client'].export_session_string()
        database().AddAcount(ses, user_info['name'], message.chat.id)
        try:
            await user_info['client'].stop()
        except:
            pass
        await bot.send_message(message.chat.id, "*تم تاكيد الحساب بنجاح ✅ *",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton('🔙 رجوع', callback_data='back')]]
                )
            )
    except Exception as e:
        print(e)
        try:
            await user_info['client'].stop()
        except:
            pass
        await bot.send_message(message.chat.id, f"⚠️ حدث خطأ أثناء التأكيد: {e}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton('🔙 رجوع', callback_data='back')]]
                )
            )


#################################################
#نقل الاعضاء      





@bot.on_message(filters.private)
async def statement(client, message):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    num = message.text
    await bot.send_message(chat_id=message.chat.id,text="قم بارسال رابط القروب المراد سحب الأعضاء منه\n––––––––––––––––––––––––––––\n\nمثل:\n`https://t.me/Libya_15`",)
    Fromgrob_info = {"num":num,}
    bot.register_next_step_handler(partial(statement1,user_info=Fromgrob_info))	
@bot.on_message(filters.private)
async def statement1(client, message, user_info: dict):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    Fromgrob = message.text
    await bot.send_message(chat_id=message.chat.id,text="قم بارسال رابط القروب المراد اضافة الأعضاء له\n––––––––––––––––––––––––––––\n\nمثل:\n`https://t.me/Libya_15`",)
    Fromgrob_info = {"Fromgrob":Fromgrob,"num":user_info['num']}
    bot.register_next_step_handler(partial(statement2,user_info=Fromgrob_info))	
@bot.on_message(filters.private)
async def statement2(client, message, user_info: dict):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    Ingrob = message.text
    await bot.send_message(chat_id=message.chat.id,text="انتظر دقائق ليتم تجهيز الاعضاء ⏱",)
    add_members, admins, bots = await Custem().GETuser(user_info['Fromgrob']) 
    numUser = len(add_members)
    await bot.send_message(message.chat.id,f"""ᯓ 𓏺˛ SouRce MoNj .⚡️ - إشعـــــار النقل الظاهر ⛞
⋆─┄─┄─┄─┄─┄┄─┄┄─┄─⋆

المتاحين للاضافة : {numUser} عضو 
النقل من  : `{user_info['Fromgrob']}` 
النقل الي : `{Ingrob}` 

لإلغاء العملية أرسل : /stop_add """ ,)
    await Custem().ADDuser(Ingrob,user_info['Fromgrob'],bot,user_info['num'])
#################################################
@bot.on_message(filters.private)
async def statementhide(client, message):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    num = message.text
    await bot.send_message(
        chat_id=message.chat.id,
        text="قم بارسال رابط القروب المراد سحب الأعضاء منه\n⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\nمثل:\n`https://t.me/Libya_15`",
    )
    Fromgrob_info = {"num": num}
    bot.register_next_step_handler(
        partial(statement1hide, user_info=Fromgrob_info)
    )
@bot.on_message(filters.private)
async def statement1hide(client, message, user_info: dict):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    Fromgrob = message.text.strip()
    user_info['Fromgrob'] = Fromgrob
    # ask for limit before fetching
    await bot.send_message(
        chat_id=message.chat.id,
        text="قم بإدخال عدد الرسائل التي تريد جلب الاعضاء منها\n⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\nمثل:\n`30000`",
    )
    # register ask_limit
    bot.register_next_step_handler(
        partial(Custem().ask_limit, user_info=user_info)
    )

# statement2hide now receives limit in user_info and Ingrob link
@bot.on_message(filters.private)
async def statement2hide(client, message, user_info: dict):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    Ingrob = message.text.strip()
    limit = user_info.get('limit')
    await bot.send_message(message.chat.id, "*انتظر دقائق ليتم تجهيز الاعضاء ⏱*")

    # استدعاء الدالة لجلب أعضاء المجموعة والحفظ في MEMBERS_JSON
    add_members, admins, bots = await Custem().GETuserhide(user_info['Fromgrob'], limit)
    # عدد الأعضاء المراد إضافتهم من JSON
    numUser = len(add_members)

    # إرسال إشعار بالبيانات
    await bot.send_message(
        message.chat.id,
        (
            "ᯓ 𓏺˛ SouRce MoNj .⚡️ - إشعـــــار النقل المخفي ⛞\n"
            "⋆─┄─┄─┄─┄─┄┄─┄┄─┄─⋆\n\n"
            f"المتاحين للاضافة : {numUser} عضو\n"
            f"النقل من  : `{user_info['Fromgrob']}`\n"
            f"النقل الي : `{Ingrob}`\n\n"
            "لإلغاء العملية أرسل : /stop_add"
        )
    )
    await Custem().ADDuserhide(add_members, Ingrob, user_info['Fromgrob'], bot, user_info['num'])  



@bot.on_message(filters.private)
@bot.on_callback_query()
async def call_handler(client, call):
    user_id = call.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await call.reply(
            "عذرا البوت ليس لك لا يمكنك استخدامه\n⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\n\nلطلب بوت مشابه قم بالتواصل مع المطور: @e_8ii و @cnvno"
        )
        pass
    if call.data == "save_json":
        # اطلب اسم الملف
        await bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text="📁 أرسل اسم الملف المراد حفظ فيه الأعضاء\n\n⋆─┄──┄─┄─┄─┄┄─┄┄─┄─⋆\nمثل:\n`ملف نقل 1`"
        )
        bot.register_next_step_handler(partial(ask_group_link, user_info={}))
@bot.on_message(filters.private)
async def ask_group_link(client, message, user_info):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    # استلم اسم الملف
    user_info['filename'] = message.text.strip()
    await client.send_message(message.chat.id, "🔗 أرسل رابط القروب لاستخراج الأعضاء:")
    bot.register_next_step_handler(partial(ask_limit, user_info=user_info))
@bot.on_message(filters.private)
async def ask_limit(client, message, user_info):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    # استلم رابط القروب
    user_info['group_link'] = message.text.strip()
    await client.send_message(
        message.chat.id,
        "🔢 كم عدد الرسائل تريد جلبها؟ (مثلاً: 30000 رساله)"
    )
    bot.register_next_step_handler(partial(process_save, user_info=user_info))
@bot.on_message(filters.private)
async def process_save(client, message, user_info):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    # استلم قيمة limit
    try:
        limiting = int(message.text.strip())
    except ValueError:
        limiting = 30000  # قيمة افتراضية في حال الإدخال خاطئ
    await client.send_message(message.chat.id, "⏳ جارٍ استخراج الأعضاء وحفظها...")
    members = await Custem().GETusersavecontact(
        user_info['group_link'],
        user_info['filename'],
        limiting  # هنا نمرر القيمة التي أدخلها المستخدم
    )
    await client.send_message(
        message.chat.id,
        f"✅ تم حفظ {len(members)} عضو في الملف: `{user_info['filename']}.json` داخل المجلد `{VCF_DIR}`."
    )


#################################################
#رفع النسخه الحسابات 
@bot.on_message(filters.private)
async def AddBackupAccounts(client, message):
    user_id = message.from_user.id
    # تحقق من الصلاحيات: فقط OWNER_ID أو أعضاء Devs يحق لهم رفع الملفات
    if user_id != Config.OWNER_ID and user_id not in Config.Devs:
        await message.reply(
            "عذرا الأوامر ليست لك"
        )
        pass
    # تأكد من أن هناك وثيقة مرفقة مع الرسالة
    if message.document.file_name.endswith("json"):
        await message.download("./WhiskeyBackUp.json")
        with open("./WhiskeyBackUp.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        k = 0
        for account in data:
            try:
                # إضافة الحسابات إلى قاعدة البيانات
                database().AddAcount(account[0], account[1], account[2])
                k += 1
            except Exception as e:
                print(f"Error processing account: {e}")
                pass

        # تحديث الرسالة مع عدد الحسابات المضافة
        await client.send_message(
            chat_id=message.chat.id,
            text=f"تم رفع النسخة الاحتياطية بنجاح. حساباتك: {k} حساب.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
        )
        os.remove("./WhiskeyBackUp.json")
    else:
        # إذا لم يكن هناك مستند مرفق
        await client.send_message(
            chat_id=message.chat.id,
            text="*لم يتم العثور على مستند مرفق. يُرجى إرسال النسخة الاحتياطية بصيغة JSON.*",
        )
#####################################
#عرض الحسابات وحذف الحسابات
@bot.on_message(filters.private)
async def show_accounts_as_buttons(call, current_page, pross):

    accounts = database().backupaccounts()  # جلب الحسابات من قاعدة البيانات
    buttons_per_page = 14  # 7 صفوف × عمودين = 14 زرّ في كل صفحة
    buttons = []

    # تحويل الحسابات إلى أزرار
    for account in accounts:
        label = f"الرقم: {account[1]}"
        if pross == "RemoveAccount":
            data = f"delaccount_{account[1]}"
        else:
            data = "no_action"
        buttons.append(InlineKeyboardButton(label, callback_data=data))

    # تقسيم الأزرار إلى صفحات
    pages = [buttons[i : i + buttons_per_page] for i in range(0, len(buttons), buttons_per_page)]

    # إعداد أزرار التنقل
    page_buttons = []
    if current_page > 0:
        page_buttons.append(InlineKeyboardButton("السابق ◀️", callback_data=f"page_{pross}-{current_page - 1}"))
    if current_page < len(pages) - 1:
        page_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"page_{pross}-{current_page + 1}"))
    page_buttons.append(InlineKeyboardButton("رجوع 🛎", callback_data="back"))

    # التحقق من صحة رقم الصفحة
    if current_page < 0 or current_page >= len(pages):
        return await call.message.edit_text(
            "*لا توجد حسابات حالياً.*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع 🛎", callback_data="back")]])
        )

    # بناء لوحة الأزرار: عمودين
    current_buttons = pages[current_page]
    keyboard = [
        current_buttons[i : i + 2]
        for i in range(0, len(current_buttons), 2)
    ]
    if page_buttons:
        keyboard.append(page_buttons)

    # عرض الرسالة مع لوحة الأزرار
    await call.message.edit_text(
        "*حساباتك المسجلة بالكامل:*",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


######################################################################


if __name__ == "__main__":
    bot.run()