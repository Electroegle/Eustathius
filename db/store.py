import sqlite3, json
from datetime import datetime
from pathlib import Path
DB_PATH = Path(__file__).parent / "eustathius.db"
def get_conn():
    conn = sqlite3.connect(str(DB_PATH)); conn.row_factory = sqlite3.Row; return conn
def init():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, task_description TEXT, skill_used TEXT,
        model_used TEXT, priority TEXT, result TEXT, status TEXT
    );
    """)
    conn.commit(); conn.close()
init()
def add_task(desc, skill, model, prio, result, status):
    conn = get_conn()
    conn.execute("INSERT INTO tasks VALUES (NULL,?,?,?,?,?,?,?)",
                 (datetime.now().isoformat(), desc, skill, model, prio, result, status))
    conn.commit(); conn.close()
def get_recent_tasks(limit=10):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
