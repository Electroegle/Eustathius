import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "eustathius.db"


@contextmanager
def _conn():
    """Context-managed SQLite connection with WAL mode enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_conn():
    """Legacy compatibility shim — callers that need a raw connection."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init():
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT NOT NULL,
            task_description TEXT,
            skill_used       TEXT,
            model_used       TEXT,
            priority         TEXT,
            result           TEXT,
            status           TEXT
        );

        CREATE TABLE IF NOT EXISTS model_benchmarks (
            model_name   TEXT PRIMARY KEY,
            tokens_per_sec REAL NOT NULL,
            updated_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS council_sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT NOT NULL,
            prompt       TEXT,
            final_answer TEXT,
            details      TEXT
        );

        CREATE TABLE IF NOT EXISTS model_stats (
            model_name    TEXT PRIMARY KEY,
            success_count INTEGER NOT NULL DEFAULT 0,
            total_count   INTEGER NOT NULL DEFAULT 0
        );
        """)


_init()


# ── Benchmarks ────────────────────────────────────────────────────────────────

def save_model_benchmark(model: str, tps: float) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO model_benchmarks VALUES (?, ?, ?)",
            (model, tps, datetime.now().isoformat()),
        )


def get_model_benchmark(model: str) -> float | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT tokens_per_sec FROM model_benchmarks WHERE model_name = ?",
            (model,),
        ).fetchone()
    return row[0] if row else None


# ── Tasks ─────────────────────────────────────────────────────────────────────

def add_task(
    desc: str,
    skill: str,
    model: str,
    priority: str,
    result: str,
    status: str,
) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO tasks VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), desc, skill, model, priority, result, status),
        )


def get_recent_tasks(limit: int = 10) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Council ───────────────────────────────────────────────────────────────────

def add_council_session(data: dict) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO council_sessions (timestamp, prompt, final_answer, details) "
            "VALUES (?, ?, ?, ?)",
            (
                datetime.now().isoformat(),
                data.get("prompt", ""),
                data.get("final_answer", ""),
                json.dumps(data.get("answers", {})),
            ),
        )


# ── Model reliability stats ───────────────────────────────────────────────────

def record_model_result(model: str, success: bool = True) -> None:
    with _conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM model_stats WHERE model_name = ?", (model,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE model_stats "
                "SET total_count = total_count + 1, "
                "    success_count = success_count + ? "
                "WHERE model_name = ?",
                (1 if success else 0, model),
            )
        else:
            conn.execute(
                "INSERT INTO model_stats VALUES (?, ?, ?)",
                (model, 1 if success else 0, 1),
            )


def get_model_stats() -> dict[str, dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM model_stats").fetchall()
    return {
        r["model_name"]: {
            "success": r["success_count"],
            "total":   r["total_count"],
        }
        for r in rows
    }
