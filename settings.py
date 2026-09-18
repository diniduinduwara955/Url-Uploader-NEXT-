import json
from pathlib import Path

STORE=Path("settings.json")

def load():
    try:return json.loads(STORE.read_text())
    except Exception:return {}

def save(data): STORE.write_text(json.dumps(data,indent=2))

def user_data(user_id):
    data=load(); return data.setdefault(str(user_id),{"upload_as_doc":True,"thumbnail":None,"caption":""})
