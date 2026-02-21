import re
import asyncio
from datetime import datetime
import jdatetime
from PIL import Image
import io

def detect_image_type(data_bytes):
    try:
        img = Image.open(io.BytesIO(data_bytes))
        return img.format  # 'JPEG', 'PNG', ...
    except Exception:
        return None

# مثال استفاده:
# img_type = detect_image_type(file_bytes)
# if img_type == 'JPEG': ...

from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
    RPCError
)
from telethon.tl.functions.account import UpdateProfileRequest

# ---------------- تنظیمات ----------------

api_id = 14992695        # اینجا api_id خودت
api_hash = 'a64a4b3fa559c59861d91a8860cebfb2'  # اینجا api_hash خودت
allowed_user_id = 8079462268 # آیدی عددی خودت

client = TelegramClient("session", api_id, api_hash)

# لیست‌ها در حافظه (اگر دائمی می‌خوای بعداً می‌تونیم ذخیره‌سازی اضافه کنیم)
enemies = {}
friends = {}
user_response_queue = {}

enemy_responses = [
    "پیامت ثبت شد.",
    "لطفاً محترمانه‌تر بنویس.",
    "این نوع پیام‌ها پذیرفته نمی‌شود.",
    "قوانین احترام را رعایت کن."
]

friend_responses = [
    "دمت گرم رفیق ❤️",
    "ارادت، پیامت رسید.",
    "رفاقتت قابل احترامه.",
    "مرسی که هستی."
]

daily_message = "روز جدید مبارک 🌙✨"

days_fa = {
    "Saturday": "شنبه",
    "Sunday": "یکشنبه",
    "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه",
    "Wednesday": "چهارشنبه",
    "Thursday": "پنج‌شنبه",
    "Friday": "جمعه"
}

months_fa = {
    1: "فروردین", 2: "اردیبهشت", 3: "خرداد", 4: "تیر",
    5: "مرداد", 6: "شهریور", 7: "مهر", 8: "آبان",
    9: "آذر", 10: "دی", 11: "بهمن", 12: "اسفند"
}

time_enabled = False  # کنترل نمایش تایم در اسم

# ---------------- توابع کمکی ----------------

def get_info():
    now = jdatetime.datetime.now()
    g = now.togregorian()

    return {
        "time": now.strftime("%H:%M:%S"),
        "jalali": now.strftime("%Y/%m/%d"),
        "gregorian": g.strftime("%Y/%m/%d"),
        "day_fa": days_fa[g.strftime("%A")],
        "day_en": g.strftime("%A"),
        "month_fa": months_fa[now.month],
        "month_en": g.strftime("%B"),
        "utc": g.strftime("%Y-%m-%d %H:%M:%S")
    }

def fancy(t: str) -> str:
    return t.translate(str.maketrans("0123456789", "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"))

async def send_reply(event, lst):
    """پاسخ‌دهی ترتیبی، ولی بدون گیر کردن در انتهای لیست."""
    uid = event.sender_id
    if uid not in user_response_queue:
        user_response_queue[uid] = 0

    i = user_response_queue[uid] % len(lst)
    await event.reply(lst[i])
    user_response_queue[uid] += 1

async def save_media(event):
    """سیو مدیا با ریپلای روی پیام و نوشتن 'سیو'."""
    if not event.is_reply:
        return

    if event.raw_text.strip() not in ["سیو", "save", "ذخیره"]:
        return

    rep = await event.get_reply_message()
    if not rep or not rep.media:
        return

    try:
        await event.message.delete()
        media = await client.download_media(rep.media)
        await client.send_file("me", media)
        await client.send_message("me", "مدیا ذخیره شد ✓")
    except Exception as e:
        print("Error in save_media:", e)

async def change_name(event):
    """تغییر اسم با دستور: اسم عوض بشه به ..."""
    m = re.match(r"اسم عوض بشه به (.+)", event.raw_text.strip())
    if not m:
        return

    new = m.group(1).strip()
    if not new:
        return

    try:
        await client(UpdateProfileRequest(first_name=new))
        await event.message.edit("اسم تغییر کرد ✓")
    except Exception as e:
        print("Error in change_name:", e)

async def manage_lists(event):
    """مدیریت لیست بدخا و مشتی با ریپلای روی پیام کاربر."""
    if not event.is_reply:
        return

    rep = await event.get_reply_message()
    uid = rep.sender_id
    txt = event.raw_text.strip()

    try:
        if "تنظیم بدخا" in txt:
            enemies[uid] = True
            friends.pop(uid, None)
            await event.message.edit("به لیست بدخا اضافه شد.")
        elif "حذف بدخا" in txt:
            enemies.pop(uid, None)
            await event.message.edit("از لیست بدخا حذف شد.")
        elif "تنظیم مشتی" in txt:
            friends[uid] = True
            enemies.pop(uid, None)
            await event.message.edit("به لیست مشتی اضافه شد.")
        elif "حذف مشتی" in txt:
            friends.pop(uid, None)
            await event.message.edit("از لیست مشتی حذف شد.")
    except Exception as e:
        print("Error in manage_lists:", e)

# ---------------- لوپ تایم در اسم ----------------

async def time_loop():
    global time_enabled
    while True:
        try:
            if time_enabled:
                now = datetime.now()
                t = fancy(f"{now.hour}:{now.minute:02d}")

                me = await client.get_me()
                base_name = me.first_name or ""
                # حذف تایم قبلی اگر وجود داشته باشد
                base_name = re.sub(r"\s*[𝟶-𝟿]{1,2}:[𝟶-𝟿]{2}", "", base_name).strip()
                new_name = f"{base_name} {t}".strip()

                await client(UpdateProfileRequest(first_name=new_name))
        except FloodWaitError as e:
            print(f"FloodWait in time_loop: {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print("Error in time_loop:", e)

        # فاصله مناسب برای جلوگیری از محدودیت
        await asyncio.sleep(120)

# ---------------- ارسال پیام روزانه ----------------

async def midnight_sender():
    global daily_message
    last_day = None

    while True:
        try:
            now = datetime.now().date()
            if now != last_day:
                await client.send_message("me", daily_message)
                last_day = now
        except Exception as e:
            print("Error in midnight_sender:", e)

        await asyncio.sleep(60)

# ---------------- دستورات ادمین ----------------

async def commands(event):
    global time_enabled, daily_message

    if event.sender_id != allowed_user_id:
        return

    t = event.raw_text.strip()

    if t == "تاریخ و ساعت":
        i = get_info()
        await event.message.edit(
            f"ساعت: {i['time']}\n"
            f"تاریخ: {i['jalali']} - {i['gregorian']}\n"
            f"روز: {i['day_fa']} - {i['day_en']}\n"
            f"ماه: {i['month_fa']} - {i['month_en']}\n"
            f"UTC: {i['utc']}"
        )

    elif t == "تایم روشن":
        time_enabled = True
        await event.message.edit("تایم روشن شد ✓")

    elif t == "تایم خاموش":
        time_enabled = False
