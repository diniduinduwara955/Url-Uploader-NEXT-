import asyncio
import os
import re
import shutil
import time
from pathlib import Path

import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_TOKEN, API_ID, API_HASH, ASSISTANT_SESSION, DOWNLOAD_LOCATION, MAX_FILE_SIZE

ROOT = Path(DOWNLOAD_LOCATION)
ROOT.mkdir(parents=True, exist_ok=True)

bot = Client("url_uploader_next_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
assistant = Client("url_uploader_next_assistant", api_id=API_ID, api_hash=API_HASH, session_string=ASSISTANT_SESSION)

JOBS = {}


def humanbytes(n):
    if not n:
        return "Unknown"
    v = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024 or u == "TB":
            return f"{v:.2f} {u}"
        v /= 1024
    return "Unknown"


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠️ SETTINGS", callback_data="settings")],
        [InlineKeyboardButton("🤝 HELP", callback_data="help"), InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")],
        [InlineKeyboardButton("✖️ CLOSE", callback_data="close")],
    ])


def progress_text(label, current, total, started):
    elapsed = max(time.time() - started, 0.01)
    speed = current / elapsed
    pct = min(100.0, current * 100 / total) if total else 0.0
    eta = int((total - current) / speed) if total and speed else 0
    done = min(10, int(pct // 10))
    bar = "▣" * done + "▢" * (10 - done)
    return (
        f"{label}\n\n┏━━━━✦[{bar}]✦━━━━\n"
        f"┃ 📦 Progress : {pct:.2f}%\n"
        f"┃ ✅ Done    : {humanbytes(current)}\n"
        f"┃ 📁 Total   : {humanbytes(total)}\n"
        f"┃ 🚀 Speed   : {humanbytes(int(speed))}/s\n"
        f"┃ 🕒 ETA     : {eta}s\n┗━━━━━━━━━━━━━━━━━━━━━"
    )


async def safe_edit(message, text, markup=None):
    try:
        await message.edit_text(text, reply_markup=markup)
    except Exception:
        pass


async def download_direct(url, destination, status, cancel_event):
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=60, sock_read=300)
    async with aiohttp.ClientSession(timeout=timeout, raise_for_status=True) as session:
        async with session.get(url, allow_redirects=True) as response:
            total = int(response.headers.get("Content-Length") or 0)
            if total and total > MAX_FILE_SIZE:
                raise ValueError("File is larger than the 3900 MB limit.")
            started = time.time()
            current = 0
            with destination.open("wb") as fp:
                while True:
                    if cancel_event.is_set():
                        raise asyncio.CancelledError
                    chunk = await response.content.read(1024 * 1024)
                    if not chunk:
                        break
                    fp.write(chunk)
                    current += len(chunk)
                    if current > MAX_FILE_SIZE:
                        raise ValueError("Downloaded file exceeded the 3900 MB limit.")
                    if current % (8 * 1024 * 1024) < len(chunk):
                        await safe_edit(status, progress_text("📥 Dᴏᴡɴʟᴏᴀᴅɪɴɢ...", current, total, started), cancel_markup(status.chat.id))
            return current


def cancel_markup(chat_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⛔ CANCEL", callback_data=f"cancel:{chat_id}", style=enums.ButtonStyle.DANGER)]])


@bot.on_message(filters.private & filters.command("start"))
async def start_handler(_, message):
    await message.reply_text(
        f"👋 Hello {message.from_user.mention}\n\n"
        "I'm URL Uploader NEXT.\n"
        "Send a direct URL and choose how you want it uploaded.\n\n"
        "📦 Maximum file size: 3900 MB",
        reply_markup=menu(),
    )


@bot.on_message(filters.private & filters.command("help"))
async def help_handler(_, message):
    await message.reply_text(
        "📚 HOW TO USE\n\n"
        "1. Send a direct URL.\n"
        "2. Add a custom name like:\n"
        "https://example.com/file.mp4 | My Movie.mkv\n\n"
        "You can also use a URL supported by yt-dlp."
    )


@bot.on_message(filters.private & filters.command("settings"))
async def settings_handler(_, message):
    await message.reply_text("⚙️ SETTINGS\n\n📁 Default mode: DOCUMENT\n📦 Maximum: 3900 MB\n🖼 Custom thumbnail: supported in upload flow")


@bot.on_callback_query()
async def callbacks(_, query):
    data = query.data or ""
    if data == "settings":
        await safe_edit(query.message, "⚙️ SETTINGS\n\n📁 Upload mode: DOCUMENT\n📦 Maximum: 3900 MB\n🖼 Thumbnail: ready for per-user upload flow")
    elif data == "help":
        await safe_edit(query.message, "📚 HOW TO USE\n\nSend a direct URL.\n\nCustom name:\nhttps://example.com/file.mp4 | My Movie.mkv")
    elif data == "about":
        await safe_edit(query.message, "╭───────────────⍟\n│ 📛 URL Uploader NEXT\n│ 💻 Python + Pyrogram\n│ 📦 MTProto 3900 MB mode\n╰───────────────⍟")
    elif data == "home":
        await safe_edit(query.message, f"👋 Hello {query.from_user.mention}\n\nSend a direct link to start.", menu())
    elif data == "close":
        await query.message.delete()
    elif data.startswith("cancel:"):
        chat_id = data.split(":", 1)[1]
        job = JOBS.get(str(chat_id))
        if job:
            job["cancel"].set()
            await query.answer("Cancellation requested.", show_alert=True)
        else:
            await query.answer("No active job.", show_alert=True)
    else:
        await query.answer()


@bot.on_message(filters.private & filters.text)
async def url_handler(_, message):
    text = (message.text or "").strip()
    if text.startswith("/"):
        return
    if not re.search(r"https?://", text, re.I):
        return

    parts = text.split("|", 1)
    url = parts[0].strip()
    custom_name = parts[1].strip() if len(parts) == 2 else ""
    if not custom_name:
        custom_name = Path(url.split("?", 1)[0]).name or "download.bin"
    custom_name = os.path.basename(custom_name) or "download.bin"

    user_dir = ROOT / str(message.from_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    destination = user_dir / custom_name
    status = await message.reply_text("⌛ Pʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ʟɪɴᴋ...", reply_markup=cancel_markup(message.chat.id))
    cancel_event = asyncio.Event()
    JOBS[str(message.chat.id)] = {"cancel": cancel_event, "started": time.time()}

    try:
        size = await download_direct(url, destination, status, cancel_event)
        if cancel_event.is_set():
            raise asyncio.CancelledError

        await safe_edit(status, f"📤 Uᴘʟᴏᴀᴅɪɴɢ...\n\n📁 {custom_name}\n📦 {humanbytes(size)}", cancel_markup(message.chat.id))

        upload_started = time.time()

        async def upload_progress(current, total, *_):
            if cancel_event.is_set():
                raise asyncio.CancelledError
            await safe_edit(status, progress_text("📤 Uᴘʟᴏᴀᴅɪɴɢ...", current, total, upload_started), cancel_markup(message.chat.id))

        await assistant.send_document(
            chat_id=message.chat.id,
            document=str(destination),
            caption=f"📁 {custom_name}\n📦 {humanbytes(size)}",
            progress=upload_progress,
        )
        await safe_edit(status, "✅ Uᴘʟᴏᴀᴅ Cᴏᴍᴘʟᴇᴛᴇᴅ\n\nThanks for using URL Uploader NEXT.")

    except asyncio.CancelledError:
        await safe_edit(status, "⛔ Jᴏʙ Cᴀɴᴄᴇʟʟᴇᴅ")
    except Exception as exc:
        await safe_edit(status, f"❌ Uᴘʟᴏᴀᴅ Fᴀɪʟᴇᴅ\n\n{exc}")
    finally:
        JOBS.pop(str(message.chat.id), None)
        shutil.rmtree(user_dir, ignore_errors=True)


async def main():
    if not BOT_TOKEN or not API_ID or not API_HASH:
        raise RuntimeError("BOT_TOKEN, API_ID and API_HASH are required.")
    if not ASSISTANT_SESSION:
        raise RuntimeError("ASSISTANT_SESSION is required for 3900 MB MTProto uploads.")
    await assistant.start()
    await bot.start()
    print("URL Uploader NEXT is running")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
