import asyncio
import shutil
import time
from pathlib import Path

import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_TOKEN, API_ID, API_HASH, ASSISTANT_SESSION, DOWNLOAD_LOCATION, MAX_FILE_SIZE

ROOT=Path(DOWNLOAD_LOCATION)
ROOT.mkdir(parents=True,exist_ok=True)
bot=Client("url_uploader_next_bot",api_id=API_ID,api_hash=API_HASH,bot_token=BOT_TOKEN)
assistant=Client("url_uploader_next_assistant",api_id=API_ID,api_hash=API_HASH,session_string=ASSISTANT_SESSION)


def humanbytes(n):
    if not n:return "Unknown"
    v=float(n)
    for u in ("B","KB","MB","GB","TB"):
        if v<1024 or u=="TB": return f"{v:.2f} {u}"
        v/=1024

async def show_progress(m,label,current,total,start):
    elapsed=max(time.time()-start,0.01); speed=current/elapsed
    pct=current*100/total if total else 0; eta=(total-current)/speed if total and speed else 0
    bar=("▣"*int(pct//10)).ljust(10,"▢")
    try:
        await m.edit_text(f"{label}\n\n┏━━━━✦[{bar}]✦━━━━\n┃ 📦 Progress : {pct:.2f}%\n┃ ✅ Done    : {humanbytes(current)}\n┃ 📁 Total   : {humanbytes(total)}\n┃ 🚀 Speed   : {humanbytes(int(speed))}/s\n┃ 🕒 ETA     : {int(eta)}s\n┗━━━━━━━━━━━━━━━━━━━━━")
    except Exception: pass

async def download(url,dest,status):
    timeout=aiohttp.ClientTimeout(total=None,sock_connect=60,sock_read=300)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.get(url,allow_redirects=True) as r:
            r.raise_for_status(); total=int(r.headers.get("Content-Length") or 0)
            if total>MAX_FILE_SIZE: raise ValueError("File is larger than 3900 MB.")
            current=0; start=time.time()
            with open(dest,"wb") as f:
                while True:
                    chunk=await r.content.read(1024*1024)
                    if not chunk: break
                    f.write(chunk); current+=len(chunk)
                    if current>MAX_FILE_SIZE: raise ValueError("File exceeded the 3900 MB limit.")
                    if current%(8*1024*1024)<len(chunk): await show_progress(status,"📥 Downloading...",current,total,start)
            return current

@bot.on_message(filters.private & filters.command("start"))
async def start_handler(_,m):
    await m.reply_text("👋 Hello!\n\nI'm URL Uploader NEXT.\nSend a direct link to upload it to Telegram.\n\n📦 Maximum file size: 3900 MB",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings",callback_data="settings")],[InlineKeyboardButton("ℹ️ Help",callback_data="help")]]))

@bot.on_callback_query()
async def callbacks(_,q):
    if q.data=="help": await q.message.edit_text("📥 Send a direct URL.\n\nCustom name:\nhttps://example.com/file.mp4 | My Movie.mkv")
    elif q.data=="settings": await q.message.edit_text("⚙️ Settings\n\n📦 Maximum: 3900 MB\n📁 Upload mode: Document")
    else: await q.answer()

@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def url_handler(_,m):
    text=m.text.strip()
    if not text.startswith(("http://","https://")): return
    parts=text.split("|",1); url=parts[0].strip()
    name=parts[1].strip() if len(parts)==2 and parts[1].strip() else (Path(url.split("?",1)[0]).name or "download.bin")
    userdir=ROOT/str(m.from_user.id); userdir.mkdir(parents=True,exist_ok=True); dest=userdir/name
    status=await m.reply_text("⏳ Processing your link...")
    try:
        size=await download(url,dest,status)
        await status.edit_text(f"✅ Download complete\n\n📁 {name}\n📦 {humanbytes(size)}\n\n📤 Uploading...")
        await assistant.send_document(m.chat.id,str(dest),caption=f"📁 {name}\n📦 {humanbytes(size)}")
        await status.edit_text("✅ Upload completed successfully.")
    except Exception as e:
        await status.edit_text(f"❌ Error\n\n{e}")
    finally: shutil.rmtree(userdir,ignore_errors=True)

async def main():
    await assistant.start(); await bot.start(); print("URL Uploader NEXT is running"); await asyncio.Event().wait()

if __name__=="__main__": asyncio.run(main())
