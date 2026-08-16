"""Persistent fridge memory and user preferences (SQLite)."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "fridge.db"


@dataclass
class Item:
    name: str
    quantity: str | None
    confidence: str


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS fridge (
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity TEXT,
                confidence TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, name)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS preferences (
                user_id INTEGER PRIMARY KEY,
                text TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )


def upsert_item(user_id: int, name: str, quantity: str | None, confidence: str) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO fridge (user_id, name, quantity, confidence)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (user_id, name) DO UPDATE SET
                 quantity = excluded.quantity,
                 confidence = excluded.confidence,
                 updated_at = datetime('now')""",
            (user_id, name.strip().lower(), quantity, confidence),
        )


def remove_item(user_id: int, name: str) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM fridge WHERE user_id = ? AND name LIKE ?",
            (user_id, f"%{name.strip().lower()}%"),
        )
        return cur.rowcount > 0


def clear_fridge(user_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM fridge WHERE user_id = ?", (user_id,))


def get_fridge(user_id: int) -> list[Item]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT name, quantity, confidence FROM fridge WHERE user_id = ? ORDER BY name",
            (user_id,),
        ).fetchall()
    return [Item(name=r[0], quantity=r[1], confidence=r[2]) for r in rows]


def set_preference(user_id: int, text: str) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO preferences (user_id, text) VALUES (?, ?)
               ON CONFLICT (user_id) DO UPDATE SET text = excluded.text,
                 updated_at = datetime('now')""",
            (user_id, text.strip()),
        )


def get_preference(user_id: int) -> str | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT text FROM preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row[0] if row else None
