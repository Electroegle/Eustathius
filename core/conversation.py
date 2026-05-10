import json, uuid
from pathlib import Path
from datetime import datetime
from config_loader import config

SESSIONS_DIR = Path(config.get("conversation",{}).get("sessions_dir","conversations"))
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

class ConversationManager:
    def __init__(self):
        self.session_id = None
        self.history = []

    def new_session(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.history = []
        return self.session_id

    def add_exchange(self, user, assistant):
        self.history.append({"role":"user","content":user,"timestamp":datetime.now().isoformat()})
        self.history.append({"role":"assistant","content":assistant,"timestamp":datetime.now().isoformat()})

    def save_session(self):
        if not self.session_id: return
        (SESSIONS_DIR / f"{self.session_id}.json").write_text(json.dumps({"id":self.session_id,"history":self.history}, indent=2))

    def load_session(self, sid):
        file = SESSIONS_DIR / f"{sid}.json"
        if not file.exists(): return False
        data = json.loads(file.read_text())
        self.session_id = data["id"]; self.history = data["history"]
        return True

    def list_sessions(self): return [f.stem for f in SESSIONS_DIR.glob("*.json")]
