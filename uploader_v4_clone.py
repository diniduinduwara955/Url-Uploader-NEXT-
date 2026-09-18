# URL Uploader NEXT — V4-style workflow
# Large-file MTProto uploader. No Cine Universe Mini App code is imported here.

import asyncio
import json
import os
import shutil
import time
from pathlib import Path

import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_ID = int(os.environ.get("API_ID", "0") or 0)
API_HASH = os.environ.get("API_HASH", "")
ASSISTANT_SESSION = os.environ.get("ASSISTANT_SESSION", "")
DOWNLOAD_LOCATION = os.environ.get("DOWNLOAD_LOCATION", "./DOWNLOADS")
MAX_FILE_SIZE = 3900 * 1024 * 1024

ROOT = Path(DOWNLOAD_LOCATION)
ROOT.mkdir(parents=True, exist_ok=True)

bot = Client("URLUploaderNEXT", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
assistant = Client("URLUploaderNEXT_Assistant", api_id=API_ID, api_hash=API_HASH, session_string=ASSISTANT_SESSION)

def humanbytes(size):
    if not size:
        return "Unknown"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠️ Settings", callback_data="settings")],
        [InlineKeyboardButton("🤝 Help", callback_data="help"), InlineKeyboardButton("ℹ️ About", callback_data="about")],
        [InlineKeyboardButton("✖️ Close", callback_data="close")],
    ])

async def edit_progress(message, title, current, total, start):
    elapsed = max(time.time() - start, 0.01)
    speed = current / elapsed
    pct = current * 100 / total if total else 0
    eta = (total-current) / speed if total and speed else 0
    done = int(pct // 10)
    bar = "▣" * done + "▢" * (10 - done)
    text = (
        f"{title}\n\n"
        f"┏━━━━✦[{bar}]✦━━━━\n"
        f"┃ 📦 Progress : {pct:.2f}%\n"
        f"┃ ✅ Done    : {humanbytes(current)}\n"
        f"┃ 📁 Total   : {humanbytes(total)}\n"
        f"┃ 🚀 Speed   : {humanbytes(int(speed))}/s\n"
        f"┃ 🕒 ETA     : {int(eta)}s\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        await message.edit_text(text)
    except Exception:
        pass

async def download_file(url, destination, status):
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=60, sock_read=300)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, allow_redirects=True) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            if total and total > MAX_FILE_SIZE:
                raise ValueError("File size is above the 3900 MB limit.")
            current = 0
            start = time.time()
            with open(destination, "wb") as fp:
                while True:
                    chunk = await response.content.read(1024 * 1024)
                    if not chunk:
                        break
                    fp.write(chunk)
                    current += len(chunk)
                    if current > MAX_FILE_SIZE:
                        raise ValueError("Downloaded file exceeded the 3900 MB limit.")
                    if current % (8 * 1024 * 1024) < len(chunk):
                        await edit_progress(status, "📥 Downloading...", current, total, start)
            return current

@bot.on_message(filters.private & filters.command("start"))
async def start(_, message):
    await message.reply_text(
        f"👋 Hello {message.from_user.mention}\n\n"
        "I'm URL Uploader NEXT.\n"
        "Send a direct link and I'll process it.\n\n"
        "📦 Maximum: 3900 MB",
        reply_markup=menu()
    )

@bot.on_callback_query(filters.regex("^settings$"))
async def settings(_, query):
    await query.message.edit_text(
        "⚙️ CURRENT SETTINGS\n\n"
        "📁 Upload mode : DOCUMENT\n"
        "📦 Max file    : 3900 MB\n"
        "🖼 Thumbnail   : handled by assistant upload flow",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="home")]])
    )

@bot.on_callback_query(filters.regex("^help$"))
async def help_page(_, query):
    await query.message.edit_text(
        "📚 HOW TO USE\n\n"
        "Send a direct URL.\n"
        "Custom name:\n"
        "https://example.com/file.mp4 | My Movie.mkv",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="home")]])
    )

@bot.on_callback_query(filters.regex("^about$"))
async def about(_, query):
    await query.message.edit_text(
        "╭───────────────⍟\n"
        "│ 📛 URL Uploader NEXT\n"
        "│ 💻 Python + Pyrogram\n"
        "│ 📦 3900 MB MTProto mode\n"
        "╰───────────────⍟",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="home")]])
    )

@bot.on_callback_query(filters.regex("^home$"))
async def home(_, query):
    await query.message.edit_text(
        f"👋 Hello {query.from_user.mention}\n\n"
        "Send a direct link to start.",
        reply_markup=menu()
    )

@bot.on_callback_query(filters.regex("^close$"))
async def close(_, query):
    await query.message.delete()

@bot.on_message(filters.private & filters.text)
async def receive_url(_, message):
    if message.text.startswith("/"):
        return
    text = message.text.strip()
    if not text.startswith(("http://", "https://")):
        return

    pieces = text.split("|", 1)
    url = pieces[0].strip()
    filename = pieces[1].strip() if len(pieces) == 2 and pieces[1].strip() else Path(url.split("?", 1)[0]).name or "download.bin"
    work = ROOT / str(message.from_user.id)
    work.mkdir(parents=True, exist_ok=True)
    destination = work / filename
    status = await message.reply_text("⌛ Pʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ʟɪɴᴋ...")
    try:
        size = await download_file(url, destination, status)
        await status.edit_text(f"📤 Uploading...\n\n📁 {filename}\n📦 {humanbytes(size)}")
        await assistant.send_document(
            chat_id=message.chat.id,
            document=str(destination),
            caption=f"📁 {filename}\n📦 {humanbytes(size)}",
        )
        await status.edit_text("✅ Upload completed successfully.")
    except Exception as exc:
        await status.edit_text(f"❌ Upload failed\n\n{exc}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

async def main():
    if not ASSISTANT_SESSION:
        raise RuntimeError("ASSISTANT_SESSION is required for 3900 MB MTProto uploads.")
    await assistant.start()
    await bot.start()
    print("URL Uploader NEXT started")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
