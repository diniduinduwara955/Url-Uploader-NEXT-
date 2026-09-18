import asyncio
import os
import shutil
import time
from pathlib import Path

import aiohttp
from pyrogram import Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import MAX_FILE_SIZE, DOWNLOAD_LOCATION
from utils import humanbytes, progress_text

async def download_direct(url, destination, status, cancel_event):
    timeout=aiohttp.ClientTimeout(total=None,sock_connect=60,sock_read=300)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url,allow_redirects=True) as response:
            response.raise_for_status()
            total=int(response.headers.get("Content-Length") or 0)
            if total and total>MAX_FILE_SIZE: raise ValueError("File is larger than 3900 MB.")
            start=time.time(); current=0
            with open(destination,"wb") as fp:
                while True:
                    if cancel_event.is_set(): raise asyncio.CancelledError
                    chunk=await response.content.read(1024*1024)
                    if not chunk: break
                    fp.write(chunk); current+=len(chunk)
                    if current>MAX_FILE_SIZE: raise ValueError("Downloaded file exceeded 3900 MB.")
                    if current%(8*1024*1024)<len(chunk):
                        try: await status.edit_text(progress_text("📥 Downloading...",current,total,start))
                        except Exception: pass
            return current

async def upload_document(client, chat_id, path, caption, progress_message):
    started=time.time()
    async def cb(current,total,*_):
        try: await progress_message.edit_text(progress_text("📤 Uploading...",current,total,started))
        except Exception: pass
    return await client.send_document(chat_id, str(path), caption=caption, progress=cb)
