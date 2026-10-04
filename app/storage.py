"""SQLite persistence for recruiter accounts and uploaded resume records."""
import json
import sqlite3
from contextlib import contextmanager
from app.config import DATA_DIR

DATABASE_PATH = DATA_DIR / "talentlens.sqlite3"


@contextmanager
def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database():
    with connect() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_bytes BLOB NOT NULL,
                profile_json TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS resumes_owner_id ON resumes(user_id, id);
        """)


def user_count() -> int:
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_initial_user(email: str, display_name: str, password_hash: str) -> int:
    """Atomically allow only the first local account to be registered."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] != 0:
            raise ValueError("Initial account setup is already complete")
        cursor = db.execute("INSERT INTO users(email, display_name, password_hash) VALUES (?, ?, ?)",
                            (email.strip().lower(), display_name.strip(), password_hash))
        return int(cursor.lastrowid)


def get_user(email: str):
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int):
    with connect() as db:
        row = db.execute("SELECT id, email, display_name FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def save_resume(user_id: int, filename: str, content_type: str, file_bytes: bytes, profile: dict, embedding):
    with connect() as db:
        cursor = db.execute("""INSERT INTO resumes
            (user_id, filename, content_type, file_bytes, profile_json, embedding)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, filename, content_type, file_bytes,
             json.dumps(profile, ensure_ascii=False), embedding.tobytes()))
        return int(cursor.lastrowid)


def list_resumes(user_id: int):
    with connect() as db:
        rows = db.execute("SELECT id, filename, profile_json, embedding FROM resumes WHERE user_id = ? ORDER BY id",
                          (user_id,)).fetchall()
        return [dict(row) for row in rows]


def list_resume_files(user_id: int):
    with connect() as db:
        rows = db.execute("SELECT id, filename, content_type, file_bytes, created_at FROM resumes WHERE user_id = ? ORDER BY id",
                          (user_id,)).fetchall()
        return [dict(row) for row in rows]
