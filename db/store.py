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
    CREATE TABLE IF NOT EXISTS model_benchmarks (
        model_name TEXT PRIMARY KEY, tokens_per_sec REAL, updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS council_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
        prompt TEXT, final_answer TEXT, details TEXT
    );
    CREATE TABLE IF NOT EXISTS model_stats (
        model_name TEXT PRIMARY KEY,
        success_count INTEGER DEFAULT 0,
        total_count INTEGER DEFAULT 0
    );
    """)
    conn.commit(); conn.close()
init()

def save_model_benchmark(model, tps):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO model_benchmarks VALUES (?,?,?)", (model, tps, datetime.now().isoformat()))
    conn.commit(); conn.close()

def get_model_benchmark(model):
    conn = get_conn()
    row = conn.execute("SELECT tokens_per_sec FROM model_benchmarks WHERE model_name=?", (model,)).fetchone()
    conn.close()
    return row[0] if row else None

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

def add_council_session(data):
    conn = get_conn()
    conn.execute("INSERT INTO council_sessions (timestamp,prompt,final_answer,details) VALUES (?,?,?,?)",
                 (datetime.now().isoformat(), data["prompt"], data["final_answer"], json.dumps(data["answers"])))
    conn.commit(); conn.close()

def record_model_result(model, success=True):
    conn = get_conn()
    row = conn.execute("SELECT * FROM model_stats WHERE model_name=?", (model,)).fetchone()
    if row:
        conn.execute("UPDATE model_stats SET total_count=total_count+1, success_count=success_count+? WHERE model_name=?",
                     (1 if success else 0, model))
    else:
        conn.execute("INSERT INTO model_stats VALUES (?,?,?)", (model, 1 if success else 0, 1))
    conn.commit(); conn.close()

def get_model_stats():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM model_stats").fetchall()
    conn.close()
    return {r["model_name"]: {"success": r["success_count"], "total": r["total_count"]} for r in rows}
