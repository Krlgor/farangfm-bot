"""
FARANG.FM TELEGRAM BOT v4.0 - Render Ready
- Language selection: RU / EN / TH
- Listen Now → Telegram Mini App
- Moderation system: approve / reject / edit
- Scheduled auto-posts via job_queue
- Groq AI content generation
- Admin: /post, /generate, /schedule, /pending
"""

import os
import sys
import logging
import requests
import asyncio
from datetime import datetime, timezone, timedelta
from functools import wraps
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from telegram.error import TelegramError

from database import (
    init_db, get_post, update_post_status, update_post_text,
    get_pending_posts, get_schedule,
    add_scheduled_post, toggle_scheduled_post, remove_scheduled_post,
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

TOKEN       = os.getenv("BOT_TOKEN", "")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "")
ADMIN_ID    = int(os.getenv("ADMIN_ID", "0"))
GROQ_KEY    = os.getenv("GROQ_API_KEY", "")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://farang-fm.netlify.app/")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/farangfm")

# Проверка обязательных переменных
if not TOKEN:
    logging.error("BOT_TOKEN not set!")
    sys.exit(1)
if not CHANNEL_ID:
    logging.error("CHANNEL_ID not set!")
    sys.exit(1)
else:
    CHANNEL_ID = int(CHANNEL_ID)
if ADMIN_ID == 0:
    logging.error("ADMIN_ID not set!")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Bangkok timezone (UTC+7)
BKK_TZ = timezone(timedelta(hours=7))

# Conversation state for editing a post
STATE_EDIT_TEXT = 0

# In-memory language store {user_id: 'ru'|'en'|'th'}
USER_LANG: dict[int, str] = {}

# ═══════════════════════════════════════════════════════════════════════════════
# STREAMS
# ═══════════════════════════════════════════════════════════════════════════════

STREAMS = {"LOFI": "🌙", "CHILL": "🌊", "ROAD": "🛵", "DANCE": "🔥"}

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK SERVER (для Render)
# ═══════════════════════════════════════════════════════════════════════════════

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Подавляем логи health check

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    httpd = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"🏥 Health server running on port {port}")
    httpd.serve_forever()

# ═══════════════════════════════════════════════════════════════════════════════
# TRANSLATIONS (сокращено для читаемости, полная версия в архиве)
# ═══════════════════════════════════════════════════════════════════════════════

T = {
    "ru": {
        "welcome": "<b>🎙️ Добро пожаловать на FARANG.FM!</b>\n\nПривет, {name}! 👋\n\nКруглосуточное тропическое радио из Таиланда 🌴\n\n<i>🌙 LOFI · 🌊 CHILL · 🛵 ROAD · 🔥 DANCE</i>",
        "listen_now": "🎧 Слушать сейчас",
        "streams": "📻 Стримы",
        "advertise": "💼 Реклама",
        "channel": "📡 Канал",
        "about": "ℹ️ О нас",
        "back": "🔙 Назад",
        "choose_stream": "<b>🎧 Выберите стрим:</b>",
        "stream_info": "<b>{emoji} Стрим {stream}</b>\n\n{desc}\n\n🎵 <i>320kbps · 24/7 · Весь мир</i>",
        "stream_descs": {
            "LOFI": "Чилловые биты. Лунное настроение. Режим фокуса.",
            "CHILL": "Морской бриз. Закатные сессии. Чистое расслабление.",
            "ROAD": "Неоновые шоссе. Энергия тук-тука. Полный газ.",
            "DANCE": "Клубные хиты. Дроп баса. До рассвета.",
        },
        "about_text": "<b>📡 FARANG.FM</b>\n\nКруглосуточное тропическое радио из Таиланда 🌴\nДля экспатов, туристов и местных по всему миру.\n\n<b>Стримы:</b> 🌙 LOFI · 🌊 CHILL · 🛵 ROAD · 🔥 DANCE\n\n<b>Бесплатно · HD качество · Всегда онлайн</b>",
        "advertise_text": "<b>💼 Реклама на FARANG.FM</b>\n\nОхватите тысячи слушателей в Таиланде и по всему миру.\n\n📌 Баннер на сайте\n🎙️ Аудиоролик\n📱 Пост в Telegram\n📦 Полный пакет\n\nНапишите нам напрямую 👇",
        "write_us": "✉️ Написать нам",
        "all_streams": "📻 Все стримы",
        "post_usage": "<b>Использование:</b> /post &lt;STREAM&gt; &lt;текст&gt;\n\nСтримы: LOFI, CHILL, ROAD, DANCE",
        "post_unknown": "❌ Неизвестный стрим: <b>{stream}</b>",
        "post_ok": "✅ Опубликовано! {emoji} {stream}",
        "post_error": "❌ Ошибка: <code>{err}</code>",
        "not_admin": "🚫 Только для администратора.",
    },
    "en": {
        "welcome": "<b>🎙️ Welcome to FARANG.FM!</b>\n\nHey {name}! 👋\n\n24/7 tropical radio streaming from Thailand 🌴\n\n<i>🌙 LOFI · 🌊 CHILL · 🛵 ROAD · 🔥 DANCE</i>",
        "listen_now": "🎧 Listen Now",
        "streams": "📻 Streams",
        "advertise": "💼 Advertise",
        "channel": "📡 Channel",
        "about": "ℹ️ About",
        "back": "🔙 Back",
        "choose_stream": "<b>🎧 Choose your stream:</b>",
        "stream_info": "<b>{emoji} {stream} Stream</b>\n\n{desc}\n\n🎵 <i>320kbps · 24/7 · Worldwide</i>",
        "stream_descs": {
            "LOFI": "Chill beats. Moonlit vibes. Focus mode.",
            "CHILL": "Ocean breeze. Sunset sessions. Pure relaxation.",
            "ROAD": "Neon highways. Tuk-tuk energy. Full throttle.",
            "DANCE": "Club bangers. Bass drops. All night long.",
        },
        "about_text": "<b>📡 FARANG.FM</b>\n\n24/7 tropical radio from Thailand 🌴\nMusic for expats, tourists &amp; locals worldwide.\n\n<b>Streams:</b> 🌙 LOFI · 🌊 CHILL · 🛵 ROAD · 🔥 DANCE\n\n<b>Free · High Quality · Always On</b>",
        "advertise_text": "<b>💼 Advertise on FARANG.FM</b>\n\nReach thousands of listeners in Thailand &amp; worldwide.\n\n📌 Website Banner\n🎙️ Audio Spot\n📱 Telegram Post\n📦 Full Package\n\nMessage us directly 👇",
        "write_us": "✉️ Write to Us",
        "all_streams": "📻 All Streams",
        "post_usage": "<b>Usage:</b> /post &lt;STREAM&gt; &lt;text&gt;\n\nStreams: LOFI, CHILL, ROAD, DANCE",
        "post_unknown": "❌ Unknown stream: <b>{stream}</b>",
        "post_ok": "✅ Posted! {emoji} {stream}",
        "post_error": "❌ Error: <code>{err}</code>",
        "not_admin": "🚫 Admin only.",
    },
    "th": {
        "welcome": "<b>🎙️ ยินดีต้อนรับสู่ FARANG.FM!</b>\n\nสวัสดี {name}! 👋\n\nวิทยุออนไลน์ 24/7 จากประเทศไทย 🌴\n\n<i>🌙 LOFI · 🌊 CHILL · 🛵 ROAD · 🔥 DANCE</i>",
        "listen_now": "🎧 ฟังเลย",
        "streams": "📻 สตรีม",
        "advertise": "💼 โฆษณา",
        "channel": "📡 ช่อง",
        "about": "ℹ️ เกี่ยวกับ",
        "back": "🔙 กลับ",
        "choose_stream": "<b>🎧 เลือกสตรีมของคุณ:</b>",
        "stream_info": "<b>{emoji} สตรีม {stream}</b>\n\n{desc}\n\n🎵 <i>320kbps · 24/7 · ทั่วโลก</i>",
        "stream_descs": {
            "LOFI": "บีตชิลล์ บรรยากาศแสงจันทร์ โหมดโฟกัส",
            "CHILL": "สายลมทะเล บรรยากาศยามเย็น ผ่อนคลายสุดๆ",
            "ROAD": "ไฟถนนนีออน พลังงานตุ๊กตุ๊ก เต็มสปีด",
            "DANCE": "เพลงคลับ เบสหนัก สนุกทั้งคืน",
        },
        "about_text": "<b>📡 FARANG.FM</b>\n\nวิทยุออนไลน์ 24/7 จากประเทศไทย 🌴\nเพลงสำหรับชาวต่างชาติ นักท่องเที่ยว และคนท้องถิ่นทั่วโลก\n\n<b>สตรีม:</b> 🌙 LOFI · 🌊 CHILL · 🛵 ROAD · 🔥 DANCE\n\n<b>ฟรี · คุณภาพสูง · ออนไลน์ตลอดเวลา</b>",
        "advertise_text": "<b>💼 โฆษณาบน FARANG.FM</b>\n\nเข้าถึงผู้ฟังนับพันคนในไทยและทั่วโลก\n\n📌 แบนเนอร์บนเว็บไซต์\n🎙️ สปอตเสียง\n📱 โพสต์ Telegram\n📦 แพ็กเกจครบชุด\n\nติดต่อเราโดยตรง 👇",
        "write_us": "✉️ ติดต่อเรา",
        "all_streams": "📻 ทุกสตรีม",
        "post_usage": "<b>วิธีใช้:</b> /post &lt;STREAM&gt; &lt;ข้อความ&gt;\n\nสตรีม: LOFI, CHILL, ROAD, DANCE",
        "post_unknown": "❌ ไม่พบสตรีม: <b>{stream}</b>",
        "post_ok": "✅ โพสต์แล้ว! {emoji} {stream}",
        "post_error": "❌ เกิดข้อผิดพลาด: <code>{err}</code>",
        "not_admin": "🚫 สำหรับผู้ดูแลระบบเท่านั้น",
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def tx(user_id: int, key: str, **kwargs) -> str:
    lang = USER_LANG.get(user_id, "en")
    text = T[lang].get(key, T["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text

def stream_desc(user_id: int, stream: str) -> str:
    lang = USER_LANG.get(user_id, "en")
    return T[lang]["stream_descs"].get(stream, T["en"]["stream_descs"][stream])

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text(tx(update.effective_user.id, "not_admin"))
            return
        return await func(update, context)
    return wrapper

def listen_btn(user_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(tx(user_id, "listen_now"), web_app=WebAppInfo(url=WEBSITE_URL))

def main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [listen_btn(user_id), InlineKeyboardButton(tx(user_id, "streams"), callback_data="streams")],
        [InlineKeyboardButton(tx(user_id, "advertise"), callback_data="advertise"),
         InlineKeyboardButton(tx(user_id, "channel"), url=CHANNEL_URL)],
        [InlineKeyboardButton(tx(user_id, "about"), callback_data="about")],
    ])

LANG_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
    InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
    InlineKeyboardButton("🇹🇭 ภาษาไทย", callback_data="lang_th"),
]])

def channel_post_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🎧 Listen Now", url=WEBSITE_URL),
        InlineKeyboardButton("💬 Бот", url=f"https://t.me/{os.getenv('BOT_USERNAME', 'farangfm_bot')}"),
    ]])

# ═══════════════════════════════════════════════════════════════════════════════
# GROQ AI
# ═══════════════════════════════════════════════════════════════════════════════

GROQ_PROMPT = """You are a content editor for FARANG.FM — an online radio station from Thailand.

Stream: {stream}
Topic/source: {topic}

Write a short, catchy Telegram post (80-130 words) in this style:
- Fun, casual, tropical vibe
- Focus on music & atmosphere of the {stream} stream
- Add relevant emojis
- Include hashtags #FARANGFM and 1-2 topical ones
- Start with a strong hook
- End with a call-to-action (listen, join, vibe with us)
- Mix of English with optional Russian/Thai flavor words

Output ONLY the post text, no explanations."""

def groq_generate(stream: str, topic: str) -> str | None:
    if not GROQ_KEY:
        return None
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": "mixtral-8x7b-32768",
                "messages": [{"role": "user", "content": GROQ_PROMPT.format(stream=stream, topic=topic)}],
                "temperature": 0.8,
                "max_tokens": 250,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"START user={update.effective_user.id}")
    await update.message.reply_text(
        "🌍 Выберите язык  /  Choose language  /  เลือกภาษา:",
        reply_markup=LANG_KEYBOARD,
    )

@admin_only
async def post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(tx(uid, "post_usage"), parse_mode=ParseMode.HTML)
        return
    stream = args[0].upper()
    if stream not in STREAMS:
        await update.message.reply_text(tx(uid, "post_unknown", stream=stream), parse_mode=ParseMode.HTML)
        return
    emoji = STREAMS[stream]
    body = " ".join(args[1:])
    text = f"{emoji} <b>{stream}</b>\n\n{body}"
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID, text=text,
            reply_markup=channel_post_keyboard(), parse_mode=ParseMode.HTML,
        )
        logger.info(f"POST_CHANNEL stream={stream} admin={uid}")
        await update.message.reply_text(tx(uid, "post_ok", emoji=emoji, stream=stream), parse_mode=ParseMode.HTML)
    except TelegramError as e:
        await update.message.reply_text(tx(uid, "post_error", err=str(e)), parse_mode=ParseMode.HTML)

@admin_only
async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "<b>Usage:</b> /generate &lt;STREAM&gt; &lt;topic&gt;\n\n"
            "Example:\n/generate LOFI thai new year",
            parse_mode=ParseMode.HTML,
        )
        return
    stream = args[0].upper()
    if stream not in STREAMS:
        await update.message.reply_text(f"❌ Unknown stream: {stream}")
        return
    topic = " ".join(args[1:])
    msg = await update.message.reply_text("✍️ Generating with Groq AI...")

    result = groq_generate(stream, topic)
    if not result:
        await msg.edit_text("❌ Groq unavailable. Check GROQ_API_KEY secret.")
        return

    emoji = STREAMS[stream]
    preview = f"{emoji} <b>{stream}</b>\n\n{result}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Publish to Channel", callback_data=f"genpub_{stream}"),
         InlineKeyboardButton("❌ Discard", callback_data="gen_discard")],
    ])
    context.user_data["gen_text"] = result
    context.user_data["gen_stream"] = stream
    await msg.edit_text(preview, reply_markup=kb, parse_mode=ParseMode.HTML)

@admin_only
async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    posts = get_pending_posts()
    if not posts:
        await update.message.reply_text("📭 No posts pending moderation.")
        return
    for post in posts[:5]:
        pid = post["id"]
        short = post["rewritten_text"][:200] + ("…" if len(post["rewritten_text"]) > 200 else "")
        text = f"📰 <b>Pending</b> <code>{pid[:8]}</code>\n\n{short}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Publish", callback_data=f"approve_{pid}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"reject_{pid}")],
            [InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{pid}")],
        ])
        await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@admin_only
async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    sched = get_schedule()

    if not args:
        if not sched:
            await update.message.reply_text("📅 No scheduled posts.")
            return
        lines = ["<b>📅 Scheduled Posts</b>\n"]
        for key, info in sched.items():
            status = "✅" if info.get("enabled") else "⏸️"
            lines.append(f"{status} <b>{info['display_name']}</b> — {info['time_value']} ({info['stream']})")
        lines.append("\n<i>Commands:</i> /schedule on|off|del &lt;key&gt;")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    sub = args[0].lower()

    if sub == "on" and len(args) >= 2:
        toggle_scheduled_post(args[1], True)
        await update.message.reply_text(f"✅ <b>{args[1]}</b> enabled.", parse_mode=ParseMode.HTML)
    elif sub == "off" and len(args) >= 2:
        toggle_scheduled_post(args[1], False)
        await update.message.reply_text(f"⏸️ <b>{args[1]}</b> paused.", parse_mode=ParseMode.HTML)
    elif sub == "del" and len(args) >= 2:
        remove_scheduled_post(args[1])
        await update.message.reply_text(f"🗑️ <b>{args[1]}</b> deleted.", parse_mode=ParseMode.HTML)
    elif sub == "add" and len(args) >= 5:
        key, time_val, stream_val = args[1], args[2], args[3].upper()
        tmpl = " ".join(args[4:])
        if stream_val not in STREAMS:
            await update.message.reply_text(f"❌ Unknown stream: {stream_val}")
            return
        add_scheduled_post(key, key.replace("_", " ").title(), time_val, stream_val, tmpl)
        await update.message.reply_text(f"✅ Added <b>{key}</b> at {time_val}.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            "<b>Usage:</b>\n"
            "/schedule — list all\n"
            "/schedule on|off|del &lt;key&gt;\n"
            "/schedule add &lt;key&gt; &lt;HH:MM&gt; &lt;STREAM&gt; &lt;text&gt;",
            parse_mode=ParseMode.HTML,
        )

# ═══════════════════════════════════════════════════════════════════════════════
# JOB QUEUE: auto-publish scheduled posts (Bangkok timezone)
# ═══════════════════════════════════════════════════════════════════════════════

async def scheduled_post_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(BKK_TZ).strftime("%H:%M")
    for key, info in get_schedule().items():
        if not info.get("enabled"):
            continue
        if info.get("time_value") != now:
            continue
        stream = info.get("stream", "LOFI")
        emoji = STREAMS.get(stream, "🎵")
        text = info.get("template", "").format(stream=stream, emoji=emoji)
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID, text=text,
                reply_markup=channel_post_keyboard(), parse_mode=ParseMode.HTML,
            )
            logger.info(f"SCHEDULED_POST key={key} stream={stream} time={now} (Bangkok)")
        except TelegramError as e:
            logger.error(f"Scheduled post error ({key}): {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MODERATION CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

async def approve_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return

    post_id = query.data.replace("approve_", "")
    post = get_post(post_id)
    if not post:
        await query.edit_message_text("❌ Post not found.")
        return

    text = post["rewritten_text"]
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID, text=text,
            reply_markup=channel_post_keyboard(), parse_mode=ParseMode.HTML,
        )
        update_post_status(post_id, "approved")
        logger.info(f"APPROVED post_id={post_id}")
        await query.edit_message_text(f"✅ <b>Published to @farangfm!</b>\n\n{text[:100]}…", parse_mode=ParseMode.HTML)
    except TelegramError as e:
        await query.edit_message_text(f"❌ Error: {e}")

async def reject_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    post_id = query.data.replace("reject_", "")
    update_post_status(post_id, "rejected")
    logger.info(f"REJECTED post_id={post_id}")
    await query.edit_message_text("❌ <b>Post rejected.</b>", parse_mode=ParseMode.HTML)

async def edit_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    post_id = query.data.replace("edit_", "")
    post = get_post(post_id)
    if not post:
        await query.edit_message_text("❌ Post not found.")
        return
    context.user_data["editing_post_id"] = post_id
    original = post["rewritten_text"]
    await query.edit_message_text(
        f"✏️ <b>Edit the post and send it as a message:</b>\n\n"
        f"<i>Current text:</i>\n{original}",
        parse_mode=ParseMode.HTML,
    )
    return STATE_EDIT_TEXT

async def edit_post_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    post_id = context.user_data.pop("editing_post_id", None)
    new_text = update.message.text
    if not post_id:
        await update.message.reply_text("❌ No post being edited.")
        return ConversationHandler.END
    update_post_text(post_id, new_text)
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID, text=new_text,
            reply_markup=channel_post_keyboard(), parse_mode=ParseMode.HTML,
        )
        update_post_status(post_id, "approved")
        logger.info(f"EDITED+PUBLISHED post_id={post_id}")
        await update.message.reply_text("✅ <b>Edited post published!</b>", parse_mode=ParseMode.HTML)
    except TelegramError as e:
        await update.message.reply_text(f"❌ Error: {e}")
    return ConversationHandler.END

async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("editing_post_id", None)
    await update.message.reply_text("❌ Edit cancelled.")
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN MENU CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    name = query.from_user.first_name

    if data.startswith("lang_"):
        USER_LANG[uid] = data[5:]
        await query.edit_message_text(
            tx(uid, "welcome", name=name),
            reply_markup=main_keyboard(uid), parse_mode=ParseMode.HTML,
        )

    elif data == "main":
        await query.edit_message_text(
            tx(uid, "welcome", name=name),
            reply_markup=main_keyboard(uid), parse_mode=ParseMode.HTML,
        )

    elif data == "streams":
        rows = [[InlineKeyboardButton(f"{e} {s}", callback_data=f"s_{s}")]
                for s, e in STREAMS.items()]
        rows.append([InlineKeyboardButton(tx(uid, "back"), callback_data="main")])
        await query.edit_message_text(
            tx(uid, "choose_stream"),
            reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML,
        )

    elif data.startswith("s_"):
        stream = data[2:]
        emoji = STREAMS.get(stream, "🎵")
        desc = stream_desc(uid, stream)
        text = tx(uid, "stream_info", emoji=emoji, stream=stream, desc=desc)
        kb = InlineKeyboardMarkup([
            [listen_btn(uid)],
            [InlineKeyboardButton(tx(uid, "all_streams"), callback_data="streams"),
             InlineKeyboardButton(tx(uid, "back"), callback_data="main")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data == "about":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Telegram", url=CHANNEL_URL),
             InlineKeyboardButton("🌐 Website", web_app=WebAppInfo(url=WEBSITE_URL))],
            [InlineKeyboardButton(tx(uid, "back"), callback_data="main")],
        ])
        await query.edit_message_text(tx(uid, "about_text"), reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data == "advertise":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(tx(uid, "write_us"), url=CHANNEL_URL)],
            [InlineKeyboardButton(tx(uid, "back"), callback_data="main")],
        ])
        await query.edit_message_text(tx(uid, "advertise_text"), reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data.startswith("genpub_"):
        stream = data[7:]
        emoji = STREAMS.get(stream, "🎵")
        text = context.user_data.pop("gen_text", "")
        full = f"{emoji} <b>{stream}</b>\n\n{text}"
        context.user_data.pop("gen_stream", None)
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID, text=full,
                reply_markup=channel_post_keyboard(), parse_mode=ParseMode.HTML,
            )
            await query.edit_message_text(f"✅ Published! {emoji} {stream}", parse_mode=ParseMode.HTML)
        except TelegramError as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif data == "gen_discard":
        context.user_data.pop("gen_text", None)
        context.user_data.pop("gen_stream", None)
        await query.edit_message_text("🗑️ Discarded.")

# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK HANDLER (для приёма постов от n8n)
# ══════════════════════════════════responseAskingViewsBinding═════════════════════════════════════════════

# Для простоты, webhook эндпоинт можно добавить позже через Flask/FastAPI
# Пока оставляем polling режим, а посты от n8n будут приходить через отдельный сервер
# Или можно интегрировать с текущим ботом через webhook_url

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # Запуск health server в отдельном потоке
    Thread(target=run_health_server, daemon=True).start()
    
    # Инициализация базы данных
    try:
        init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)
    
    logger.info("🤖 FARANG.FM Bot v4.0 starting...")
    logger.info(f"📡 Channel: {CHANNEL_ID}  |  👤 Admin: {ADMIN_ID}")
    logger.info(f"🤖 Groq AI: {'enabled' if GROQ_KEY else 'DISABLED — set GROQ_API_KEY'}")
    logger.info(f"🌐 Website: {WEBSITE_URL}")
    
    # Создание приложения
    app = Application.builder().token(TOKEN).build()
    
    # Edit-post conversation handler
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_post_start, pattern="^edit_")],
        states={STATE_EDIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_post_save)]},
        fallbacks=[CommandHandler("cancel", edit_cancel)],
        per_message=False,
    )
    
    # Register handlers
    app.add_handler(edit_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post_cmd))
    app.add_handler(CommandHandler("generate", generate_cmd))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CallbackQueryHandler(approve_post, pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(reject_post, pattern="^reject_"))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_error_handler(error_handler)
    
    # Scheduled posts: check every minute
    app.job_queue.run_repeating(scheduled_post_job, interval=60, first=10)
    
    logger.info("🚀 Bot is running! Starting polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()