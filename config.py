import os

BOT_TOKEN=os.environ.get("BOT_TOKEN") or os.environ.get("UPLOADER_BOT_TOKEN","")
API_ID=int(os.environ.get("API_ID") or os.environ.get("UPLOADER_API_ID","0"))
API_HASH=os.environ.get("API_HASH") or os.environ.get("UPLOADER_API_HASH","")
ASSISTANT_SESSION=os.environ.get("ASSISTANT_SESSION") or os.environ.get("UPLOADER_SESSION","")
DOWNLOAD_LOCATION=os.environ.get("DOWNLOAD_LOCATION","./DOWNLOADS")
MAX_FILE_SIZE=3900*1024*1024
CHUNK_SIZE=1024*1024
