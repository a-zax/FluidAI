import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.time_utils import now_iso


DB_PATH = Path("data") / "assistant.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                requester TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sla_hours INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                generated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pending_actions (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                confirmed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                session_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def fetch_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def fetch_one(query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def execute(query: str, params: tuple = ()) -> None:
    with get_connection() as conn:
        conn.execute(query, params)


def execute_returning_id(query: str, params: tuple = ()) -> int:
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return int(cursor.lastrowid)


def to_json(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def from_json(value: str) -> Dict[str, Any]:
    return json.loads(value)


def audit_event(event_type: str, payload: Dict[str, Any], session_id: Optional[str] = None) -> None:
    execute(
        "INSERT INTO audit_events (event_type, session_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
        (event_type, session_id, to_json(payload), now_iso()),
    )


init_db()
