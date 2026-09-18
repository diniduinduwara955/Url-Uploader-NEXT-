import time

def humanbytes(size):
    if not size: return "Unknown"
    value=float(size)
    for unit in ("B","KB","MB","GB","TB"):
        if value < 1024 or unit=="TB": return f"{value:.2f} {unit}"
        value/=1024

def progress_text(label,current,total,start):
    elapsed=max(time.time()-start,0.01)
    speed=current/elapsed
    pct=(current*100/total) if total else 0
    eta=int((total-current)/speed) if total and speed else 0
    bar="▣"*int(pct//10)+"▢"*(10-int(pct//10))
    return (f"{label}\n\n┏━━━━✦[{bar}]✦━━━━\n"
            f"┃ 📦 Progress : {pct:.2f}%\n"
            f"┃ ✅ Done    : {humanbytes(current)}\n"
            f"┃ 📁 Total   : {humanbytes(total)}\n"
            f"┃ 🚀 Speed   : {humanbytes(int(speed))}/s\n"
            f"┃ 🕒 ETA     : {eta}s\n┗━━━━━━━━━━━━━━━━━━━━━")
